"""
Applies the per-failure-type retry rules (PLAN.md parameter table) to one
LLM tier (Gemini or Groq). Each tier gets its own budget of retries; when
the budget for the failure type in play is exhausted (or the failure type
is non-retryable), the tier fails and the caller escalates to the next
fallback tier.
"""
import time
from dataclasses import dataclass, field

from .failure_types import FailureType, classify_api_error, has_grounding_failure

TRANSIENT_MAX_RETRIES = 2
MALFORMED_MAX_RETRIES = 1
BACKOFF_BASE_SECONDS = 2  # exponential: 2s, 4s -- clears a per-minute rate-limit window


@dataclass
class TierResult:
    tier: str
    success: bool
    grounded_result: dict | None = None
    retries_used: int = 0
    failure_type: FailureType | None = None
    error: str | None = None
    attempts_log: list = field(default_factory=list)


def run_llm_tier(
    tier_name: str,
    generate_raw_fn,
    parse_fn,
    ground_fn,
    correction_note: str = "",
) -> TierResult:
    """
    generate_raw_fn(extra_instruction: str) -> raw response text. Raises on
        network/API failure.
    parse_fn(raw_text: str) -> dict. Raises (JSONDecodeError/ValueError) on
        malformed output.
    ground_fn(parsed: dict) -> grounded_result dict (see clause_extraction.
        ground_quotes for shape).
    """
    transient_retries = 0
    malformed_retries = 0
    extra_instruction = ""
    attempts_log = []

    while True:
        try:
            raw = generate_raw_fn(extra_instruction)
        except Exception as exc:
            ftype = classify_api_error(exc)
            attempts_log.append({"stage": "generate", "failure_type": ftype.value, "error": str(exc)})

            if ftype == FailureType.TRANSIENT and transient_retries < TRANSIENT_MAX_RETRIES:
                transient_retries += 1
                time.sleep(BACKOFF_BASE_SECONDS * (2 ** (transient_retries - 1)))
                continue

            # QUOTA_EXHAUSTED, UNKNOWN, or TRANSIENT-budget-exhausted: fail
            # this tier, let the caller escalate.
            return TierResult(
                tier=tier_name, success=False, retries_used=transient_retries + malformed_retries,
                failure_type=ftype, error=str(exc), attempts_log=attempts_log,
            )

        try:
            parsed = parse_fn(raw)
        except (ValueError, KeyError) as exc:
            attempts_log.append({"stage": "parse", "failure_type": FailureType.MALFORMED_OUTPUT.value, "error": str(exc)})
            if malformed_retries < MALFORMED_MAX_RETRIES:
                malformed_retries += 1
                extra_instruction = (
                    "\n\nIMPORTANT: your previous response was not valid JSON matching "
                    "the required shape. Respond with ONLY the JSON object, no other text, "
                    "no markdown code fences."
                )
                continue
            return TierResult(
                tier=tier_name, success=False, retries_used=transient_retries + malformed_retries,
                failure_type=FailureType.MALFORMED_OUTPUT, error=str(exc), attempts_log=attempts_log,
            )

        grounded_result = ground_fn(parsed)
        if has_grounding_failure(grounded_result):
            attempts_log.append({"stage": "ground", "failure_type": FailureType.GROUNDING_FAILURE.value})
            # No retry on grounding failure -- same prompt on the same doc
            # tends to reproduce the same hallucination (PLAN.md reasoning).
            return TierResult(
                tier=tier_name, success=False, retries_used=transient_retries + malformed_retries,
                failure_type=FailureType.GROUNDING_FAILURE, grounded_result=grounded_result,
                attempts_log=attempts_log,
            )

        return TierResult(
            tier=tier_name, success=True, grounded_result=grounded_result,
            retries_used=transient_retries + malformed_retries, attempts_log=attempts_log,
        )
