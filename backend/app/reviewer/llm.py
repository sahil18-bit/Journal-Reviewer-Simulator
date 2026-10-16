"""Small client for the language model. Supports Gemini, OpenAI and Anthropic."""

from __future__ import annotations

import json
import re
from typing import Protocol

import httpx

# First model is tried first; the next ones are used if a model name is not available.
DEFAULT_MODELS = {
    "gemini": ["gemini-flash-latest", "gemini-2.5-flash"],
    "openai": ["gpt-4o-mini", "gpt-4.1-mini"],
    "anthropic": ["claude-sonnet-4-5", "claude-haiku-4-5"],
}


def guess_provider(api_key: str) -> str:
    """Recognise the provider from the key's prefix (Claude sk-ant-, OpenAI sk-, Gemini AIza)."""
    key = api_key.strip()
    if key.startswith("sk-ant-"):
        return "anthropic"
    if key.startswith("sk-"):
        return "openai"
    return "gemini"


class LLMError(Exception):
    pass


class LLM(Protocol):
    def ask(self, system: str, prompt: str) -> str: ...


class HttpLLM:
    def __init__(self, provider: str, api_key: str, model: str = "", timeout: float = 120.0):
        if provider not in DEFAULT_MODELS:
            raise LLMError(f"Unknown provider: {provider}")
        if not api_key:
            raise LLMError("No API key configured.")
        self.provider = provider
        self.api_key = api_key
        self.models = [model] if model else list(DEFAULT_MODELS[provider])
        self.model = self.models[0]
        self.timeout = timeout

    def ask(self, system: str, prompt: str) -> str:
        """Ask the model; if the model name is unknown (HTTP 404), try the next default."""
        for i, model in enumerate(self.models):
            self.model = model
            try:
                return self._ask_once(system, prompt)
            except LLMError as exc:
                if "HTTP 404" not in str(exc) or i == len(self.models) - 1:
                    raise
        raise LLMError("No model available.")

    def _ask_once(self, system: str, prompt: str) -> str:
        try:
            if self.provider == "gemini":
                url = (
                    "https://generativelanguage.googleapis.com/v1beta/models/"
                    f"{self.model}:generateContent"
                )
                body = {
                    "system_instruction": {"parts": [{"text": system}]},
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.2,
                        "responseMimeType": "application/json",
                    },
                }
                r = httpx.post(
                    url, json=body, headers={"x-goog-api-key": self.api_key}, timeout=self.timeout
                )
                r.raise_for_status()
                return r.json()["candidates"][0]["content"]["parts"][0]["text"]
            if self.provider == "openai":
                body = {
                    "model": self.model,
                    "temperature": 0.2,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                }
                r = httpx.post(
                    "https://api.openai.com/v1/chat/completions",
                    json=body,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=self.timeout,
                )
                r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"]
            body = {
                "model": self.model,
                "max_tokens": 4000,
                "temperature": 0.2,
                "system": system,
                "messages": [{"role": "user", "content": prompt}],
            }
            r = httpx.post(
                "https://api.anthropic.com/v1/messages",
                json=body,
                headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01"},
                timeout=self.timeout,
            )
            r.raise_for_status()
            return "".join(b.get("text", "") for b in r.json()["content"])
        except httpx.HTTPStatusError as exc:
            raise LLMError(f"The AI provider returned HTTP {exc.response.status_code}.") from exc
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            raise LLMError("Could not get a response from the AI provider.") from exc


def parse_json(text: str) -> dict:
    """Pull the JSON object out of a model reply (models sometimes add ``` fences)."""
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise LLMError("The AI reply did not contain JSON.")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise LLMError("The AI reply contained invalid JSON.") from exc
    if not isinstance(data, dict):
        raise LLMError("The AI reply was not a JSON object.")
    return data
