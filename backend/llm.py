"""LLM helper for chat model generation."""

from __future__ import annotations

import os

from openai import OpenAI

_API_KEY = os.getenv("OPENAI_API_KEY")
if not _API_KEY:
    raise RuntimeError("OPENAI_API_KEY not set")

client = OpenAI(api_key=_API_KEY)

CHAT_MODEL = os.getenv("CHAT_MODEL", "gpt-4o-mini")


def generate(system_prompt: str, user_prompt: str) -> str:
    """
    Returns a single text string. Uses Chat Completions API.

    Args:
        system_prompt: System message content
        user_prompt: User message content

    Returns:
        Generated text response
    """
    resp = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
    )

    # Extract text from first choice
    if resp.choices and resp.choices[0].message.content:
        return resp.choices[0].message.content.strip()
    return ""


__all__ = ["generate", "CHAT_MODEL"]

