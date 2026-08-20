"""
Groq-specific raw generation call -- AI fallback tier (different provider
from Gemini, so a Gemini-side outage/quota issue doesn't take down both
tiers at once -- see PLAN.md "Fallback chain" reasoning).

Model name is env-overridable (GROQ_MODEL) rather than hardcoded with
confidence -- verify the default against `client.models.list()` once a
real API key is available; Groq's hosted model lineup changes over time
and this was picked from training knowledge, not a live check.
"""
import os

import groq

from .clause_extraction import build_prompt

DEFAULT_MODEL = "llama-3.3-70b-versatile"


def make_generate_fn(doc_text: str, client: groq.Groq):
    prompt = build_prompt(doc_text)
    model = os.environ.get("GROQ_MODEL", DEFAULT_MODEL)

    def generate(extra_instruction: str = "") -> str:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt + extra_instruction}],
        )
        return response.choices[0].message.content

    return generate
