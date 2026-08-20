"""
Step 1: PDF text extraction. Phase 1 = happy path only -- pdfplumber, no
failure heuristic, no OCR/LLM fallback (that's Phase 2, see PLAN.md
"Failure handling / fallback chain").
"""
from pathlib import Path

import pdfplumber


def extract_text(pdf_path: Path) -> str:
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            pages.append(text)
    return "\n".join(pages)
