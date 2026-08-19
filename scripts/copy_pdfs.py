"""
Copy the 27 clean-corpus Distributor Agreement PDFs from the full CUAD_v1
release (data/raw/cuad_full/, downloaded separately from Zenodo -- see
DECISIONS.md "PDF Sourcing") into data/pdfs/, and write a title->filename
manifest so the pipeline (Phase 1) can look up a doc's PDF by its CUAD
title.
"""
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CUAD_PATH = ROOT / "data" / "raw" / "extracted" / "CUADv1.json"
PDF_ROOT = ROOT / "data" / "raw" / "cuad_full" / "CUAD_v1" / "full_contract_pdf"
OUT_DIR = ROOT / "data" / "pdfs"

EXCLUDE_TITLES = {
    "NETGEAR,INC_04_21_2003-EX-10.16-AMENDMENT TO THE DISTRIBUTOR AGREEMENT BETWEEN INGRAM MICRO AND NETGEAR",
    "NEONSYSTEMSINC_03_01_1999-EX-10.5-DISTRIBUTOR AGREEMENT_Amendment",
    "ScansourceInc_20190509_10-Q_EX-10.2_11661422_EX-10.2_Distributor Agreement",
    "ScansourceInc_20190822_10-K_EX-10.39_11793959_EX-10.39_Distributor Agreement",
}


def norm(s):
    return re.sub(r"\s+", " ", s).strip().lower()


def main():
    with open(CUAD_PATH, encoding="utf-8") as f:
        cuad = json.load(f)

    titles = [
        e["title"] for e in cuad["data"]
        if "DISTRIBUTOR" in e["title"].upper() and e["title"] not in EXCLUDE_TITLES
    ]
    assert len(titles) == 27, f"expected 27 clean titles, got {len(titles)}"

    all_pdfs = list(PDF_ROOT.rglob("*.pdf"))
    by_stem = {}
    for p in all_pdfs:
        by_stem.setdefault(norm(p.stem), []).append(p)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {}
    missing = []
    for t in titles:
        matches = by_stem.get(norm(t), [])
        if not matches:
            missing.append(t)
            continue
        src = matches[0]
        safe_name = re.sub(r'[<>:"/\\|?*]', "_", t) + ".pdf"
        dst = OUT_DIR / safe_name
        shutil.copyfile(src, dst)
        manifest[t] = safe_name

    if missing:
        raise SystemExit(f"missing PDFs for: {missing}")

    with open(OUT_DIR / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"copied {len(manifest)} PDFs to {OUT_DIR}")


if __name__ == "__main__":
    main()
