"""
Unit tests for retry_policy.run_llm_tier against the 4 failure types it's
supposed to handle differently (PLAN.md parameter table). Uses mocked
generate/parse/ground functions -- these failure modes (malformed JSON,
synthetic rate-limit) don't reproduce reliably on demand from a live API,
so they're tested the same way a real test suite would: deterministically,
via mocks, not by hoping the real API misbehaves on cue.

Run: python tests/test_retry_policy.py
"""
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.retry_policy import run_llm_tier, _call_with_timeout, TRANSIENT_MAX_RETRIES, MALFORMED_MAX_RETRIES
from src.failure_types import FailureType, classify_api_error


def fake_grounded_result(all_present=True):
    return {
        "Governing Law": {"present": all_present, "llm_claimed_present": True, "quotes": [], "occurrence_count": 1},
    }


def test_transient_retries_then_fails():
    """A 429 rate-limit error should retry TRANSIENT_MAX_RETRIES times with
    backoff, then fail the tier (caller escalates)."""
    call_count = {"n": 0}

    def flaky_generate(extra):
        call_count["n"] += 1
        raise Exception("429 rate limit exceeded, please retry")

    start = time.time()
    result = run_llm_tier("test", flaky_generate, lambda raw: {}, lambda parsed: {})
    elapsed = time.time() - start

    assert not result.success
    assert result.failure_type == FailureType.TRANSIENT
    assert call_count["n"] == TRANSIENT_MAX_RETRIES + 1, f"expected {TRANSIENT_MAX_RETRIES + 1} attempts, got {call_count['n']}"
    assert elapsed >= 2 + 4 - 0.5, f"expected exponential backoff (2s+4s), elapsed only {elapsed:.1f}s"
    print("test_transient_retries_then_fails: PASS")


def test_transient_succeeds_after_retry():
    """If the transient error clears within the retry budget, the tier
    should succeed, not needlessly keep retrying."""
    call_count = {"n": 0}

    def flaky_then_ok(extra):
        call_count["n"] += 1
        if call_count["n"] < 2:
            raise Exception("429 rate limit exceeded")
        return "ok"

    result = run_llm_tier(
        "test", flaky_then_ok, lambda raw: {"parsed": True},
        lambda parsed: fake_grounded_result(all_present=True),
    )
    assert result.success
    assert call_count["n"] == 2
    print("test_transient_succeeds_after_retry: PASS")


def test_malformed_output_retries_once_with_correction():
    """Bad JSON should trigger one corrective retry (with an extra
    instruction appended), not more."""
    seen_instructions = []

    def bad_json_generate(extra):
        seen_instructions.append(extra)
        return "not valid json {{{"

    def parse_fn(raw):
        import json
        return json.loads(raw)  # always raises on "not valid json {{{"

    result = run_llm_tier("test", bad_json_generate, parse_fn, lambda parsed: {})

    assert not result.success
    assert result.failure_type == FailureType.MALFORMED_OUTPUT
    assert len(seen_instructions) == MALFORMED_MAX_RETRIES + 1
    assert seen_instructions[0] == ""  # first attempt: no correction yet
    assert "IMPORTANT" in seen_instructions[1]  # retry: corrective instruction appended
    print("test_malformed_output_retries_once_with_correction: PASS")


def test_grounding_failure_no_retry():
    """A grounding failure (LLM claimed present, nothing grounded) should
    fail the tier immediately -- no retry, per PLAN.md reasoning (retrying
    the same prompt on the same doc reproduces the same hallucination)."""
    call_count = {"n": 0}

    def generate(extra):
        call_count["n"] += 1
        return "ok"

    def ground_fn(parsed):
        return {
            "Governing Law": {"present": False, "llm_claimed_present": True, "quotes": [], "occurrence_count": 0},
        }

    result = run_llm_tier("test", generate, lambda raw: {}, ground_fn)

    assert not result.success
    assert result.failure_type == FailureType.GROUNDING_FAILURE
    assert call_count["n"] == 1, "should not retry on grounding failure"
    print("test_grounding_failure_no_retry: PASS")


