from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from app.config import get_settings
from app.db import get_conn
from app.services import google_usage, usage_guard
from test_public_release import production, client


def configure(monkeypatch):
    monkeypatch.setenv("GOOGLE_LIFETIME_BUDGET_ENABLED", "false")
    monkeypatch.setenv("GOOGLE_BUDGET_LIMIT_TL", "1")
    monkeypatch.setenv("GOOGLE_MAPS_MAX_ATTEMPTS", "1")
    get_settings.cache_clear()


def test_uncapped_mode_preserves_accounting_and_restart(production, monkeypatch):
    configure(monkeypatch)
    for _ in range(2):
        google_usage.reserve_call("routes_compute_routes", 1)
    status = google_usage.usage_status()
    assert status["available"] and not status["budget_enforced"]
    assert status["budget_limit_tl"] is None
    assert status["usage_accounting_enforced"]
    assert status["estimated_cost_tl"] == 2
    assert google_usage.operation_capacity({"places_nearby_new": 1, "routes_compute_routes": 9})["available"]
    google_usage.ensure_capacity(10)
    get_settings.cache_clear()
    with get_conn() as conn:
        usage_guard.verify(conn)
        assert conn.execute("SELECT COUNT(*) FROM google_api_usage").fetchone()[0] == 2
    with client(production) as browser:
        usage = browser.get("/health").json()["google_usage"]
        assert usage["budget_enforced"] is False
        assert usage["budget_limit_tl"] is None
        assert usage["usage_accounting_enforced"] is True


def test_uncapped_keeps_atomic_service_quotas(production, monkeypatch):
    configure(monkeypatch)
    def reserve(_):
        try:
            return google_usage.reserve_call("geocoding", 1)
        except google_usage.GoogleUsageBlocked:
            return None
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(result is not None for result in pool.map(reserve, range(12))) == 3
    assert not google_usage.operation_capacity({"geocoding": 1})["available"]
    assert google_usage.usage_status()["estimated_cost_tl"] == 3


def test_uncapped_keeps_daily_limit(production, monkeypatch):
    configure(monkeypatch)
    monkeypatch.setenv("GOOGLE_MAPS_DAILY_CALL_LIMIT", "1")
    get_settings.cache_clear()
    google_usage.reserve_call("routes_compute_routes", 1)
    with pytest.raises(google_usage.GoogleUsageBlocked, match="günlük"):
        google_usage.reserve_call("routes_compute_routes", 1)


def test_uncapped_keeps_ledger_guard(production, monkeypatch):
    configure(monkeypatch)
    google_usage.reserve_call("routes_compute_routes", 1)
    with get_conn() as conn:
        conn.execute("DELETE FROM google_api_usage")
    with pytest.raises(google_usage.GoogleUsageBlocked, match="sayacı"):
        google_usage.reserve_call("routes_compute_routes", 1)
    assert not google_usage.usage_status()["available"]


def test_uncapped_keeps_price_validation(production, monkeypatch):
    configure(monkeypatch)
    monkeypatch.setenv("GOOGLE_PRICE_AUTO_REFRESH_ENABLED", "false")
    monkeypatch.setenv("GOOGLE_PRICE_VERIFIED_AT", (datetime.now(timezone.utc) - timedelta(days=8)).isoformat())
    get_settings.cache_clear()
    with pytest.raises(google_usage.GoogleUsageBlocked, match="geçerlilik"):
        google_usage.reserve_call("routes_compute_routes", 1)


def test_default_remains_capped(production, monkeypatch):
    monkeypatch.setenv("GOOGLE_BUDGET_LIMIT_TL", "1")
    get_settings.cache_clear()
    google_usage.reserve_call("routes_compute_routes", 1)
    with pytest.raises(google_usage.GoogleUsageBlocked, match="bütçesi"):
        google_usage.reserve_call("routes_compute_routes", 1)
