"""
Step 4: Decision memo assembly. Per-clause structured result +
"X of Y clauses present" summary line -- no weighted score, no
Compliant/Flagged verdict (explicit non-goal, see PLAN.md).
"""
from .clause_definitions import CHECKLIST


def assemble_extraction_failure_memo(doc_title: str, reason: str) -> dict:
    """Text extraction never got far enough to run any tier -- e.g. a
    missing/corrupt file, or a scanned/image-only PDF that yields near-empty
    text pdfplumber can't do anything with. Distinct from a real "0 of 8
    clauses present" result: that means the tiers ran and found nothing;
    this means the tiers never got real document text to check."""
    return {
        "document": doc_title,
        "summary": "text extraction failed -- no clauses could be checked",
        "clauses": [],
        "extraction_failed": True,
        "extraction_failure_reason": reason,
    }


def assemble_memo(doc_title: str, compared_result: dict) -> dict:
    present_count = sum(1 for cat in CHECKLIST if compared_result[cat]["present"])
    clauses = []
    for cat in CHECKLIST:
        entry = compared_result[cat]
        clauses.append(
            {
                "category": cat,
                "present": entry["present"],
                "occurrence_count": entry["occurrence_count"],
                "quotes": [q["text"] for q in entry["quotes"] if q["grounded"]],
                "locations": [q["location"] for q in entry["quotes"] if q["grounded"]],
                "reference_comparison": entry["reference_comparison"],
                # NOTE: currently always False for a memo that reaches this
                # point. has_grounding_failure() fails the *whole tier* the
                # moment any category is llm_claimed_present-but-ungrounded
                # (retry_policy.run_llm_tier), so compared_result here is
                # always from a tier where that was true for zero
                # categories. Kept because it's part of the documented
                # per-category memo shape and would start firing if the
                # all-or-nothing tier-level escalation is ever changed to a
                # per-category one -- see DECISIONS.md.
                "llm_claimed_present_but_ungrounded": (
                    entry["llm_claimed_present"] and not entry["present"]
                ),
            }
        )
    return {
        "document": doc_title,
        "summary": f"{present_count} of {len(CHECKLIST)} checklist clauses present",
        "clauses": clauses,
    }


def format_memo_markdown(memo: dict) -> str:
    lines = [f"# Clause Review: {memo['document']}", "", f"**{memo['summary']}**", ""]
    if memo.get("extraction_failed"):
        lines.append(f"**EXTRACTION FAILED:** {memo['extraction_failure_reason']}")
        return "\n".join(lines)
    if memo.get("fallback_used"):
        # ASCII only -- a non-ASCII char here crashed the CLI on a Windows
        # cp1252 stdout, and only on this path (the happy-path memo has no
        # non-ASCII), so the pipeline survived every induced API failure and
        # then died rendering the warning about it.
        lines.append(
            f"**WARNING: fallback used** -- tier: `{memo['fallback_tier']}`, "
            f"retries spent: {memo['retries_used']}"
        )
        if memo["fallback_tier"] == "rule_based":
            # rule_based_fallback's "quotes" are fixed +-250-char context
            # windows around a keyword hit, not tightly extracted phrases
            # like the LLM tiers produce. reference_comparison.MATCH_THRESHOLD
            # was calibrated on LLM-length quotes, so a wider window
            # systematically scores lower against it -- "deviates from
            # standard" on this tier means something looser than it does on
            # gemini/groq. Not a bug to fix now (see reference_comparison.py
            # -- threshold itself is provisional, tuned in Phase 4); flagging
            # here so the verdict isn't read as equivalent across tiers.
            lines.append(
                "*(rule-based tier: reference-comparison verdicts below are less "
                "reliable -- quotes are wider context windows, not tightly "
                "extracted phrases)*"
            )
        lines.append("")
    for c in memo["clauses"]:
        status = "PRESENT" if c["present"] else "ABSENT"
        lines.append(f"## {c['category']} -- {status}")
        if c["llm_claimed_present_but_ungrounded"]:
            lines.append(
                "*(model claimed this clause was present but no quote could be "
                "verified against the source text -- treated as absent)*"
            )
        if c["present"]:
            for q in c["quotes"]:
                lines.append(f"> {q}")
            rc = c["reference_comparison"]
            if rc and rc["status"] != "no_reference":
                verdict = "Matches standard" if rc["status"] == "matches_standard" else "Deviates from standard"
                lines.append(f"\n*{verdict}* (similarity {rc['best_score']})")
        lines.append("")
    return "\n".join(lines)
