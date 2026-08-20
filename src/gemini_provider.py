"""Gemini-specific raw generation call -- primary tier."""
from google import genai

from .clause_extraction import build_prompt

MODEL = "gemini-2.5-flash"


def make_generate_fn(doc_text: str, client: genai.Client):
    prompt = build_prompt(doc_text)

    def generate(extra_instruction: str = "") -> str:
        response = client.models.generate_content(model=MODEL, contents=prompt + extra_instruction)
        return response.text

    return generate
