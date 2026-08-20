#!/usr/bin/env python3
"""
CLI entry point for the Phase 2 pipeline: full retry + 3-tier fallback
chain (Gemini -> Groq -> rule-based).

Usage:
    python run_pipeline.py "data/pdfs/ZogenixInc_..._Distributor Agreement.pdf"

Requires GEMINI_API_KEY and GROQ_API_KEY set (in .env or the environment).
"""
import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv
from google import genai
import groq

sys.path.insert(0, str(Path(__file__).resolve().parent))
from src import fallback_pipeline, memo as memo_mod

ROOT = Path(__file__).resolve().parent
REFERENCE_CLAUSES_PATH = ROOT / "data" / "answer_keys" / "reference_clauses.json"


def main():
    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument("pdf_path", type=Path)
    parser.add_argument("--json", action="store_true", help="print raw JSON instead of markdown memo")
    args = parser.parse_args()

    gemini_client = genai.Client()
    groq_client = groq.Groq()

    result = fallback_pipeline.run(args.pdf_path, REFERENCE_CLAUSES_PATH, gemini_client, groq_client)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(memo_mod.format_memo_markdown(result))
        print(f"\n---\ntier attempts: {result['tier_attempts']}")


if __name__ == "__main__":
    main()
