"""
core.config
-----------
Centralized config. Reads from environment variables (.env via python-dotenv).
Never hard-code secrets here — use .env or your secret manager.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import List

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class LLMSettings:
    # ---- Gemini (primary) ----
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
    gemini_endpoint: str = os.getenv(
        "GEMINI_ENDPOINT",
        "https://generativelanguage.googleapis.com/v1beta/models",
    )

    # ---- OpenRouter (fallback) ----
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    openrouter_endpoint: str = os.getenv(
        "OPENROUTER_ENDPOINT",
        "https://openrouter.ai/api/v1/chat/completions",
    )
    # Default model list. Free tiers churn — the provider also queries
    # /api/v1/models at startup (see openrouter_auto_discover) and ALWAYS
    # falls back to openrouter/free + openrouter/auto so a stale id never
    # blocks the chain.
    openrouter_models: List[str] = field(
        default_factory=lambda: [
            m.strip()
            for m in os.getenv(
                "OPENROUTER_MODELS",
                "google/gemma-4-26b-a4b-it:free,"
                "google/gemma-4-31b-it:free,"
                "openrouter/free",
            ).split(",")
            if m.strip()
        ]
    )
    # When true, the OpenRouter provider hits /api/v1/models on first use and
    # auto-includes any :free model returned. Set OPENROUTER_AUTO_DISCOVER=0
    # to disable (e.g., in airgapped tests).
    openrouter_auto_discover: bool = (
        os.getenv("OPENROUTER_AUTO_DISCOVER", "1") not in ("0", "false", "False")
    )

    # ---- Common ----
    request_timeout_s: int = int(os.getenv("LLM_TIMEOUT_S", "18"))
    max_retries_per_model: int = int(os.getenv("LLM_RETRIES", "0"))
    retry_backoff_s: float = float(os.getenv("LLM_BACKOFF_S", "0.75"))


@dataclass(frozen=True)
class StorageSettings:
    # SQLite is the default — zero-config, persists sessions/grades/users.
    # Set DATABASE_URL to a Postgres URL for production.
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./data/interview.db")


@dataclass(frozen=True)
class AuthSettings:
    secret_key: str = os.getenv("AUTH_SECRET_KEY", "dev-only-change-me-in-production")
    session_cookie: str = os.getenv("AUTH_COOKIE_NAME", "ip_session")
    session_ttl_seconds: int = int(os.getenv("AUTH_TTL_S", str(60 * 60 * 24 * 14)))  # 14d
    # Cookie attributes — defaults are dev-friendly. In production set:
    #   AUTH_COOKIE_SAMESITE=none  AUTH_COOKIE_SECURE=1
    # so the browser sends the cookie cross-site over HTTPS.
    cookie_samesite: str = os.getenv("AUTH_COOKIE_SAMESITE", "lax")
    cookie_secure: bool = os.getenv("AUTH_COOKIE_SECURE", "0") in ("1", "true", "True")


@dataclass(frozen=True)
class APISettings:
    host: str = os.getenv("API_HOST", "0.0.0.0")
    port: int = int(os.getenv("API_PORT", "8000"))
    cors_origins: List[str] = field(
        default_factory=lambda: [
            o.strip()
            for o in os.getenv(
                "CORS_ORIGINS",
                "http://localhost:5173,http://localhost:3000",
            ).split(",")
            if o.strip()
        ]
    )


@dataclass(frozen=True)
class AppSettings:
    llm: LLMSettings = field(default_factory=LLMSettings)
    storage: StorageSettings = field(default_factory=StorageSettings)
    auth: AuthSettings = field(default_factory=AuthSettings)
    api: APISettings = field(default_factory=APISettings)
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    log_dir: str = os.getenv("LOG_DIR", "./logs")


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Cached singleton — change env vars and restart the process to reload."""
    return AppSettings()
