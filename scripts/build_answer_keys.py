"""
Build the dev-set and full-validation-set answer keys for the Distributor
Agreement clause-review pipeline, from CUAD's own lawyer-applied labels.

Ground truth construction is done directly (not delegated to OpenCode) per
project convention (DECISIONS.md, Workflow) -- this is what the pipeline's
accuracy is measured against, so it has to be built and understood first-hand.

Steps:
  1. Load CUADv1.json, filter to Distributor Agreement docs, drop the 2
     amendment-only riders (see DECISIONS.md, "Corpus Cleaning").
  2. For each doc, extract Present/Absent + quoted spans for the 8 checklist
     categories.
  3. Rank docs by checklist-clause richness and take a systematic stratified
     sample: every ~3rd doc (by rank) goes to the full-validation set, the
     rest to the dev set. This keeps both sets similarly distributed across
     "clause-rich" vs "clause-sparse" documents instead of risking an
     unlucky split.
  4. Write dev_set.json (20 docs) and full_validation_set.json (9 docs).
  5. Derive per-category reference clause text (most common phrasing) from
     the full clean 29-doc corpus, write reference_clauses.json.
"""
import json
import re
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parent.parent
CUAD_PATH = ROOT / "data" / "raw" / "extracted" / "CUADv1.json"
OUT_DIR = ROOT / "data" / "answer_keys"

CHECKLIST = [
    "Governing Law",
    "Non-Compete",
    "Termination For Convenience",
    "Cap On Liability",
    "Uncapped Liability",
    "Anti-Assignment",
    "Exclusivity",
    "License Grant",
]

# Amendment/addendum-only riders, not standalone contracts -- excluded from
# the corpus. Title-based filtering alone misses these (e.g. "Amendment
# No. 3 to the ... Distributor Agreement" is titled just "...Distributor
# Agreement" in CUAD's metadata) -- caught by scanning each doc's opening
# text for AMENDMENT/ADDENDUM language. See DECISIONS.md "Corpus Cleaning".
EXCLUDE_TITLES = {
    "NETGEAR,INC_04_21_2003-EX-10.16-AMENDMENT TO THE DISTRIBUTOR AGREEMENT BETWEEN INGRAM MICRO AND NETGEAR",
    "NEONSYSTEMSINC_03_01_1999-EX-10.5-DISTRIBUTOR AGREEMENT_Amendment",
    "ScansourceInc_20190509_10-Q_EX-10.2_11661422_EX-10.2_Distributor Agreement",  # Addendum
    "ScansourceInc_20190822_10-K_EX-10.39_11793959_EX-10.39_Distributor Agreement",  # Amendment No. 3
}


def category_of(question: str):
    m = re.search(r'related to "([^"]+)"', question)
    return m.group(1).strip() if m else None


def extract_doc_record(entry):
    title = entry["title"]
    para = entry["paragraphs"][0]
    by_category = {}
    for qa in para["qas"]:
        cat = category_of(qa["question"])
        if cat is None:
            continue
        answers = qa.get("answers", [])
        by_category[cat] = {
            "present": bool(answers),
            "spans": [
                {"text": a["text"], "start": a["answer_start"]} for a in answers
            ],
        }
    checklist_record = {c: by_category.get(c, {"present": False, "spans": []}) for c in CHECKLIST}
    richness = sum(1 for c in CHECKLIST if checklist_record[c]["present"])
    return {
        "title": title,
        "checklist": checklist_record,
        "richness": richness,
        "context": para["context"],
    }


def stratified_split(docs, n_validation):
    # docs assumed sorted by richness descending
    n = len(docs)
    validation_idx = {round(i * n / n_validation) for i in range(n_validation)}
    validation_idx = sorted(validation_idx)
    # guard against collisions from rounding
    i = 0
    seen = set()
    fixed = []
    for idx in validation_idx:
        while idx in seen and idx < n - 1:
            idx += 1
        seen.add(idx)
        fixed.append(idx)
    validation_set = {docs[i]["title"] for i in fixed}
    dev = [d for d in docs if d["title"] not in validation_set]
    validation = [d for d in docs if d["title"] in validation_set]
    return dev, validation


