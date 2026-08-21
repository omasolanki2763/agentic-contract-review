"""Gemini-specific raw generation call -- primary tier."""
from google import genai

from .clause_extraction import build_prompt

MODEL = "gemini-2.5-flash"


def make_generate_fn(doc_text: str, client: genai.Client):
    prompt = build_prompt(doc_text)

    def generate(extra_instruction: str = "") -> str:
        response = client.models.generate_content(model=MODEL, contents=prompt + extra_instruction)
        text = response.text
        if not text:
            # response.text is None whenever there's no usable candidate
            # text (safety block, or MAX_TOKENS reached with only "thought"
            # parts) -- an empty/no-op response, not a network failure.
            # Raising ValueError classifies it as MALFORMED_OUTPUT so it
            # gets the documented corrective retry instead of crashing the
            # chain on `.strip()`/`.find()` downstream.
            raise ValueError(f"empty response from Gemini (finish_reason={_finish_reason(response)})")
        return text

    return generate


def _finish_reason(response):
    try:
        return response.candidates[0].finish_reason
    except (AttributeError, IndexError, TypeError):
        return "unknown"
