"""
Router tests — use fake providers so no real HTTP happens.
Proves the fallback chain: failing-Gemini → succeeding-OpenRouter.
"""

from typing import List

import pytest

from core.llm.base import LLMProvider, LLMProviderError
from core.llm.router import LLMRouter
from core.models import LLMRequest, LLMResponse


class _Fake(LLMProvider):
    def __init__(self, name: str, models: List[str], *, fail_n: int = 0, status: int | None = None):
        self.name = name
        self._models = models
        self._fail_n = fail_n
        self._status = status
        self.calls = 0

    def is_configured(self) -> bool:
        return True

    def models(self) -> List[str]:
        return list(self._models)

    def generate(self, req: LLMRequest, model: str) -> LLMResponse:
        self.calls += 1
        if self.calls <= self._fail_n:
            raise LLMProviderError(
                f"forced failure #{self.calls}", provider=self.name, model=model, status=self._status
            )
        return LLMResponse(text=f"ok from {self.name}/{model}", model=model, provider=self.name, latency_ms=1)


def test_primary_succeeds_first_try():
    primary = _Fake("primary", ["m1"])
    fallback = _Fake("fallback", ["f1"])
    router = LLMRouter(providers=[primary, fallback])
    resp = router.complete(LLMRequest(system="s", user="u"))
    assert resp.provider == "primary"
    assert primary.calls == 1
    assert fallback.calls == 0


def test_falls_back_when_primary_keeps_failing(monkeypatch):
    # Make backoff a no-op so the test is fast.
    import core.llm.router as r_mod
    monkeypatch.setattr(r_mod.time, "sleep", lambda _s: None)

    # Primary fails enough to exhaust retries on its only model.
    primary = _Fake("primary", ["m1"], fail_n=99)
    fallback = _Fake("fallback", ["f1"])
    router = LLMRouter(providers=[primary, fallback])

    resp = router.complete(LLMRequest(system="s", user="u"))
    assert resp.provider == "fallback"
    assert fallback.calls == 1


def test_skips_provider_on_auth_error(monkeypatch):
    """401 means key is bad — skip the WHOLE provider, don't waste retries."""
    import core.llm.router as r_mod
    monkeypatch.setattr(r_mod.time, "sleep", lambda _s: None)

    primary = _Fake("primary", ["m1", "m2", "m3"], fail_n=99, status=401)
    fallback = _Fake("fallback", ["f1"])
    router = LLMRouter(providers=[primary, fallback])

    resp = router.complete(LLMRequest(system="s", user="u"))
    # Primary was tried exactly once (no retries on 401, no other models attempted).
    assert primary.calls == 1
    assert resp.provider == "fallback"


def test_all_fail_raises(monkeypatch):
    import core.llm.router as r_mod
    monkeypatch.setattr(r_mod.time, "sleep", lambda _s: None)

    p = _Fake("p", ["m1"], fail_n=99)
    f = _Fake("f", ["m1", "m2"], fail_n=99)
    router = LLMRouter(providers=[p, f])
    with pytest.raises(LLMProviderError):
        router.complete(LLMRequest(system="s", user="u"))


def test_404_skips_to_next_model_without_retries(monkeypatch):
    """A 404 means the model is gone — don't waste retries, just move on."""
    import core.llm.router as r_mod
    monkeypatch.setattr(r_mod.time, "sleep", lambda _s: None)

    # Provider has 3 models. Models m1 and m2 are gone (404). m3 works.
    class _Provider(LLMProvider):
        name = "or"
        def __init__(self):
            self._models = ["m1", "m2", "m3"]
            self.calls = []
        def is_configured(self): return True
        def models(self): return list(self._models)
        def generate(self, req, model):
            self.calls.append(model)
            if model in ("m1", "m2"):
                raise LLMProviderError("not found", provider=self.name, model=model, status=404)
            return LLMResponse(text="ok", model=model, provider=self.name, latency_ms=1)

    prov = _Provider()
    router = LLMRouter(providers=[prov])
    resp = router.complete(LLMRequest(system="s", user="u"))
    assert resp.model == "m3"
    # Each 404'd model should have been tried EXACTLY ONCE — no retries.
    assert prov.calls == ["m1", "m2", "m3"]
