import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.config import Settings, get_settings


@pytest.fixture(autouse=True)
def isolated_local_credentials(monkeypatch):
    # Unit tests must not load the developer's real credentials from .env.
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "")
    monkeypatch.setenv("GOOGLE_MAPS_CALLS_ENABLED", "false")
    monkeypatch.setenv("GOOGLE_PRICE_AUTO_REFRESH_ENABLED", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
