from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from app.config import get_settings
from app.db import get_conn, init_db
from app.services import google_usage, usage_guard
from app.services.public_safety import reserve_rate_limits
from test_public_release import production, client


def configure(monkeypatch):
    monkeypatch.setenv("GOOGLE_DAILY_QUOTA_ENABLED", "false")
    monkeypatch.setenv("GOOGLE_LIFETIME_BUDGET_ENABLED", "false")
    monkeypatch.setenv("GOOGLE_MAPS_MAX_ATTEMPTS", "1")
    get_settings.cache_clear()


def test_no_daily_stop_after_pilot_allowance_and_restart(production, monkeypatch):
    configure(monkeypatch)
    for operation, count in [("geocoding", 4), ("places_nearby_new", 4), ("routes_compute_routes", 28)]:
        for _ in range(count):
            google_usage.reserve_call(operation, 1)
    init_db()
    get_settings.cache_clear()
    status = google_usage.usage_status()
    assert status["available"] and status["used_today"] == 36
    assert status["daily_quota_enforced"] is False
    assert status["daily_limit"] is None and status["remaining_today"] is None
    assert status["service_remaining"] == {"geocoding": None, "places": None, "routes": None}
    assert status["provider_quotas_managed_externally"] is True
    assert status["usage_accounting_enforced"] is True
    assert status["estimated_cost_tl"] == 36
    google_usage.ensure_capacity(25)
    with get_conn() as conn:
        usage_guard.verify(conn)
    with client(production) as browser:
        runtime = browser.get("/runtime-config").json()
        assert runtime["google_remaining_requests"] is None
        assert runtime["google_daily_quota_enforced"] is False
        assert all(capacity["available"] for mode in runtime["google_search_capacity"].values() for capacity in mode.values())
        assert browser.get("/health").json()["google_usage"]["daily_quota_enforced"] is False


def test_disabled_daily_quota_keeps_atomic_accounting(production, monkeypatch):
    configure(monkeypatch)
    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(lambda _: google_usage.reserve_call("geocoding_location", 1), range(40)))
    assert len(set(ids)) == 40
    assert google_usage.usage_status()["estimated_cost_tl"] == 40
    with get_conn() as conn:
        usage_guard.verify(conn)
        assert conn.execute("SELECT COUNT(*) FROM google_api_usage").fetchone()[0] == 40


def test_daily_quota_can_be_restored_without_resetting_history(production, monkeypatch):
    configure(monkeypatch)
    for _ in range(4):
        google_usage.reserve_call("places_nearby_new", 1)
    monkeypatch.setenv("GOOGLE_DAILY_QUOTA_ENABLED", "true")
    get_settings.cache_clear()
    with pytest.raises(google_usage.GoogleUsageBlocked, match="kotası"):
        google_usage.reserve_call("places_nearby_new", 1)
    assert google_usage.usage_status()["used_today"] == 4
    assert not google_usage.operation_capacity({"places_nearby_new": 1})["available"]


def test_daily_switch_does_not_disable_lifetime_cap(production, monkeypatch):
    configure(monkeypatch)
    monkeypatch.setenv("GOOGLE_LIFETIME_BUDGET_ENABLED", "true")
    monkeypatch.setenv("GOOGLE_BUDGET_LIMIT_TL", "1")
    get_settings.cache_clear()
    google_usage.reserve_call("routes_compute_routes", 1)
    with pytest.raises(google_usage.GoogleUsageBlocked, match="bütçesi"):
        google_usage.reserve_call("routes_compute_routes", 1)
    assert not google_usage.operation_capacity({"routes_compute_routes": 1})["available"]


@pytest.mark.parametrize("blocker", ["ledger", "prices", "disabled"])
def test_no_daily_cap_keeps_fail_closed_validation(production, monkeypatch, blocker):
    configure(monkeypatch)
    google_usage.reserve_call("routes_compute_routes", 1)
    if blocker == "ledger":
        with get_conn() as conn:
            conn.execute("DELETE FROM google_api_usage")
    elif blocker == "prices":
        monkeypatch.setenv("GOOGLE_PRICE_AUTO_REFRESH_ENABLED", "false")
        monkeypatch.setenv("GOOGLE_PRICE_VERIFIED_AT", (datetime.now(timezone.utc) - timedelta(days=8)).isoformat())
    else:
        monkeypatch.setenv("GOOGLE_MAPS_CALLS_ENABLED", "false")
    get_settings.cache_clear()
    assert not google_usage.usage_status()["available"]
    assert not google_usage.operation_capacity({"routes_compute_routes": 1})["available"]
    with pytest.raises(google_usage.GoogleUsageBlocked):
        google_usage.ensure_capacity(1)
    with pytest.raises(google_usage.GoogleUsageBlocked):
        google_usage.reserve_call("routes_compute_routes", 1)


def test_rate_limits_remain_enabled_without_daily_quota(production, monkeypatch):
    configure(monkeypatch)
    settings = get_settings()
    outcomes = [reserve_rate_limits(settings, f"s-{i}", "192.0.2.100", "/scenarios") for i in range(10)]
    assert sum(outcomes) == 6


def test_daily_quota_is_enabled_by_default(production):
    assert get_settings().google_daily_quota_enabled is True
    for _ in range(3):
        google_usage.reserve_call("geocoding", 1)
    with pytest.raises(google_usage.GoogleUsageBlocked, match="kotası"):
        google_usage.reserve_call("geocoding", 1)
