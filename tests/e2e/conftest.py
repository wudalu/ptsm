from __future__ import annotations

import pytest

from ptsm.config.settings import get_settings


@pytest.fixture(autouse=True)
def force_offline_llm_provider(monkeypatch: pytest.MonkeyPatch):
    """Keep e2e dry-run tests deterministic even when local .env has real keys."""
    monkeypatch.setenv("DEFAULT_LLM_PROVIDER", "deterministic")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
