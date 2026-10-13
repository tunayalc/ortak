import asyncio
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import httpx
import pytest

from app.config import get_settings
from app.db import get_conn, init_db
from app.schemas import PlaceCandidate, ScenarioCreate, RouteMetric
from app.services import google_maps, google_transport, session_store
from app.services.scenario import create_scenario


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'maps.db'}")
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-secret-do-not-log")
    monkeypatch.setenv("GOOGLE_MAPS_CALLS_ENABLED", "true")
    monkeypatch.setenv("GOOGLE_MAPS_DAILY_CALL_LIMIT", "33")
    get_settings.cache_clear()
    init_db()
    yield
    get_settings.cache_clear()


def candidate():
    return PlaceCandidate(id="c1", scenario_id="s1", place_id="p1", name="Test", address="Adres", category="cafe", rating=4.5, review_count=100, lat=39.91, lng=32.81, provider="google")


def test_google_driving_route_uses_duration_in_traffic(monkeypatch):
    captured = {}

    async def fake_google_post(_url, params, _method, field_mask):
        captured.update(params)
        captured["field_mask"] = field_mask
        return {"routes": [{"distanceMeters": 1000, "duration": "900s"}]}

    monkeypatch.setattr(google_maps, "_google_post", fake_google_post)

    metric = asyncio.run(
        google_maps._google_route("s1", "u1", 39.9, 32.8, candidate(), "driving")
    )

    assert captured["routingPreference"] == "TRAFFIC_AWARE"
    assert captured["travelMode"] == "DRIVE"
    assert captured["destination"] == {"placeId": "p1"}
    assert captured["field_mask"] == "routes.duration,routes.distanceMeters"
    assert metric.duration_seconds == 900
    assert metric.distance_meters == 1000


def test_empty_google_route_is_not_synthetic_data_labeled_google(monkeypatch):
    async def no_routes(*args):
        return {"routes": []}
    monkeypatch.setattr(google_maps, "_google_post", no_routes)
    with pytest.raises(RuntimeError, match="uygun rota bulamadı"):
        asyncio.run(google_maps._google_route("s1", "u1", 39.9, 32.8, candidate(), "walking"))


def test_invalid_google_duration_is_not_ranked(monkeypatch):
    async def invalid(*args):
        return {"routes": [{"duration": "nans", "distanceMeters": 100}]}
    monkeypatch.setattr(google_maps, "_google_post", invalid)
    with pytest.raises(RuntimeError, match="geçerli süre"):
        asyncio.run(google_maps._google_route("s1", "u1", 39.9, 32.8, candidate(), "walking"))


def test_places_new_and_no_permanent_google_content(monkeypatch):
    captured = {}
    async def nearby(url, body, operation, field_mask):
        captured.update(url=url, body=body, operation=operation, mask=field_mask)
        return {"places": [{"id": "google-place-1", "displayName": {"text": "Deneme"}, "formattedAddress": "Ankara", "location": {"latitude": 39.92, "longitude": 32.85}, "rating": 4.6, "userRatingCount": 123, "priceLevel": "PRICE_LEVEL_MODERATE", "attributions": [{"provider": "Test", "providerUri": "https://example.com"}]}]}
    monkeypatch.setattr(google_maps, "_google_post", nearby)
    scenario = asyncio.run(create_scenario(ScenarioCreate(synthetic_fixture=True, users=[{"id": "u1", "label": "Test 1", "lat": 39.92, "lng": 32.85}, {"id": "u2", "label": "Test 2", "lat": 39.93, "lng": 32.86}])))
    places = asyncio.run(google_maps.search_candidates(scenario.id, 30, None))
    assert captured["url"] == "https://places.googleapis.com/v1/places:searchNearby"
    assert captured["body"]["maxResultCount"] == 20
    assert captured["body"]["includedTypes"] == ["cafe"]
    assert "*" not in captured["mask"]
    assert places[0].price_level == 2
    assert places[0].review_count == 123
    assert places[0].attributions[0]["provider"] == "Test"
    assert session_store.list_candidates(scenario.id) == places
    with get_conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM api_cache WHERE provider = 'google'").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM place_candidates").fetchone()[0] == 0


def test_no_places_does_not_fabricate_candidates(monkeypatch):
    async def empty(*args):
        return {}
    monkeypatch.setattr(google_maps, "_google_post", empty)
    scenario = asyncio.run(create_scenario(ScenarioCreate(synthetic_fixture=True, users=[{"id": "u1", "label": "A", "lat": 39.9, "lng": 32.8}, {"id": "u2", "label": "B", "lat": 39.91, "lng": 32.81}])))
    assert asyncio.run(google_maps.search_candidates(scenario.id, 3, None)) == []


