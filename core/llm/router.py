"""
core.llm.router
---------------
Resilient LLM router.

Order of attempts:
    1. Gemini (primary)        — gemini-2.0-flash-lite
    2. OpenRouter (fallback)   — gemma → llama → mistral (configurable list)

Per-(provider, model) policy:
    - timeout per request: settings.llm.request_timeout_s
    - retries on retriable errors: settings.llm.max_retries_per_model
    - exponential-ish backoff: settings.llm.retry_backoff_s * attempt

A retriable error is anything other than 4xx authn/authz failures
(401, 403). Those mean "stop trying this provider, go to the next".

Every attempt produces a LLMUsageLog entry so we can audit cost & reliability.
"""

from __future__ import annotations

import time
from typing import Callable, List, Optional

from core.config import get_settings
from core.llm.base import LLMProvider, LLMProviderError
from core.llm.gemini import GeminiProvider
from core.llm.openrouter import OpenRouterProvider
from core.logging_setup import get_logger
from core.models import LLMRequest, LLMResponse, LLMUsageLog

log = get_logger(__name__)


# A "log sink" is anything that can persist a usage record. Default = stdout
# log line. The API layer can swap in a DB writer.
LogSink = Callable[[LLMUsageLog], None]


def _default_sink(entry: LLMUsageLog) -> None:
    log.info(
        "LLM_USAGE provider=%s model=%s success=%s latency=%dms purpose=%s err=%s",
        entry.provider, entry.model, entry.success, entry.latency_ms,
        entry.purpose, entry.error or "",
    )


# 401/403 mean credentials are wrong — no point retrying THIS provider.
PROVIDER_FATAL = {401, 403}
# 404 means THIS specific model is gone — skip it but try the next model.
MODEL_FATAL = {404}


class LLMRouter:
    """
    Public surface is just `complete()`. Everything else is internal.
    """

    def __init__(
        self,
        providers: Optional[List[LLMProvider]] = None,
        log_sink: LogSink = _default_sink,
    ) -> None:
        self.cfg = get_settings().llm
        # Default order: Gemini, then OpenRouter. Skip any provider that
        # isn't configured so a missing key doesn't blow up everything.
        self.providers: List[LLMProvider] = providers or [
            GeminiProvider(),
            OpenRouterProvider(),
        ]
        self.providers = [p for p in self.providers if p.is_configured()]
        if not self.providers:
            log.warning("LLMRouter has NO configured providers — all calls will fail.")
        self.log_sink = log_sink

    # --------------------------------------------------------------
    # Public API
    # --------------------------------------------------------------

    def complete(
        self,
        req: LLMRequest,
        *,
        purpose: str = "generic",
        session_id: Optional[str] = None,
    ) -> LLMResponse:
        """Run the full fallback chain. Returns the first success or raises."""
        attempts = 0
        last_err: Optional[LLMProviderError] = None

        for provider in self.providers:
            skip_provider = False
            for model in provider.models():
                if skip_provider:
                    break
                for retry in range(self.cfg.max_retries_per_model + 1):
                    attempts += 1
                    started = time.time()
                    try:
                        resp = provider.generate(req, model)
                        # Success — record it and return.
                        resp.attempts = attempts
                        self.log_sink(LLMUsageLog(
                            session_id=session_id,
                            purpose=purpose,
                            provider=provider.name,
                            model=model,
                            success=True,
                            latency_ms=resp.latency_ms,
                        ))
                        return resp
                    except LLMProviderError as e:
                        last_err = e
                        elapsed_ms = int((time.time() - started) * 1000)
                        self.log_sink(LLMUsageLog(
                            session_id=session_id,
                            purpose=purpose,
                            provider=provider.name,
                            model=model,
                            success=False,
                            latency_ms=elapsed_ms,
                            error=str(e),
                        ))

                        # 401/403 → credentials bad. Skip the entire provider.
                        if e.status in PROVIDER_FATAL:
                            log.warning(
                                "Provider %s rejected creds (HTTP %s) — skipping it",
                                provider.name, e.status,
                            )
                            skip_provider = True
                            break  # exit retry loop; outer guard skips remaining models

                        # 404 → THIS model is gone. Don't retry, move to the
                        # next model on the same provider. (The provider
                        # marks it dead internally so models() won't return
                        # it again.)
                        if e.status in MODEL_FATAL:
                            log.warning(
                                "Model %s/%s missing (HTTP 404) — skipping to next model",
                                provider.name, model,
                            )
                            break  # exit retry loop, outer for-loop tries next model

                        # Otherwise: retriable. Back off and retry the same model.
                        if retry < self.cfg.max_retries_per_model:
                            sleep_s = self.cfg.retry_backoff_s * (retry + 1)
                            log.info(
                                "Retry %d/%d for %s/%s in %.1fs (err=%s)",
                                retry + 1, self.cfg.max_retries_per_model,
                                provider.name, model, sleep_s, e,
                            )
                            time.sleep(sleep_s)
                        else:
                            log.warning(
                                "Exhausted retries for %s/%s — moving on",
                                provider.name, model,
                            )
                else:
                    # for-else: ran out of retries on this model; try the next.
                    continue

        # If we got here, every provider/model failed.
        msg = f"All LLM providers failed after {attempts} attempt(s)."
        log.error(msg)
        if last_err:
            raise LLMProviderError(
                f"{msg} Last error: {last_err}",
                provider=last_err.provider,
                model=last_err.model,
            )
        raise LLMProviderError(msg, provider="none", model="none")
