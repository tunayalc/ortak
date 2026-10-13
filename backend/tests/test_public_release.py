import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.db import get_conn, init_db
from app.main import create_app
from app.schemas import ParticipantLocationInput
from app.services import google_usage, location_parser, session_store, usage_guard


@pytest.fixture
def production(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_ENVIRONMENT", "production")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://ortak.test")
    monkeypatch.setenv("SESSION_SECRET", "test-only-" * 8)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'public.db'}")
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-only-not-a-real-key")
    monkeypatch.setenv("GOOGLE_MAPS_CALLS_ENABLED", "true")
    monkeypatch.setenv("GOOGLE_UNIT_PRICES_TL", json.dumps(dict.fromkeys(google_usage.OPERATIONS, 1)))
    monkeypatch.setenv("GOOGLE_PRICE_VERIFIED_AT", datetime.now(timezone.utc).isoformat())
    monkeypatch.setenv("GOOGLE_PRICE_SOURCE", "test fixture, not an actual price quote")
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    get_settings.cache_clear()
    session_store._SESSION_SCENARIOS.clear()
    init_db()
    with get_conn() as conn:
        usage_guard.write(conn)
    yield create_app()
    session_store._SESSION_SCENARIOS.clear()
    get_settings.cache_clear()


def client(app):
    return TestClient(app, base_url="https://ortak.test")


def headers(browser):
    config = browser.get("/runtime-config")
    return {"Origin": "https://ortak.test", "X-ORTAK-CSRF": config.json()["csrf_token"]}


def scenario_body():
    return {"input_mode": "link", "session_only": True, "participant_locations": [
        {"label": "Kurgusal A", "value": "39.92,32.85"},
        {"label": "Kurgusal B", "value": "39.93,32.86"},
    ]}


def test_signed_secure_cookie_and_csrf(production):
    with client(production) as browser:
        config = browser.get("/runtime-config")
        cookie = config.headers["set-cookie"].lower()
        assert all(flag in cookie for flag in ["httponly", "secure", "samesite=lax"])
        assert browser.post("/scenarios", json=scenario_body()).status_code == 403
        assert browser.post("/scenarios", json=scenario_body(), headers={"Origin": "https://evil.test"}).status_code == 403
        response = browser.post("/scenarios", json=scenario_body(), headers=headers(browser))
        assert response.status_code == 200
        assert response.json()["session_only"] is True


def test_sessions_isolated_and_owner_can_delete(production):
    with client(production) as owner, client(production) as stranger:
        auth = headers(owner)
        sid = owner.post("/scenarios", json=scenario_body(), headers=auth).json()["id"]
        assert owner.get(f"/scenarios/{sid}").status_code == 200
        assert stranger.get(f"/scenarios/{sid}").status_code == 404
        assert stranger.post("/recommendations", json={"scenario_id": sid, "k": 3}, headers=headers(stranger)).status_code == 404
        assert stranger.delete(f"/scenarios/{sid}", headers=headers(stranger)).status_code == 404
        assert owner.delete(f"/scenarios/{sid}", headers=auth).status_code == 204
        assert owner.get(f"/scenarios/{sid}").status_code == 404
    with get_conn() as conn:
        for table in ("scenarios", "place_candidates", "route_metrics", "api_cache"):
            assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_absolute_ttl_not_extended_by_reads(production, monkeypatch):
    clock = [10000.0]
    monkeypatch.setattr(session_store, "_now", lambda: clock[0])
    with client(production) as browser:
        sid = browser.post("/scenarios", json=scenario_body(), headers=headers(browser)).json()["id"]
        clock[0] += 7100
        assert browser.get(f"/scenarios/{sid}").status_code == 200
        clock[0] += 101
        assert browser.get(f"/scenarios/{sid}").status_code == 404
        assert sid not in session_store._SESSION_SCENARIOS


def test_limits_reject_before_google_and_validation_never_echoes_input(production):
    with client(production) as browser:
        auth = headers(browser)
        body = scenario_body()
        body["participant_locations"] *= 5
        assert browser.post("/scenarios", json=body, headers=auth).status_code == 400
        assert browser.post("/candidates/search", json={"scenario_id": "missing", "max_results": 12}, headers=auth).status_code == 400
        bad = scenario_body()
        bad["participant_locations"][0]["value"] = "PRIVATE-LOCATION-" * 200
        response = browser.post("/scenarios", json=bad, headers=auth)
        assert response.status_code == 422 and "PRIVATE-LOCATION" not in response.text
        response = browser.post("/scenarios", content=b"x" * 65537, headers=auth)
        assert response.status_code == 413
    assert google_usage.usage_status()["used_today"] == 0


def test_quota_persists_across_apps_and_ten_concurrent_clients(production, monkeypatch):
    from app.services.public_safety import reserve_rate_limits
    settings = get_settings()
    def hit(index):
        return reserve_rate_limits(settings, f"session-{index}", "192.0.2.1", "/scenarios")
    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(hit, range(10)))
    assert sum(results) == 6
    init_db()
    assert not hit(99)
    with get_conn() as conn:
        assert "192.0.2.1" not in json.dumps([dict(row) for row in conn.execute("SELECT * FROM request_limits")])


