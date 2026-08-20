"""
Phase 1 pipeline: happy path only. No retries, no fallback, no tracing --
those are Phase 2 (failure handling) and Phase 3 (observability). This just
proves the shape works end to end: PDF -> extraction -> clause extraction
-> reference comparison -> memo.
"""
from pathlib import Path

from google import genai

from . import pdf_extraction, clause_extraction, reference_comparison, memo


def run(pdf_path: Path, reference_clauses_path: Path, client: genai.Client) -> dict:
    doc_text = pdf_extraction.extract_text(pdf_path)
    grounded = clause_extraction.extract_clauses(doc_text, client)
    reference = reference_comparison.load_reference_clauses(reference_clauses_path)
    compared = reference_comparison.compare_document(grounded, reference)
    return memo.assemble_memo(pdf_path.stem, compared)
