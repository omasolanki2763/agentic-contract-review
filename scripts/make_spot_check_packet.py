"""
Build a human-readable spot-check packet: full contract text + checklist
labels, for a hand-picked spread of dev-set docs (clause-rich to
clause-empty), so the labels can be personally verified against source
text. This is the Phase 0 defensibility step -- see PLAN.md, "Ground-Truth
Labelling Protocol", step 3.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AK_DIR = ROOT / "data" / "answer_keys"

PICKS = [
    "ZogenixInc_20190509_10-Q_EX-10.2_11663313_EX-10.2_Distributor Agreement",  # 8/8, clause-rich
    "LIMEENERGYCO_09_09_1999-EX-10-DISTRIBUTOR AGREEMENT",  # 4/8, mid
    "OPTIMIZEDTRANSPORTATIONMANAGEMENT,INC_07_26_2000-EX-6.6-DISTRIBUTOR AGREEMENT",  # 3/8, mid-low
    "ScansourceInc_20190822_10-K_EX-10.39_11793959_EX-10.39_Distributor Agreement",  # 0/8, clause-empty
]


def main():
    with open(AK_DIR / "dev_set.json", encoding="utf-8") as f:
        dev = {d["title"]: d for d in json.load(f)}
    with open(AK_DIR / "doc_contexts.json", encoding="utf-8") as f:
        contexts = json.load(f)

    lines = ["# Phase 0 Spot-Check Packet\n"]
    lines.append(
        "Read each document's full text below, then check every checklist "
        "label against it. The goal isn't auditing CUAD's legal correctness "
        "(trust the lawyers) -- it's personally understanding *why* each "
        "label is what it is, so it can be explained live under interviewer "
        "questioning.\n"
    )

    for title in PICKS:
        d = dev[title]
        lines.append(f"\n---\n\n## {title}\n")
        lines.append(f"Richness: {d['richness']}/8 checklist categories present\n")
        lines.append("### Checklist labels\n")
        for cat, rec in d["checklist"].items():
            if rec["present"]:
                lines.append(f"- **{cat}: PRESENT**")
                for span in rec["spans"]:
                    lines.append(f"  - quoted: \"{span['text'].strip()}\"")
            else:
                lines.append(f"- **{cat}: ABSENT**")
        lines.append("\n### Full contract text\n")
        lines.append("```")
        lines.append(contexts[title])
        lines.append("```")

    out_path = AK_DIR / "spot_check_packet.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
