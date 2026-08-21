"""
Groq-specific raw generation call -- AI fallback tier (different provider
from Gemini, so a Gemini-side outage/quota issue doesn't take down both
tiers at once -- see PLAN.md "Fallback chain" reasoning).

Model name is env-overridable (GROQ_MODEL). Verified against a live
`client.models.list()` call once the API key was available -- the first
guess (llama-3.3-70b-versatile, from training knowledge) turned out to be
stale and isn't in Groq's current lineup at all. Picked openai/gpt-oss-120b
instead: large, general-purpose, actually present in the live model list.
"""
import os

import groq

from .clause_extraction import build_prompt

DEFAULT_MODEL = "openai/gpt-oss-120b"


def make_generate_fn(doc_text: str, client: groq.Groq):
    prompt = build_prompt(doc_text)
    model = os.environ.get("GROQ_MODEL", DEFAULT_MODEL)

    def generate(extra_instruction: str = "") -> str:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt + extra_instruction}],
        )
        if not response.choices:
            raise ValueError("empty choices list from Groq")
        text = response.choices[0].message.content
        if not text:
            # Same empty-response case as gemini_provider -- not a network
            # failure, classify as MALFORMED_OUTPUT for the corrective retry.
            raise ValueError(
                f"empty response from Groq (finish_reason={response.choices[0].finish_reason})"
            )
        return text

    return generate
