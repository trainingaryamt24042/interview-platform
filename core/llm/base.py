"""
core.llm.base
-------------
Provider interface. Every concrete provider implements `generate()`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from core.models import LLMRequest, LLMResponse


class LLMProvider(ABC):
    """Common contract for every LLM backend the router knows about."""

    name: str = "abstract"

    @abstractmethod
    def is_configured(self) -> bool:
        """True if the provider has the credentials it needs to be tried."""

    @abstractmethod
    def models(self) -> List[str]:
        """Concrete model identifiers this provider will attempt, in order."""

    @abstractmethod
    def generate(self, req: LLMRequest, model: str) -> LLMResponse:
        """
        Produce a completion. MUST raise on any failure (HTTP, timeout,
        empty response, content blocked) so the router can move on.
        """


class LLMProviderError(RuntimeError):
    """All provider failures bubble up as this so the router can catch one type."""

    def __init__(self, message: str, *, provider: str, model: str, status: int | None = None):
        super().__init__(message)
        self.provider = provider
        self.model = model
        self.status = status