def test_quota_exhausted_no_retry():
    """Daily quota exhaustion should fail immediately -- no retry, waiting
    doesn't fix a quota that's finished for the day."""
    call_count = {"n": 0}

    def generate(extra):
        call_count["n"] += 1
        raise Exception("429 Resource has been exhausted (e.g. check quota). requests per day limit reached")

    result = run_llm_tier("test", generate, lambda raw: {}, lambda parsed: {})

    assert not result.success
    assert result.failure_type == FailureType.QUOTA_EXHAUSTED
    assert call_count["n"] == 1, "should not retry on daily quota exhaustion"
    print("test_quota_exhausted_no_retry: PASS")


def test_ground_fn_exception_retries_then_fails_as_malformed():
    """A parse_fn/ground_fn that raises something other than ValueError/
    KeyError (e.g. AttributeError from an LLM returning the wrong JSON
    *shape* -- an array instead of an object, a bare bool) must not crash
    the whole tier. Found by code review, not by these tests originally --
    the parse-stage except clause used to only catch (ValueError, KeyError)
    and ground_fn wasn't wrapped at all."""
    call_count = {"n": 0}

    def generate(extra):
        call_count["n"] += 1
        return "ok"

    def parse_fn(raw):
        return {"Governing Law": {"present": True, "quotes": []}}  # valid JSON, wrong shape below

    def ground_fn(parsed):
        raise AttributeError("simulates 'list' object has no attribute 'get'")

    result = run_llm_tier("test", generate, parse_fn, ground_fn)

    assert not result.success
    assert result.failure_type == FailureType.MALFORMED_OUTPUT
    assert call_count["n"] == MALFORMED_MAX_RETRIES + 1, "should get the same 1 corrective retry as bad JSON"
    print("test_ground_fn_exception_retries_then_fails_as_malformed: PASS")


def test_generate_stage_malformed_output_gets_corrective_retry():
    """classify_api_error already labels some provider-raised ValueErrors
    MALFORMED_OUTPUT (e.g. gemini_provider/groq_provider raising ValueError
    on an empty/blocked response) -- the generate-stage except block used to
    only ever retry TRANSIENT, so this got zero of its documented 1 retry."""
    seen_instructions = []

    def flaky_then_ok(extra):
        seen_instructions.append(extra)
        if len(seen_instructions) < 2:
            raise ValueError("empty response from provider (finish_reason=SAFETY)")
        return "ok"

    result = run_llm_tier(
        "test", flaky_then_ok, lambda raw: {"parsed": True},
        lambda parsed: fake_grounded_result(all_present=True),
    )
    assert result.success
    assert len(seen_instructions) == 2
    assert seen_instructions[0] == ""
    assert "IMPORTANT" in seen_instructions[1]
    print("test_generate_stage_malformed_output_gets_corrective_retry: PASS")


def test_call_with_timeout_raises_without_blocking_process_exit():
    """_call_with_timeout must give up and raise TimeoutError on a call that
    never returns, without leaving anything that blocks process exit. (The
    original ThreadPoolExecutor-based version left a non-daemon worker
    thread running past the timeout; concurrent.futures' atexit handler
    joins those, which could hang the whole CLI at shutdown on a genuinely
    stuck API call.) A daemon thread can't be waited on the same way, so if
    this test process exits normally afterward, the fix holds."""
    import threading

    def hangs_forever(extra):
        import time
        time.sleep(120)

    try:
        _call_with_timeout(hangs_forever, "", timeout=0.3)
        assert False, "expected TimeoutError"
    except TimeoutError:
        pass

    # The abandoned worker is still alive (daemon, sleeping) but must not be
    # a non-daemon thread that would block interpreter shutdown.
    leaked = [t for t in threading.enumerate() if t is not threading.main_thread() and not t.daemon]
    assert not leaked, f"non-daemon leaked thread(s) would block process exit: {leaked}"
    print("test_call_with_timeout_raises_without_blocking_process_exit: PASS")


if __name__ == "__main__":
    test_grounding_failure_no_retry()
    test_quota_exhausted_no_retry()
    test_malformed_output_retries_once_with_correction()
    test_ground_fn_exception_retries_then_fails_as_malformed()
    test_generate_stage_malformed_output_gets_corrective_retry()
    test_call_with_timeout_raises_without_blocking_process_exit()
    test_transient_succeeds_after_retry()
    test_transient_retries_then_fails()  # slowest (real backoff sleeps), run last
    print("\nall retry_policy tests passed")
