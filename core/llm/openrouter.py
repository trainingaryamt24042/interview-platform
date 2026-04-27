"""
core.llm.openrouter
-------------------
OpenRouter provider. ONE API key, MANY models. Resilient to model churn:

1. The configured `OPENROUTER_MODELS` list is treated as a *preference* — the
   provider may add to it from auto-discovery and may remove from it when the
   API returns 404 ("model not found") so a deprecated id never causes
   repeated failures within the same process.

2. We always include OpenRouter's official meta-routers as final safety nets:
       - openrouter/auto      → routes to the cheapest sensible PAID model
                                that fits the request (only used if the
                                account has credit; harmless if it doesn't)
       - openrouter/free      → routes randomly across CURRENTLY-AVAILABLE
                                free models (zero cost, always works)

3. On startup, the provider can probe `/api/v1/models` to filter out any
   configured ids that no longer exist. This is best-effort and silently
   skipped on failure — we still have the meta-routers.
"""

from __future__ import annotations

import threading
import time
from typing import List, Set

import requests

from core.config import get_settings
from core.llm.base import LLMProvider, LLMProviderError
from core.logging_setup import get_logger
from core.models import LLMRequest, LLMResponse

log = get_logger(__name__)

# Meta-routers — these endpoints always exist and pick a working model
# for us. They're our insurance against model-id churn.
META_ROUTERS = ["openrouter/free", "openrouter/auto"]


class OpenRouterProvider(LLMProvider):
    name = "openrouter"

    def __init__(self) -> None:
        self.cfg = get_settings().llm
        self._lock = threading.Lock()
        self._dead_models: Set[str] = set()
        self._discovered: List[str] | None = None
        self._auto_discover_enabled = self.cfg.openrouter_auto_discover

    # ------------------------------------------------------------------
    # Public LLMProvider API
    # ------------------------------------------------------------------

    def is_configured(self) -> bool:
        return bool(self.cfg.openrouter_api_key)

    def models(self) -> List[str]:
        """
        Build the per-call attempt order:
          1. user-configured OPENROUTER_MODELS (less the dead ones)
          2. the two meta-routers as safety nets
          3. auto-discovered :free models (one-time on first call)

        Stable order, no duplicates, dead models filtered out.
        """
        with self._lock:
            ordered: List[str] = []

            for m in self.cfg.openrouter_models:
                if m and m not in ordered and m not in self._dead_models:
                    ordered.append(m)

            for m in META_ROUTERS:
                if m not in ordered and m not in self._dead_models:
                    ordered.append(m)

            if self._auto_discover_enabled and self._discovered is None:
                self._discovered = self._discover_free_models()

            for m in self._discovered or []:
                if m not in ordered and m not in self._dead_models:
                    ordered.append(m)

            return ordered

    def generate(self, req: LLMRequest, model: str) -> LLMResponse:
        if not self.is_configured():
            raise LLMProviderError("OpenRouter key missing", provider=self.name, model=model)

        headers = {
            "Authorization": f"Bearer {self.cfg.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/interview-platform",
            "X-Title": "AI Interview Platform",
        }

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": req.system},
                {"role": "user", "content": req.user},
            ],
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
        }

        started = time.time()
        try:
            resp = requests.post(
                self.cfg.openrouter_endpoint,
                headers=headers,
                json=payload,
                timeout=self.cfg.request_timeout_s,
            )
        except requests.exceptions.Timeout as e:
            raise LLMProviderError(f"Timeout: {e}", provider=self.name, model=model) from e
        except requests.exceptions.RequestException as e:
            raise LLMProviderError(f"Network error: {e}", provider=self.name, model=model) from e

        latency_ms = int((time.time() - started) * 1000)

        if resp.status_code != 200:
            # 404 = "no endpoints found for <model>" — disable for the rest
            # of the process so we don't keep wasting attempts on it.
            if resp.status_code == 404:
                self._mark_dead(model)
            raise LLMProviderError(
                f"HTTP {resp.status_code}: {resp.text[:300]}",
                provider=self.name,
                model=model,
                status=resp.status_code,
            )

        data = resp.json()

        # OpenRouter sometimes returns 200 with an `error` body when the
        # downstream provider routing failed.
        if isinstance(data, dict) and data.get("error"):
            err = data["error"]
            err_msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
            err_code = err.get("code") if isinstance(err, dict) else None
            if err_code == 404 or "no endpoints" in err_msg.lower():
                self._mark_dead(model)
            raise LLMProviderError(
                f"OpenRouter error: {err_msg}",
                provider=self.name,
                model=model,
                status=err_code if isinstance(err_code, int) else None,
            )

        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise LLMProviderError(
                f"Malformed response: {e}", provider=self.name, model=model
            ) from e

        if not text or not text.strip():
            raise LLMProviderError("Empty completion", provider=self.name, model=model)

        # When using a meta-router, OpenRouter tells us the actual model used.
        used_model = data.get("model") if isinstance(data, dict) else None
        if not isinstance(used_model, str) or not used_model:
            used_model = model

        log.debug(
            "OpenRouter OK requested=%s actual=%s latency=%dms chars=%d",
            model, used_model, latency_ms, len(text),
        )
        return LLMResponse(
            text=text.strip(),
            model=used_model,
            provider=self.name,
            latency_ms=latency_ms,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _mark_dead(self, model: str) -> None:
        with self._lock:
            if model not in self._dead_models:
                log.warning("OpenRouter model %s returned 404 — disabling for this process", model)
                self._dead_models.add(model)

    def _discover_free_models(self) -> List[str]:
        """
        Best-effort: ask OpenRouter for the current model catalogue and pick
        the free ones (id ends in ':free'). Returns [] on any failure.
        """
        try:
            resp = requests.get(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {self.cfg.openrouter_api_key}"},
                timeout=10,
            )
            if resp.status_code != 200:
                log.info("OpenRouter discovery skipped (HTTP %s)", resp.status_code)
                return []
            ids: List[str] = [
                m["id"]
                for m in resp.json().get("data", [])
                if isinstance(m, dict) and isinstance(m.get("id"), str)
            ]
            free = [i for i in ids if i.endswith(":free")][:10]
            log.info("OpenRouter discovery added %d free model(s)", len(free))
            return free
        except Exception as e:
            log.info("OpenRouter discovery failed silently: %s", e)
            return []