def mock_transport(monkeypatch, handler):
    original = httpx.AsyncClient
    monkeypatch.setattr(google_transport.httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))


def test_permission_error_is_not_retried_and_key_is_not_logged(monkeypatch, caplog):
    requests = []
    def denied(request):
        requests.append(request)
        return httpx.Response(403, json={"error": {"message": "test-secret-do-not-log"}})
    mock_transport(monkeypatch, denied)
    with caplog.at_level("INFO", logger="ortak.google"):
        with pytest.raises(RuntimeError) as error:
            asyncio.run(google_transport.google_request(google_maps.GOOGLE_PLACES_URL, {}, "places_nearby_new", http_method="POST", field_mask="places.id"))
    assert len(requests) == 1
    assert requests[0].headers["X-Goog-Api-Key"] == "test-secret-do-not-log"
    assert "test-secret-do-not-log" not in str(error.value)
    assert "test-secret-do-not-log" not in caplog.text


def test_quota_retry_records_real_attempts_without_payload(monkeypatch):
    attempts = []
    sleeps = []
    def quota_then_ok(request):
        attempts.append(request)
        return httpx.Response(429 if len(attempts) == 1 else 200, json={} if len(attempts) == 1 else {"places": []})
    async def sleep(seconds):
        sleeps.append(seconds)
    mock_transport(monkeypatch, quota_then_ok)
    monkeypatch.setattr(google_transport.asyncio, "sleep", sleep)
    async def run():
        with google_transport.capture_google_calls() as events:
            result = await google_transport.google_request(google_maps.GOOGLE_PLACES_URL, {"private": "coordinate-must-not-be-logged"}, "places_nearby_new", http_method="POST")
        return result, events
    result, events = asyncio.run(run())
    assert result == {"places": []}
    assert sleeps == [0.5]
    assert [event["http_status"] for event in events] == [429, 200]
    assert "coordinate-must-not-be-logged" not in json.dumps(events)


@pytest.mark.parametrize("limit", [1, 2, 3])
def test_retry_limit_stops_network_and_ledger_at_configured_attempt(monkeypatch, limit):
    monkeypatch.setenv("GOOGLE_MAPS_MAX_ATTEMPTS", str(limit))
    get_settings.cache_clear()
    requests = []
    def unavailable(request):
        requests.append(request)
        return httpx.Response(503, json={})
    async def no_sleep(_):
        pass
    mock_transport(monkeypatch, unavailable)
    monkeypatch.setattr(google_transport.asyncio, "sleep", no_sleep)
    with pytest.raises(RuntimeError, match="HTTP 503"):
        asyncio.run(google_transport.google_request(google_maps.GOOGLE_PLACES_URL, {}, "places_nearby_new", http_method="POST"))
    assert len(requests) == limit
    with get_conn() as conn:
        assert [row["attempt"] for row in conn.execute("SELECT attempt FROM google_api_usage ORDER BY id")] == list(range(1, limit + 1))


def test_failed_matrix_resumes_only_missing_pairs_without_rebilling_success(monkeypatch):
    from app.services import google_usage
    monkeypatch.setenv("GOOGLE_MAPS_MAX_ATTEMPTS", "1")
    get_settings.cache_clear()
    scenario = asyncio.run(create_scenario(ScenarioCreate(synthetic_fixture=True, users=[
        {"id": "u1", "label": "A", "lat": 39.92, "lng": 32.85},
        {"id": "u2", "label": "B", "lat": 39.93, "lng": 32.86} ])))
    places = [candidate().model_copy(update={"id": f"c{i}", "scenario_id": scenario.id}) for i in (1, 2)]
    session_store.save_candidates(scenario.id, places)
    calls = []
    async def route(sid, uid, lat, lng, place, mode, **kwargs):
        calls.append((uid, place.id))
        google_usage.reserve_call("routes_compute_routes", 1)
        if len(calls) == 3:
            raise RuntimeError("Temporary provider failure")
        return RouteMetric(id=str(len(calls)), scenario_id=sid, user_id=uid, candidate_id=place.id,
                           duration_seconds=60, distance_meters=100, provider="google")
    monkeypatch.setattr(google_maps, "_google_route", route)
    with pytest.raises(RuntimeError):
        asyncio.run(google_maps.build_route_matrix(scenario.id, "google"))
    assert len(session_store.list_routes(scenario.id)) == 2
    result = asyncio.run(google_maps.build_route_matrix(scenario.id, "google"))
    assert len(result) == 4
    assert calls.count(("u1", "c1")) == calls.count(("u1", "c2")) == 1
    assert google_usage.usage_status()["used_today"] == 5
    assert len(asyncio.run(google_maps.build_route_matrix(scenario.id, "google"))) == 4
    assert google_usage.usage_status()["used_today"] == 5
