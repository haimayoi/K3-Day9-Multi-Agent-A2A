"""Thin wrapper for the single model every agent is allowed to call.

Model name is imported from config.py, never hardcoded here again and never
read from .env (README.md #9.4 — model name must be declared in source).
Only OPENAI_API_KEY belongs in .env.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from openai import OpenAI

from .config import MODEL_NAME

load_dotenv()

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY not set. Copy .env.example to .env and fill it in."
            )
        _client = OpenAI(api_key=api_key)
    return _client


def call_llm(system_prompt: str, user_prompt: str, temperature: float = 0.0) -> str:
    """Single-turn call to MODEL_NAME. Returns the raw text response.

    temperature=0.0 by default: this pipeline needs reproducible judgments,
    not creative variation, across 50 graded cases.
    """
    client = _get_client()
    response = client.chat.completions.create(
        model=MODEL_NAME,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content or ""
