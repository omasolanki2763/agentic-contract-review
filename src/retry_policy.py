"""
Applies the per-failure-type retry rules (PLAN.md parameter table) to one
LLM tier (Gemini or Groq). Each tier gets its own budget of retries; when
the budget for the failure type in play is exhausted (or the failure type
is non-retryable), the tier fails and the caller escalates to the next
fallback tier.
"""
import threading
import time
from dataclasses import dataclass, field

from .failure_types import FailureType, classify_api_error, has_grounding_failure

TRANSIENT_MAX_RETRIES = 2
MALFORMED_MAX_RETRIES = 1
BACKOFF_BASE_SECONDS = 2  # exponential: 2s, 4s -- clears a per-minute rate-limit window

# 3x measured average call latency (Gemini, 3-doc sample: 17.9s/23.9s/20.6s,
# avg 20.8s) -- empirical, not guessed. See DECISIONS.md "Timeout".
CALL_TIMEOUT_SECONDS = 62


def _call_with_timeout(fn, *args, timeout=None):
    """Run fn(*args) with a wall-clock timeout.

    Neither SDK has a reliable native call timeout (see run_pipeline.py,
    which does set a provider-level timeout slightly under this value as
    the first line of defense -- this wrapper is the backstop for whatever
    slips past that). Runs the call on a daemon thread rather than a
    ThreadPoolExecutor: if the underlying network call genuinely hangs
    forever (no server-side timeout support in the SDK), a non-daemon pool
    thread would block process exit forever (verified: leaked
    ThreadPoolExecutor workers are joined by its atexit handler). A daemon
    thread is abandoned cleanly on timeout and can't wedge process exit or
    starve a shared pool.
    """
    if timeout is None:
        timeout = CALL_TIMEOUT_SECONDS

    result = {}

    def target():
        try:
            result["value"] = fn(*args)
        except BaseException as exc:  # noqa: BLE001 -- re-raised on the caller's thread
            result["error"] = exc

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout)

    if thread.is_alive():
        raise TimeoutError(f"call exceeded {timeout}s timeout")
    if "error" in result:
        raise result["error"]
    return result["value"]


_CORRECTION_INSTRUCTION = (
    "\n\nIMPORTANT: your previous response was not valid JSON matching "
    "the required shape. Respond with ONLY the JSON object, no other text, "
    "no markdown code fences."
)


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
            raw = _call_with_timeout(generate_raw_fn, extra_instruction)
        except Exception as exc:
            ftype = classify_api_error(exc)
            attempts_log.append({"stage": "generate", "failure_type": ftype.value, "error": str(exc)})

            if ftype == FailureType.TRANSIENT and transient_retries < TRANSIENT_MAX_RETRIES:
                transient_retries += 1
                time.sleep(BACKOFF_BASE_SECONDS * (2 ** (transient_retries - 1)))
                continue
            if ftype == FailureType.MALFORMED_OUTPUT and malformed_retries < MALFORMED_MAX_RETRIES:
                # A provider that raises ValueError instead of returning bad
                # text (e.g. an empty/blocked response, see gemini_provider.
                # groq_provider) is the same "malformed output" case as bad
                # JSON -- it gets the same one corrective retry.
                malformed_retries += 1
                extra_instruction = _CORRECTION_INSTRUCTION
                continue

            # QUOTA_EXHAUSTED, UNKNOWN, GROUNDING_FAILURE, or budget-exhausted
            # TRANSIENT/MALFORMED_OUTPUT: fail this tier, caller escalates.
            return TierResult(
                tier=tier_name, success=False, retries_used=transient_retries + malformed_retries,
                failure_type=ftype, error=str(exc), attempts_log=attempts_log,
            )

        try:
            parsed = parse_fn(raw)
            grounded_result = ground_fn(parsed)
        except Exception as exc:
            # Covers both malformed JSON (parse_fn) and a shape parse_fn let
            # through that ground_fn can't work with -- an LLM returning an
            # array instead of an object, quote objects instead of strings,
            # etc. is the same "output doesn't match the required shape"
            # failure the corrective re-prompt exists for, so it shares the
            # malformed-output retry budget rather than crashing the chain.
            attempts_log.append({"stage": "parse_or_ground", "failure_type": FailureType.MALFORMED_OUTPUT.value, "error": str(exc)})
            if malformed_retries < MALFORMED_MAX_RETRIES:
                malformed_retries += 1
                extra_instruction = _CORRECTION_INSTRUCTION
                continue
            return TierResult(
                tier=tier_name, success=False, retries_used=transient_retries + malformed_retries,
                failure_type=FailureType.MALFORMED_OUTPUT, error=str(exc), attempts_log=attempts_log,
            )

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
