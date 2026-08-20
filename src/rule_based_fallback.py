"""
Rule-based fallback tier (last resort, no API call, near-zero failure
surface -- guarantees the pipeline never returns nothing, per PLAN.md
"Failure handling / fallback chain"). Deterministic keyword search per
category; if a telltale phrase is found, the sentence containing it is
extracted as the "quote". Reuses the keyword lists validated in Phase 0's
`self_check_absent.py` self-check (those were checked against real
contract text and shown to correctly discriminate the 4 spot-checked
docs), but here they DRIVE extraction instead of just flagging.

This tier is expected to be noisier than the LLM tiers -- it has no
semantic understanding (e.g. it can't tell "exclusive" from
"non-exclusive" the way a human/LLM reading the sentence can... actually
it can, see the negation guard below, added after Phase 0's spot-check
found that exact false-positive pattern). It exists purely so the
pipeline always produces *something*, not to be accurate.
"""
import re

from .clause_definitions import CHECKLIST

KEYWORDS = {
    "Governing Law": ["governed by", "governing law", "construed in accordance", "laws of the state",
                       "laws of", "jurisdiction of", "venue shall", "choice of law"],
    "Non-Compete": ["non-compete", "not compete", "competing product", "competitive product", "competitor",
                     "shall not engage in", "restraint of trade", "compete with", "not to sell",
                     "not sell any product", "not carry any competitive", "not carry any competing"],
    "Termination For Convenience": ["without cause", "for convenience", "either party may terminate",
                                      "terminate this agreement at any time"],
    "Cap On Liability": ["limitation of liability", "shall not exceed", "liable for any special",
                          "consequential damages", "aggregate liability", "maximum liability",
                          "in no event shall", "punitive damages", "incidental damages", "limit of liability"],
    "Uncapped Liability": ["gross negligence", "willful misconduct", "unlimited liability"],
    "Anti-Assignment": ["shall not assign", "may not assign", "assign this agreement",
                         "delegate any duty", "not be assigned", "not assignable", "assignable by"],
    "Exclusivity": ["exclusive distributor", "exclusive right", "sole distributor", "sole and exclusive"],
    "License Grant": ["hereby grants", "grants to distributor", "grants distributor", "license to use"],
}

# Keyword hits within a few words of a negation are almost always the
# opposite of what they look like ("non-exclusive" contains "exclusive").
# Caught during Phase 0 spot-checking (DECISIONS.md, "Ground Truth --
# Spot-Check Result") -- 6 false-positive "exclusive" hits on one doc were
# all actually "non-exclusive". This guard is scoped to Exclusivity only --
# applying it to every category is wrong, because for several categories
# (Anti-Assignment: "not assignable"; Non-Compete: "shall not compete")
# the negation word IS the clause, not a false trigger. Caught while
# testing this fallback tier: "assignable by" matched inside "is not
# assignable by Distributor" and the guard was about to wrongly suppress
# a correct hit.
NEGATION_WINDOW = 8
NEGATIONS = {"non", "not", "no", "without"}
NEGATION_GUARDED_CATEGORIES = {"Exclusivity"}


def _is_negated(text: str, match_start: int) -> bool:
    before = text[max(0, match_start - 40):match_start]
    words = re.findall(r"[a-z']+", before.lower())
    return any(w in NEGATIONS for w in words[-NEGATION_WINDOW:])


def _extract_sentence(text: str, idx: int, window: int = 250) -> str:
    start = max(0, idx - window)
    end = min(len(text), idx + window)
    snippet = text[start:end]
    return re.sub(r"\s+", " ", snippet).strip()


def extract_clauses(doc_text: str) -> dict:
    result = {}
    for cat in CHECKLIST:
        hits = []
        seen_starts = set()
        for kw in KEYWORDS[cat]:
            for m in re.finditer(re.escape(kw), doc_text, re.IGNORECASE):
                if cat in NEGATION_GUARDED_CATEGORIES and _is_negated(doc_text, m.start()):
                    continue
                # dedupe hits that land in roughly the same spot
                if any(abs(m.start() - s) < 100 for s in seen_starts):
                    continue
                seen_starts.add(m.start())
                hits.append(m.start())

        quotes = [
            {"text": _extract_sentence(doc_text, idx), "grounded": True, "score": 100, "location": idx}
            for idx in hits
        ]
        result[cat] = {
            "present": len(quotes) > 0,
            "llm_claimed_present": len(quotes) > 0,
            "quotes": quotes,
            "occurrence_count": len(quotes),
        }
    return result