def test_budget_atomic_and_persistent(production, monkeypatch):
    monkeypatch.setenv("GOOGLE_BUDGET_LIMIT_TL", "3")
    get_settings.cache_clear()
    def reserve(_):
        try:
            return google_usage.reserve_call("geocoding", 1)
        except google_usage.GoogleUsageBlocked:
            return None
    with ThreadPoolExecutor(max_workers=10) as pool:
        assert sum(value is not None for value in pool.map(reserve, range(10))) == 3
    init_db()
    get_settings.cache_clear()
    assert google_usage.usage_status()["estimated_cost_tl"] == 3
    assert reserve(0) is None


@pytest.mark.parametrize("age", [8, -1])
def test_stale_or_future_prices_fail_closed(production, monkeypatch, age):
    monkeypatch.setenv("GOOGLE_PRICE_VERIFIED_AT", (datetime.now(timezone.utc) - timedelta(days=age)).isoformat())
    get_settings.cache_clear()
    with pytest.raises(google_usage.GoogleUsageBlocked):
        google_usage.reserve_call("geocoding", 1)
    assert google_usage.usage_status()["used_today"] == 0


def test_missing_price_and_unknown_historical_cost_are_not_free(production, monkeypatch):
    monkeypatch.setenv("GOOGLE_UNIT_PRICES_TL", "{}")
    get_settings.cache_clear()
    with pytest.raises(google_usage.GoogleUsageBlocked):
        google_usage.reserve_call("geocoding", 1)
    monkeypatch.setenv("GOOGLE_UNIT_PRICES_TL", json.dumps(dict.fromkeys(google_usage.OPERATIONS, 1)))
    get_settings.cache_clear()
    with get_conn() as conn:
        conn.execute("INSERT INTO google_api_usage (usage_day, timestamp_utc, operation, attempt) VALUES ('old', 'old', 'geocoding', 1)")
    google_usage.reserve_call("geocoding", 1)
    assert google_usage.usage_status()["estimated_cost_tl"] == 2


@pytest.mark.parametrize("url", [
    "https://google.com.evil.test/maps/@39.92,32.85",
    "https://evilgoogle.com/maps?q=39.92,32.85",
    "http://www.google.com/maps?q=39.92,32.85",
    "https://user@www.google.com/maps?q=39.92,32.85",
    "https://www.google.com:8080/maps?q=39.92,32.85",
    "https://127.0.0.1/maps?q=39.92,32.85",
])
def test_untrusted_maps_url_rejected_without_fetch(url, monkeypatch):
    async def never(*args, **kwargs):
        pytest.fail("Untrusted URL triggered a paid or network call")
    monkeypatch.setattr(location_parser, "_expand_short_url", never)
    monkeypatch.setattr(location_parser, "_geocode_text", never)
    result = asyncio.run(location_parser.parse_location_input(ParticipantLocationInput(label="A", value=url)))
    assert result.error and result.lat is None


def test_private_dns_and_redirect_are_blocked(monkeypatch):
    async def private(*args, **kwargs):
        return [(2, 1, 6, "", ("127.0.0.1", 443))]
    async def check_dns():
        monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", private)
        with pytest.raises(ValueError, match="Özel"):
            await location_parser.require_public_host("maps.app.goo.gl")
    asyncio.run(check_dns())
    async def public(_):
        return ["8.8.8.8"]
    original = httpx.AsyncClient
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/meta-data"})
    monkeypatch.setattr(location_parser, "require_public_host", public)
    monkeypatch.setattr(location_parser.httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    assert asyncio.run(location_parser._expand_short_url("https://maps.app.goo.gl/example")) is None
    assert len(requests) == 1


def test_redirect_dns_is_pinned_and_tls_uses_google_host(monkeypatch):
    original = httpx.AsyncClient
    requests = []
    async def public(_):
        return ["8.8.8.8"]
    def handler(request):
        requests.append(request)
        return httpx.Response(302, headers={"location": "https://www.google.com/maps?q=39.92,32.85"})
    monkeypatch.setattr(location_parser, "require_public_host", public)
    monkeypatch.setattr(location_parser.httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    assert asyncio.run(location_parser._expand_short_url("https://maps.app.goo.gl/example"))
    assert requests[0].url.host == "8.8.8.8"
    assert requests[0].headers["host"] == "maps.app.goo.gl"
    assert requests[0].extensions["sni_hostname"] == "maps.app.goo.gl"


def test_out_of_range_coordinate_rejected_before_network(monkeypatch):
    async def never(*args, **kwargs):
        pytest.fail("Invalid coordinate must not cause network calls")
    monkeypatch.setattr(location_parser, "_expand_short_url", never)
    result = asyncio.run(location_parser.parse_location_input(ParticipantLocationInput(label="A", value="https://www.google.com/maps?q=99,200")))
    assert result.error and result.lat is None
