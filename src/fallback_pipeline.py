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

from google import genai
import groq

from . import pdf_extraction, clause_extraction, gemini_provider, groq_provider
from . import rule_based_fallback, reference_comparison, memo as memo_mod
from .retry_policy import run_llm_tier


def _run_llm_chain(doc_text: str, gemini_client: genai.Client, groq_client: groq.Groq) -> dict:
    tiers_tried = []

    gen_fn = gemini_provider.make_generate_fn(doc_text, gemini_client)
    ground_fn = lambda parsed: clause_extraction.ground_quotes(doc_text, parsed)
    result = run_llm_tier("gemini", gen_fn, clause_extraction.parse_json_response, ground_fn)
    tiers_tried.append(result)
    if result.success:
        return {"grounded_result": result.grounded_result, "fallback_tier": "gemini", "tiers_tried": tiers_tried}

    gen_fn = groq_provider.make_generate_fn(doc_text, groq_client)
    result = run_llm_tier("groq", gen_fn, clause_extraction.parse_json_response, ground_fn)
    tiers_tried.append(result)
    if result.success:
        return {"grounded_result": result.grounded_result, "fallback_tier": "groq", "tiers_tried": tiers_tried}

    # Rule-based: deterministic, no API, always succeeds -- last resort.
    grounded_result = rule_based_fallback.extract_clauses(doc_text)
    return {"grounded_result": grounded_result, "fallback_tier": "rule_based", "tiers_tried": tiers_tried}


def run(
    pdf_path: Path,
    reference_clauses_path: Path,
    gemini_client: genai.Client,
    groq_client: groq.Groq,
) -> dict:
    doc_text = pdf_extraction.extract_text(pdf_path)

    chain_result = _run_llm_chain(doc_text, gemini_client, groq_client)

    reference = reference_comparison.load_reference_clauses(reference_clauses_path)
    compared = reference_comparison.compare_document(chain_result["grounded_result"], reference)
    result = memo_mod.assemble_memo(pdf_path.stem, compared)

    result["fallback_tier"] = chain_result["fallback_tier"]
    result["fallback_used"] = chain_result["fallback_tier"] != "gemini"
    result["retries_used"] = sum(t.retries_used for t in chain_result["tiers_tried"])
    result["tier_attempts"] = [
        {"tier": t.tier, "success": t.success, "retries_used": t.retries_used,
         "failure_type": t.failure_type.value if t.failure_type else None}
        for t in chain_result["tiers_tried"]
    ]
    return result
