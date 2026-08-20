"""
Mechanical aid for spot-checking ABSENT labels without needing legal
knowledge. For each doc in the spot-check packet, keyword-search the full
contract text for each ABSENT category's telltale words. If nothing turns
up, the absence needs no further reading. If something turns up, it's
flagged with a short snippet -- read just that one sentence and judge
whether it's actually the clause in question or an unrelated use of the
word (e.g. "exclusive" describing something other than distribution
rights). This narrows "read the whole contract" down to "read one flagged
sentence, if any."
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AK_DIR = ROOT / "data" / "answer_keys"

# Same PICKS as make_spot_check_packet.py
PICKS = [
    "SmartRxSystemsInc_20180914_1-A_EX1A-6 MAT CTRCT_11351705_EX1A-6 MAT CTRCT_Distributor Agreement",
    "LIMEENERGYCO_09_09_1999-EX-10-DISTRIBUTOR AGREEMENT",
    "ETELOS,INC_03_09_2004-EX-10.8-DISTRIBUTOR AGREEMENT",
    "ZogenixInc_20190509_10-Q_EX-10.2_11663313_EX-10.2_Distributor Agreement",
]

KEYWORDS = {
    "Governing Law": ["governed by", "governing law", "construed in accordance", "laws of the state",
                       "laws of", "jurisdiction of", "venue shall", "choice of law"],
    "Non-Compete": ["non-compete", "not compete", "competing product", "competitor", "shall not engage in",
                     "restraint of trade", "compete with", "not to sell", "not sell any product"],
    "Termination For Convenience": ["without cause", "for convenience", "either party may terminate",
                                      "terminate this agreement at any time", "upon written notice",
                                      "days notice", "days' notice", "days prior written notice"],
    "Cap On Liability": ["limitation of liability", "shall not exceed", "liable for any special",
                          "consequential damages", "aggregate liability", "maximum liability",
                          "in no event shall", "punitive damages", "incidental damages", "limit of liability"],
    "Uncapped Liability": ["gross negligence", "willful misconduct", "shall not apply to", "no limitation",
                            "fraud", "intentional misconduct", "unlimited liability", "shall not limit"],
    "Anti-Assignment": ["shall not assign", "may not assign", "without the prior written consent",
                         "assign this agreement", "delegate any duty", "transfer this agreement",
                         "not be assigned", "assignment of this agreement"],
    "Exclusivity": ["exclusive", "non-exclusive", "sole distributor", "only distributor", "sole and exclusive"],
    "License Grant": ["hereby grants", "grants to distributor", "grants distributor", "right to use",
                       "right to sell", "right to market", "authorized to sell", "license to"],
}


def snippet(text, idx, width=90):
    start = max(0, idx - width)
    end = min(len(text), idx + width)
    return text[start:end].replace("\n", " ").strip()


def main():
    with open(AK_DIR / "dev_set.json", encoding="utf-8") as f:
        dev = {d["title"]: d for d in json.load(f)}
    with open(AK_DIR / "doc_contexts.json", encoding="utf-8") as f:
        contexts = json.load(f)

    lines = ["# Absence Self-Check (mechanical aid, no legal knowledge needed)\n"]
    lines.append(
        "For every category marked ABSENT in the spot-check packet, this "
        "searches the full contract text for that category's telltale "
        "words. If nothing is listed under a category, the keyword search "
        "found nothing either -- the absence needs no further reading. If "
        "something IS listed, read just that one snippet and judge: is "
        "this actually describing the clause, or is it an unrelated use "
        "of the word? Nothing else in the document needs reading.\n"
    )

    for title in PICKS:
        d = dev[title]
        text = contexts[title]
        absent_cats = [c for c, rec in d["checklist"].items() if not rec["present"]]
        if not absent_cats:
            continue
        lines.append(f"\n---\n\n## {title}\n")
        any_flag = False
        for cat in absent_cats:
            hits = []
            seen_idx = set()
            for kw in KEYWORDS[cat]:
                for m in re.finditer(re.escape(kw), text, re.IGNORECASE):
                    if m.start() not in seen_idx:
                        seen_idx.add(m.start())
                        hits.append((kw, m.start()))
            if hits:
                any_flag = True
                lines.append(f"\n### {cat} -- ABSENT, but keyword hit(s) found, please check:\n")
                for kw, idx in hits[:6]:
                    lines.append(f"- matched \"{kw}\": ...{snippet(text, idx)}...")
                if len(hits) > 6:
                    lines.append(f"- (+{len(hits) - 6} more hit(s))")
        if not any_flag:
            lines.append("\nNo keyword hits for any ABSENT category -- nothing to check here.\n")

    out_path = AK_DIR / "absence_self_check.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
