"""
Step 4: Decision memo assembly. Per-clause structured result +
"X of Y clauses present" summary line -- no weighted score, no
Compliant/Flagged verdict (explicit non-goal, see PLAN.md).
"""
from .clause_definitions import CHECKLIST


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
    if memo.get("fallback_used"):
        lines.append(
            f"**⚠ fallback used** -- tier: `{memo['fallback_tier']}`, "
            f"retries spent: {memo['retries_used']}"
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
