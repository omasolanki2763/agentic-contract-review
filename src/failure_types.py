"""
Classifies a failure from a Gemini/Groq API call into one of the 4 failure
types the retry policy distinguishes (PLAN.md, "Every Parameter, Value,
and Reason" table):

  - TRANSIENT: network/timeout/per-minute rate limit -- retry x2, backoff.
  - MALFORMED_OUTPUT: invalid JSON/schema -- retry x1 with corrective re-prompt.
  - GROUNDING_FAILURE: LLM claimed a clause present but no quote grounds --
    no retry, straight to next fallback tier (same prompt on the same doc
    tends to reproduce the same hallucination).
  - QUOTA_EXHAUSTED: daily quota (not per-minute) -- no retry, straight to
    fallback (waiting doesn't fix a quota that's finished for the day).

Distinguishing per-minute vs. daily-quota 429s is done by inspecting the
error message text for quota-scope wording, since neither SDK exposes a
clean typed distinction. This is a best-effort heuristic -- documented in
DECISIONS.md as something to refine once real quota errors are actually
observed in practice, rather than guessed from memory of API docs that may
be stale. The safe default (unmatched/unknown error) is UNKNOWN, which the
retry policy treats as non-retryable -- escalate to fallback rather than
risk retrying something that will never succeed.
"""
import json
from enum import Enum


class FailureType(Enum):
    TRANSIENT = "transient"
    MALFORMED_OUTPUT = "malformed_output"
    GROUNDING_FAILURE = "grounding_failure"
    QUOTA_EXHAUSTED = "quota_exhausted"
    UNKNOWN = "unknown"


_DAILY_QUOTA_MARKERS = ("per day", "daily", "perday", "requests per day")
_TRANSIENT_MARKERS = ("timeout", "timed out", "deadline exceeded", "connection",
                       "unavailable", "rate limit", "429", "resource_exhausted")


def classify_api_error(exc: Exception) -> FailureType:
    msg = str(exc).lower()
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)

    if status == 429 or "429" in msg or "resource_exhausted" in msg:
        if any(marker in msg for marker in _DAILY_QUOTA_MARKERS):
            return FailureType.QUOTA_EXHAUSTED
        return FailureType.TRANSIENT

    if any(marker in msg for marker in _TRANSIENT_MARKERS):
        return FailureType.TRANSIENT

    if isinstance(exc, (json.JSONDecodeError, ValueError, KeyError)):
        return FailureType.MALFORMED_OUTPUT

    return FailureType.UNKNOWN


def has_grounding_failure(grounded_result: dict) -> bool:
    """True if the LLM claimed at least one category present but zero of
    its quotes for that category actually grounded -- the hallucination
    case this whole check exists to catch."""
    return any(
        entry["llm_claimed_present"] and not entry["present"]
        for entry in grounded_result.values()
    )
