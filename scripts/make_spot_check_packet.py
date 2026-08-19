"""
Build a human-readable spot-check packet: checklist labels + the relevant
quoted excerpt (not the full raw contract, which is overwhelming for a
first read), plus a plain-English definition of each clause type, for a
hand-picked spread of dev-set docs (clause-empty to clause-rich, in that
reading order). This is the Phase 0 defensibility step -- see PLAN.md,
"Ground-Truth Labelling Protocol", step 3.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AK_DIR = ROOT / "data" / "answer_keys"

# Easiest doc first, hardest last -- build up instead of starting with the
# most clause-dense contract. (Corpus floor is now 3/8, not 0/8 -- the two
# 0-1/8 outliers from the first pass turned out to be missed amendment
# riders, not genuinely clause-empty agreements. See DECISIONS.md.)
PICKS = [
    "SmartRxSystemsInc_20180914_1-A_EX1A-6 MAT CTRCT_11351705_EX1A-6 MAT CTRCT_Distributor Agreement",  # 3/8, lowest in corpus
    "LIMEENERGYCO_09_09_1999-EX-10-DISTRIBUTOR AGREEMENT",  # 4/8, mid
    "ETELOS,INC_03_09_2004-EX-10.8-DISTRIBUTOR AGREEMENT",  # 6/8, mid-high
    "ZogenixInc_20190509_10-Q_EX-10.2_11663313_EX-10.2_Distributor Agreement",  # 8/8, clause-rich
]

DEFINITIONS = {
    "Governing Law": (
        "Which state/country's law applies if there's a dispute -- e.g. \"this "
        "contract is interpreted under Texas law.\" Almost every contract has "
        "one; it's boilerplate, not a negotiated risk point."
    ),
    "Non-Compete": (
        "Restricts the distributor from selling competing products (or the "
        "supplier from using a competing distributor) during or after the "
        "contract. Look for words like \"shall not sell/promote/deal in "
        "competing products.\""
    ),
    "Termination For Convenience": (
        "Either side can end the contract without needing a reason -- just "
        "advance written notice (e.g. \"either party may terminate upon 90 "
        "days written notice\"). Contrast with termination \"for cause\" "
        "(breach), which is a different, more common clause."
    ),
    "Cap On Liability": (
        "Limits how much one party can be forced to pay the other in damages "
        "-- e.g. \"liability shall not exceed the fees paid in the prior 12 "
        "months\" or a flat exclusion of \"special, incidental, or "
        "consequential damages.\""
    ),
    "Uncapped Liability": (
        "A carve-out from the liability cap above -- specific situations "
        "(IP infringement, confidentiality breach, gross negligence, "
        "indemnification) where the normal cap doesn't apply and liability "
        "is unlimited. Rarer than a plain cap -- most contracts either have "
        "no cap language at all, or a cap with no carve-out."
    ),
    "Anti-Assignment": (
        "Restricts either party from transferring/assigning the contract "
        "(or their rights under it) to someone else without the other "
        "party's consent -- e.g. on a merger or sale of the business."
    ),
    "Exclusivity": (
        "The distributor is the *only* one allowed to sell in a given "
        "territory (or the supplier will only sell through this "
        "distributor). Look for the word \"exclusive\" attached to "
        "territory/product rights -- absence usually means the relationship "
        "is non-exclusive (supplier can appoint other distributors too)."
    ),
    "License Grant": (
        "The actual clause where the supplier gives the distributor the "
        "right to use/sell/market the product (and often the trademark). "
        "This is usually the contract's core operative clause -- look for "
        "\"hereby grants ... the right to market, distribute, and sell.\""
    ),
}


def main():
    with open(AK_DIR / "dev_set.json", encoding="utf-8") as f:
        dev = {d["title"]: d for d in json.load(f)}

    lines = ["# Phase 0 Spot-Check Packet\n"]
    lines.append(
        "For each doc: what each clause type means in plain English, then "
        "the exact quoted excerpt the label points to (not the whole "
        "contract -- that's in `doc_contexts.json` if you want to see a "
        "quote in its full surrounding text). Ordered easiest to hardest. "
        "Goal: be able to say *why* each label is right, not just that it "
        "matches CUAD.\n"
    )

    for title in PICKS:
        d = dev[title]
        lines.append(f"\n---\n\n## {title}\n")
        lines.append(f"**{d['richness']}/8 checklist categories present**\n")
        for cat, rec in d["checklist"].items():
            lines.append(f"\n### {cat}")
            lines.append(f"*{DEFINITIONS[cat]}*\n")
            if rec["present"]:
                lines.append(f"**PRESENT** -- {len(rec['spans'])} quoted span(s) found:\n")
                for span in rec["spans"][:3]:
                    lines.append(f"> {span['text'].strip()}\n")
                if len(rec["spans"]) > 3:
                    lines.append(f"*(+{len(rec['spans']) - 3} more span(s), not shown)*\n")
            else:
                lines.append("**ABSENT** -- no matching text found in this contract.\n")

    out_path = AK_DIR / "spot_check_packet.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
