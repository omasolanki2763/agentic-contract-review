"""
Phase 2 pipeline: full failure-handling + fallback chain, per PLAN.md.

Chain: Gemini (retry per failure type) -> Groq (same retry policy, different
provider) -> rule-based (deterministic, always succeeds). Every memo is
tagged with which tier actually produced the result and how many retries
were spent getting there, so a fallback-derived result is never silently
indistinguishable from a clean Gemini-tier result.
"""
import json
from pathlib import Path
from typing import Optional

from google import genai
import groq

from . import pdf_extraction, clause_extraction, gemini_provider, groq_provider
from . import rule_based_fallback, reference_comparison, memo as memo_mod
from .failure_types import FailureType
from .retry_policy import TierResult, run_llm_tier

# Below this many extracted characters, treat the PDF as unreadable rather
# than as a genuinely clause-free document -- a scanned/image-only PDF
# yields near-empty text from pdfplumber (no OCR, per pdf_extraction.py)
# and would otherwise sail through all 3 tiers reporting a confident
# "0 of 8 clauses present" with no indication the document was never
# actually read. Threshold: shortest clean doc in the dev/validation
# corpus is several thousand chars (see data/answer_keys); 500 is well
# below any real (even short) Distributor Agreement.
MIN_EXTRACTED_CHARS = 500


def _skipped_tier(tier_name: str) -> TierResult:
    """No client for this tier (e.g. its API key was missing/invalid at
    startup, see run_pipeline._make_*_client) -- record it as a failed
    attempt with no retries spent, same as any other tier failure, rather
    than silently omitting it from tier_attempts."""
    return TierResult(
        tier=tier_name, success=False, failure_type=FailureType.UNKNOWN,
        error="tier skipped: no client available (see startup warnings)",
    )


def _run_llm_chain(
    doc_text: str, gemini_client: Optional[genai.Client], groq_client: Optional[groq.Groq]
) -> dict:
    tiers_tried = []
    ground_fn = lambda parsed: clause_extraction.ground_quotes(doc_text, parsed)

    if gemini_client is not None:
        gen_fn = gemini_provider.make_generate_fn(doc_text, gemini_client)
        result = run_llm_tier("gemini", gen_fn, clause_extraction.parse_json_response, ground_fn)
        tiers_tried.append(result)
        if result.success:
            return {"grounded_result": result.grounded_result, "fallback_tier": "gemini", "tiers_tried": tiers_tried}
    else:
        tiers_tried.append(_skipped_tier("gemini"))

    if groq_client is not None:
        gen_fn = groq_provider.make_generate_fn(doc_text, groq_client)
        result = run_llm_tier("groq", gen_fn, clause_extraction.parse_json_response, ground_fn)
        tiers_tried.append(result)
        if result.success:
            return {"grounded_result": result.grounded_result, "fallback_tier": "groq", "tiers_tried": tiers_tried}
    else:
        tiers_tried.append(_skipped_tier("groq"))

    # Rule-based: deterministic, no API, always succeeds -- last resort.
    grounded_result = rule_based_fallback.extract_clauses(doc_text)
    return {"grounded_result": grounded_result, "fallback_tier": "rule_based", "tiers_tried": tiers_tried}


def run(
    pdf_path: Path,
    reference_clauses_path: Path,
    gemini_client: Optional[genai.Client],
    groq_client: Optional[groq.Groq],
) -> dict:
    try:
        doc_text = pdf_extraction.extract_text(pdf_path)
    except Exception as exc:
        return memo_mod.assemble_extraction_failure_memo(
            pdf_path.stem, f"PDF text extraction raised {type(exc).__name__}: {exc}"
        )

    if len(doc_text.strip()) < MIN_EXTRACTED_CHARS:
        return memo_mod.assemble_extraction_failure_memo(
            pdf_path.stem,
            f"only {len(doc_text.strip())} chars extracted (minimum {MIN_EXTRACTED_CHARS}) "
            "-- likely a scanned/image-only PDF, empty file, or corrupt PDF, not a "
            "contract that genuinely has zero checklist clauses",
        )

    chain_result = _run_llm_chain(doc_text, gemini_client, groq_client)

    reference = reference_comparison.load_reference_clauses(reference_clauses_path)
    compared = reference_comparison.compare_document(chain_result["grounded_result"], reference)
    result = memo_mod.assemble_memo(pdf_path.stem, compared)

    result["fallback_tier"] = chain_result["fallback_tier"]
    result["fallback_used"] = chain_result["fallback_tier"] != "gemini"
    result["retries_used"] = sum(t.retries_used for t in chain_result["tiers_tried"])
    result["tier_attempts"] = [
        {"tier": t.tier, "success": t.success, "retries_used": t.retries_used,
         "failure_type": t.failure_type.value if t.failure_type else None,
         "error": t.error, "attempts_log": t.attempts_log}
        for t in chain_result["tiers_tried"]
    ]
    return result
