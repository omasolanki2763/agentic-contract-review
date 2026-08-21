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
from google.genai import types as genai_types
import groq

sys.path.insert(0, str(Path(__file__).resolve().parent))
from src import fallback_pipeline, memo as memo_mod
from src.retry_policy import CALL_TIMEOUT_SECONDS

ROOT = Path(__file__).resolve().parent
REFERENCE_CLAUSES_PATH = ROOT / "data" / "answer_keys" / "reference_clauses.json"

# Set slightly under retry_policy's CALL_TIMEOUT_SECONDS so the provider's
# own timeout fires first (a real HTTP-level abort) and the thread-join
# backstop in retry_policy only has to catch whatever slips past it.
_PROVIDER_TIMEOUT_SECONDS = CALL_TIMEOUT_SECONDS - 4


def _make_gemini_client():
    """None on failure (e.g. missing GEMINI_API_KEY) rather than raising --
    a missing key is a legitimate "this tier is unavailable, escalate"
    case, not a reason to crash before the fallback chain even starts."""
    try:
        return genai.Client(
            http_options=genai_types.HttpOptions(timeout=_PROVIDER_TIMEOUT_SECONDS * 1000)
        )
    except Exception as exc:
        print(f"warning: could not create Gemini client ({exc}) -- gemini tier will be skipped", file=sys.stderr)
        return None


def _make_groq_client():
    try:
        return groq.Groq(
            timeout=_PROVIDER_TIMEOUT_SECONDS,
            # This tier owns its own retry policy (retry_policy.run_llm_tier);
            # the SDK's own default (2 hidden retries) would otherwise stack
            # extra HTTP requests per attempt and make the 62s wrapper
            # timeout race the SDK's own retry loop instead of one clean call.
            max_retries=0,
        )
    except Exception as exc:
        print(f"warning: could not create Groq client ({exc}) -- groq tier will be skipped", file=sys.stderr)
        return None


def main():
    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument("pdf_path", type=Path)
    parser.add_argument("--json", action="store_true", help="print raw JSON instead of markdown memo")
    args = parser.parse_args()

    gemini_client = _make_gemini_client()
    groq_client = _make_groq_client()

    result = fallback_pipeline.run(args.pdf_path, REFERENCE_CLAUSES_PATH, gemini_client, groq_client)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(memo_mod.format_memo_markdown(result))
        if "tier_attempts" in result:
            print(f"\n---\ntier attempts: {result['tier_attempts']}")


if __name__ == "__main__":
    main()
