"""
Step 2: Clause extraction (LLM: Gemini primary) + grounding check.

Phase 1 = happy path only -- one Gemini call, no retry, no fallback tier
(Groq / rule-based fallback is Phase 2, see PLAN.md "Failure handling").

Grounding check: every quote the LLM returns is verified to actually exist
in the extracted document text (fuzzy match, tolerant of whitespace/
formatting noise per PLAN.md's grounding-check design). A quote that
doesn't ground is flagged, not silently trusted -- this is what catches
hallucination.
"""
import json
import re

from google import genai
from rapidfuzz import fuzz

from .clause_definitions import CHECKLIST, DEFINITIONS

MODEL = "gemini-2.5-flash"
GROUNDING_THRESHOLD = 85  # rapidfuzz partial_ratio score, 0-100


def build_prompt(doc_text: str) -> str:
    checklist_block = "\n".join(
        f'- "{cat}": {DEFINITIONS[cat]}' for cat in CHECKLIST
    )
    return f"""You are reviewing a Distributor Agreement contract. For each of
the following 8 clause categories, determine whether the contract contains
that clause, and if so, extract the exact verbatim quote(s) from the
contract text below -- copy the text exactly as written, do not paraphrase
or summarize.

Categories:
{checklist_block}

Respond with ONLY a JSON object, no other text, in this exact shape:
{{
  "Governing Law": {{"present": true, "quotes": ["exact quote 1"]}},
  "Non-Compete": {{"present": false, "quotes": []}},
  ...
}}

Include all 8 categories as keys. If present is false, quotes must be an
empty list. Quotes must be copied verbatim from the contract text -- exact
substrings, not paraphrases.

Contract text:
---
{doc_text}
---
"""


def _parse_json_response(raw: str) -> dict:
    raw = raw.strip()
    # Gemini sometimes wraps JSON in a markdown code fence despite instructions.
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw, re.DOTALL)
    if m:
        raw = m.group(1)
    return json.loads(raw)


def call_gemini(doc_text: str, client: genai.Client) -> dict:
    prompt = build_prompt(doc_text)
    response = client.models.generate_content(model=MODEL, contents=prompt)
    return _parse_json_response(response.text)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def ground_quotes(doc_text: str, raw_result: dict) -> dict:
    """For every category/quote in raw_result, verify the quote actually
    exists in doc_text. Returns the same shape with each quote replaced by
    a dict: {text, grounded, score, location}."""
    doc_norm = _normalize(doc_text)
    grounded_result = {}

    for cat in CHECKLIST:
        entry = raw_result.get(cat, {"present": False, "quotes": []})
        present = bool(entry.get("present"))
        quotes = entry.get("quotes", []) or []

        grounded_quotes = []
        for q in quotes:
            q_norm = _normalize(q)
            idx = doc_norm.find(q_norm)
            if idx != -1:
                grounded_quotes.append(
                    {"text": q, "grounded": True, "score": 100, "location": idx}
                )
            else:
                score = fuzz.partial_ratio(q_norm, doc_norm)
                grounded_quotes.append(
                    {
                        "text": q,
                        "grounded": score >= GROUNDING_THRESHOLD,
                        "score": round(score, 1),
                        "location": None,
                    }
                )

        # A category only counts as genuinely "present" if at least one
        # quote actually grounds -- an LLM claiming presence with zero
        # grounded quotes is exactly the hallucination case this check
        # exists to catch.
        any_grounded = any(gq["grounded"] for gq in grounded_quotes)
        grounded_result[cat] = {
            "present": present and any_grounded,
            "llm_claimed_present": present,
            "quotes": grounded_quotes,
            "occurrence_count": sum(1 for gq in grounded_quotes if gq["grounded"]),
        }

    return grounded_result


def extract_clauses(doc_text: str, client: genai.Client) -> dict:
    raw = call_gemini(doc_text, client)
    return ground_quotes(doc_text, raw)