def word_set(text):
    return set(re.findall(r"[a-z0-9']+", text.lower()))


def jaccard(a, b):
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def most_representative_phrasing(docs, category, top_n=2, min_words=6):
    """Real contract clauses are essentially never verbatim-identical across
    different deals (checked: exact-match counting returned all-1s on this
    corpus). So "most common phrasing" is redefined as "most representative":
    the real clause text whose word-overlap (Jaccard) similarity to every
    other instance of the same category is highest on average -- a medoid,
    picked from actual corpus text, no invented or embedding-based text."""
    spans = []
    for d in docs:
        for span in d["checklist"][category]["spans"]:
            t = span["text"].strip()
            if len(t.split()) >= min_words:
                spans.append((d["title"], t))
    if len(spans) < 2:
        return [{"text": t, "source_doc": title, "avg_similarity": None} for title, t in spans]

    wordsets = [word_set(t) for _, t in spans]
    scores = []
    for i in range(len(spans)):
        sims = [jaccard(wordsets[i], wordsets[j]) for j in range(len(spans)) if j != i]
        scores.append(sum(sims) / len(sims))

    ranked = sorted(range(len(spans)), key=lambda i: -scores[i])
    return [
        {"text": spans[i][1], "source_doc": spans[i][0], "avg_similarity": round(scores[i], 3)}
        for i in ranked[:top_n]
    ]


def main():
    with open(CUAD_PATH, encoding="utf-8") as f:
        cuad = json.load(f)

    raw_docs = [e for e in cuad["data"] if "DISTRIBUTOR" in e["title"].upper()]
    docs = [extract_doc_record(e) for e in raw_docs if e["title"] not in EXCLUDE_TITLES]

    assert len(raw_docs) == 31, f"expected 31 raw title matches, got {len(raw_docs)}"
    assert len(docs) == 27, f"expected 27 clean docs, got {len(docs)}"

    docs.sort(key=lambda d: (-d["richness"], d["title"]))

    dev, validation = stratified_split(docs, n_validation=7)
    assert len(dev) == 20, f"expected 20 dev docs, got {len(dev)}"
    assert len(validation) == 7, f"expected 7 validation docs, got {len(validation)}"

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    def strip_for_output(d):
        return {"title": d["title"], "richness": d["richness"], "checklist": d["checklist"]}

    with open(OUT_DIR / "dev_set.json", "w", encoding="utf-8") as f:
        json.dump([strip_for_output(d) for d in dev], f, indent=2)

    with open(OUT_DIR / "full_validation_set.json", "w", encoding="utf-8") as f:
        json.dump([strip_for_output(d) for d in validation], f, indent=2)

    # Reference clause text derived from the FULL clean 29-doc corpus (not
    # just dev), most common phrasing per category.
    reference = {c: most_representative_phrasing(docs, c) for c in CHECKLIST}
    with open(OUT_DIR / "reference_clauses.json", "w", encoding="utf-8") as f:
        json.dump(reference, f, indent=2)

    # Full context text per doc, kept separately (larger, needed for spot-check
    # and later for feeding the pipeline test fixtures).
    contexts = {d["title"]: d["context"] for d in docs}
    with open(OUT_DIR / "doc_contexts.json", "w", encoding="utf-8") as f:
        json.dump(contexts, f, indent=2)

    print(f"dev set: {len(dev)} docs, richness range {min(d['richness'] for d in dev)}-{max(d['richness'] for d in dev)}")
    print(f"validation set: {len(validation)} docs, richness range {min(d['richness'] for d in validation)}-{max(d['richness'] for d in validation)}")
    print("validation titles:")
    for d in validation:
        print(f"  {d['richness']}/8  {d['title']}")


if __name__ == "__main__":
    main()
