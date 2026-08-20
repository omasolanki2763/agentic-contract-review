"""
Step 3: Reference comparison (deterministic, no LLM). Compares each
grounded quote against the Phase 0 corpus-derived reference clause text for
its category, via fuzzy string match (per PLAN.md -- no semantic/embedding
matching, that's an explicit non-goal).

Threshold is provisional -- picked to prove the shape works on the happy
path, to be tuned in Phase 4 against the dev-set accuracy metrics rather
than guessed once and left alone.
"""
import json
from pathlib import Path

from rapidfuzz import fuzz

MATCH_THRESHOLD = 45  # rapidfuzz token_sort_ratio score, 0-100 -- provisional


def load_reference_clauses(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def compare_to_reference(quote_text: str, category: str, reference: dict) -> dict:
    candidates = reference.get(category, [])
    if not candidates:
        return {"status": "no_reference", "best_score": None, "matched_against": None}

    best_score = -1.0
    best_ref = None
    for cand in candidates:
        score = fuzz.token_sort_ratio(quote_text, cand["text"])
        if score > best_score:
            best_score = score
            best_ref = cand["text"]

    status = "matches_standard" if best_score >= MATCH_THRESHOLD else "deviates_from_standard"
    return {"status": status, "best_score": round(best_score, 1), "matched_against": best_ref}


def compare_document(grounded_result: dict, reference: dict) -> dict:
    """Adds a reference-comparison verdict to each present category's best
    grounded quote (present categories only -- comparison is meaningless
    for an absent clause)."""
    out = {}
    for cat, entry in grounded_result.items():
        entry = dict(entry)
        if entry["present"]:
            best_quote = max(
                (q for q in entry["quotes"] if q["grounded"]),
                key=lambda q: q["score"],
            )
            entry["reference_comparison"] = compare_to_reference(
                best_quote["text"], cat, reference
            )
        else:
            entry["reference_comparison"] = None
        out[cat] = entry
    return out
