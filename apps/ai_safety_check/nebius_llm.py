# apps/ai_safety_check/nebius_llm.py
"""Reasoning LLM via Nebius Token Factory (OpenAI-compatible)."""
from . import config


class NebiusLLM:
    def __init__(self, client=None):
        if client is None:
            from openai import OpenAI
            client = OpenAI(base_url=config.NEBIUS_BASE_URL, api_key=config.NEBIUS_API_KEY)
        self._client = client

    def complete(self, prompt: str, *, json_mode: bool = False) -> str:
        kwargs = {"model": config.NEBIUS_MODEL,
                  "messages": [{"role": "user", "content": prompt}]}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = self._client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""
