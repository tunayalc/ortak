import asyncio
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.db import get_conn, init_db
from app.services import google_transport, google_usage


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'usage.db'}")
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "secret-never-recorded")
    monkeypatch.setenv("GOOGLE_MAPS_CALLS_ENABLED", "true")
    monkeypatch.setenv("GOOGLE_MAPS_DAILY_CALL_LIMIT", "3")
    get_settings.cache_clear()
    init_db()
    yield
    get_settings.cache_clear()


def test_disabled_calls_never_contact_google(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_CALLS_ENABLED", "false")
    get_settings.cache_clear()
    requests = []
    original = httpx.AsyncClient
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={})
    monkeypatch.setattr(google_transport.httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    with pytest.raises(google_usage.GoogleUsageBlocked, match="kapalı"):
        asyncio.run(google_transport.google_request("https://places.googleapis.com/v1/places:searchNearby", {}, "places_nearby_new", http_method="POST"))
    assert requests == []
    assert google_usage.usage_status()["used_today"] == 0


def test_parallel_reservations_cannot_exceed_daily_limit():
    def reserve(_):
        try:
            return google_usage.reserve_call("routes_compute_routes", 1)
        except google_usage.GoogleUsageBlocked:
            return None
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(reserve, range(12)))
    assert sum(item is not None for item in results) == 3
    get_settings.cache_clear()
    init_db()
    assert google_usage.usage_status()["used_today"] == 3
    with pytest.raises(google_usage.GoogleUsageBlocked):
        google_usage.reserve_call("places_nearby_new", 1)


def test_retries_count_and_usage_ledger_has_no_private_payload(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_DAILY_CALL_LIMIT", "2")
    get_settings.cache_clear()
    original = httpx.AsyncClient
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(429, json={})
    async def no_sleep(_):
        pass
    monkeypatch.setattr(google_transport.httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    monkeypatch.setattr(google_transport.asyncio, "sleep", no_sleep)
    with pytest.raises(google_usage.GoogleUsageBlocked):
        asyncio.run(google_transport.google_request("https://places.googleapis.com/v1/places:searchNearby", {"private": "location-do-not-store"}, "places_nearby_new", http_method="POST"))
    with get_conn() as conn:
        rows = [dict(row) for row in conn.execute("SELECT * FROM google_api_usage")]
    assert len(requests) == len(rows) == 2
    assert [row["attempt"] for row in rows] == [1, 2]
    assert all(row["outcome"] == "http_429" for row in rows)
    text = json.dumps(rows)
    assert "secret-never-recorded" not in text
    assert "location-do-not-store" not in text


def test_usage_day_rollover_preserves_previous_records(monkeypatch):
    monkeypatch.setattr(google_usage, "usage_day", lambda: "2026-10-12")
    google_usage.reserve_call("geocoding", 1)
    monkeypatch.setattr(google_usage, "usage_day", lambda: "2026-10-13")
    assert google_usage.usage_status()["used_today"] == 0
    google_usage.reserve_call("geocoding", 1)
    with get_conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM google_api_usage").fetchone()[0] == 2


def test_matrix_capacity_check_does_not_send_partial_work():
    google_usage.reserve_call("places_nearby_new", 1)
    with pytest.raises(google_usage.GoogleUsageBlocked, match="yetersiz"):
        google_usage.ensure_capacity(3)
    assert google_usage.usage_status()["used_today"] == 1
