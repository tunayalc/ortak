import json

from app.config import get_settings
from app.db import get_conn
from app.schemas import PlaceCandidate, RouteMetric
from app.services import google_usage, location_parser, session_store
from test_public_release import production, client, headers, scenario_body


def prices(monkeypatch, budget=30, attempts=2):
    monkeypatch.setenv("GOOGLE_UNIT_PRICES_TL", json.dumps({"geocoding": .45, "geocoding_location": .45,
        "places_nearby_new": 3.15, "routes_compute_routes": .9}))
    monkeypatch.setenv("GOOGLE_BUDGET_LIMIT_TL", str(budget))
    monkeypatch.setenv("GOOGLE_MAPS_MAX_ATTEMPTS", str(attempts))
    get_settings.cache_clear()


def test_service_prices_allow_complete_search_without_overestimating_routes(production, monkeypatch):
    prices(monkeypatch)
    google_usage.ensure_operation_capacity(google_usage.search_operations(3, 3, "synthetic"))
    google_usage.ensure_operation_capacity({"routes_compute_routes": 9})
    assert google_usage.usage_status()["used_today"] == 0
    assert google_usage.operation_capacity(google_usage.search_operations(4, 3, "synthetic"))["available"]
    prices(monkeypatch, budget=23)
    assert not google_usage.operation_capacity(google_usage.search_operations(3, 3, "synthetic"))["available"]


def test_resolved_locations_do_not_require_exhausted_geocoding_quota(production):
    for _ in range(3):
        google_usage.reserve_call("geocoding_location", 1)
    with client(production) as browser:
        capacity = browser.get("/runtime-config").json()["google_search_capacity"]
    assert capacity["resolved_coordinates"]["3"]["available"] is True
    assert capacity["synthetic"]["3"]["available"] is False


def test_retry_headroom_and_runtime_refresh_block_exhausted_routes(production, monkeypatch):
    prices(monkeypatch, budget=100, attempts=1)
    monkeypatch.setenv("GOOGLE_MAPS_DAILY_CALL_LIMIT", "11")
    get_settings.cache_clear()
    with client(production) as browser:
        assert browser.get("/runtime-config").json()["google_search_capacity"]["resolved_coordinates"]["3"]["available"]
        google_usage.reserve_call("places_nearby_new", 1)
        for _ in range(9):
            google_usage.reserve_call("routes_compute_routes", 1)
        status = browser.get("/runtime-config").json()
    assert status["google_remaining_requests"] == 1
    assert status["google_search_capacity"]["resolved_coordinates"]["3"]["available"] is False
    assert google_usage.usage_status()["estimated_cost_tl"] == 11.25


def test_parsed_coordinates_are_not_geocoded_again_in_scenario(production, monkeypatch):
    calls = []
    async def geocode(value):
        calls.append(value)
        google_usage.reserve_call("geocoding_location", 1)
        return 39.92, 32.85
    async def no_redirect(_):
        return None
    monkeypatch.setattr(location_parser, "_geocode_text", geocode)
    monkeypatch.setattr(location_parser, "_expand_short_url", no_redirect)
    with client(production) as browser:
        auth = headers(browser)
        items = [{"label": "A", "value": "https://www.google.com/maps?q=Ankara"},
                 {"label": "B", "value": "https://www.google.com/maps?q=Mamak"}]
        parsed = browser.post("/locations/parse", json={"items": items}, headers=auth).json()
        body = scenario_body()
        body["participant_locations"] = [{"label": item["label"], "value": f"{item['lat']},{item['lng']}"} for item in parsed]
        assert browser.post("/scenarios", json=body, headers=auth).status_code == 200
    assert len(calls) == 2
    assert google_usage.usage_status()["used_today"] == 2
    with get_conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM scenarios").fetchone()[0] == 0


def test_production_rejects_partially_complete_candidate_matrix(production):
    with client(production) as browser:
        auth = headers(browser)
        scenario = browser.post("/scenarios", json=scenario_body(), headers=auth).json()
        bundle = session_store._SESSION_SCENARIOS[scenario["id"]]
        bundle.candidates = [PlaceCandidate(id=f"c{i}", scenario_id=scenario["id"], place_id=f"p{i}",
            name="Fixture", address="Fixture", category="cafe", lat=39.92, lng=32.85,
            rating=4.5, review_count=20, provider="google") for i in range(3)]
        bundle.routes = [RouteMetric(id=f"r{i}", scenario_id=scenario["id"], user_id=user["id"],
            candidate_id="c0", duration_seconds=60, distance_meters=100, provider="google")
            for i, user in enumerate(scenario["users"])]
        response = browser.post("/recommendations", json={"scenario_id": scenario["id"], "k": 3}, headers=auth)
    assert response.status_code == 400
    assert "eksik" in response.json()["detail"]
