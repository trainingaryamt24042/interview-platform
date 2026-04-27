"""
core.llm.gemini
---------------
Google Gemini provider. Default model: gemini-2.0-flash-lite.
"""

from __future__ import annotations

import time
from typing import List

import requests

from core.config import get_settings
from core.llm.base import LLMProvider, LLMProviderError
from core.logging_setup import get_logger
from core.models import LLMRequest, LLMResponse

log = get_logger(__name__)


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self) -> None:
        self.cfg = get_settings().llm

    def is_configured(self) -> bool:
        return bool(self.cfg.gemini_api_key)

    def models(self) -> List[str]:
        return [self.cfg.gemini_model]

    def generate(self, req: LLMRequest, model: str) -> LLMResponse:
        if not self.is_configured():
            raise LLMProviderError("Gemini API key missing", provider=self.name, model=model)

        url = f"{self.cfg.gemini_endpoint}/{model}:generateContent?key={self.cfg.gemini_api_key}"

        # Gemini concatenates system + user as a single text block. Keeping
        # the role boundaries clear helps the model follow instructions.
        prompt_text = f"System:\n{req.system}\n\nUser:\n{req.user}\n\nAssistant:"

        payload = {
            "contents": [{"parts": [{"text": prompt_text}]}],
            "generationConfig": {
                "temperature": req.temperature,
                "maxOutputTokens": req.max_tokens,
                "topP": 0.95,
            },
        }

        started = time.time()
        try:
            resp = requests.post(
                url,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=self.cfg.request_timeout_s,
            )
        except requests.exceptions.Timeout as e:
            raise LLMProviderError(f"Timeout: {e}", provider=self.name, model=model) from e
        except requests.exceptions.RequestException as e:
            raise LLMProviderError(f"Network error: {e}", provider=self.name, model=model) from e

        latency_ms = int((time.time() - started) * 1000)

        if resp.status_code != 200:
            # 429 rate limit and 5xx are retriable — let the router decide.
            raise LLMProviderError(
                f"HTTP {resp.status_code}: {resp.text[:300]}",
                provider=self.name,
                model=model,
                status=resp.status_code,
            )

        data = resp.json()
        if "error" in data:
            raise LLMProviderError(
                data["error"].get("message", "Unknown Gemini error"),
                provider=self.name,
                model=model,
            )

        try:
            candidate = data["candidates"][0]
            finish = candidate.get("finishReason", "STOP")
            if finish != "STOP":
                raise LLMProviderError(
                    f"Content blocked: {finish}", provider=self.name, model=model
                )
            text = candidate["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as e:
            raise LLMProviderError(
                f"Malformed response: {e}", provider=self.name, model=model
            ) from e

        if not text or not text.strip():
            raise LLMProviderError("Empty completion", provider=self.name, model=model)

        log.debug("Gemini OK model=%s latency=%dms chars=%d", model, latency_ms, len(text))
        return LLMResponse(
            text=text.strip(),
            model=model,
            provider=self.name,
            latency_ms=latency_ms,
        )
