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


def test_group_privacy_votes_expiration_and_revocation(production, monkeypatch):
    from app.services import group_invites
    from app.schemas import PlaceCandidate, RouteMetric
    with client(production) as host, client(production) as guest:
        hh, gh = headers(host), headers(guest)
        assert host.post("/groups", json={"size":2}).status_code == 403
        seats = host.post("/groups", headers=hh, json={"size":2}).json()["seats"]
        def act(index, action="view", **kwargs):
            return guest.post("/groups/guest", headers=gh, json={"token":seats[index]["token"],"action":action,**kwargs})
        assert guest.get("/groups/mine").json() is None
        assert guest.post("/groups/locations", headers=gh).status_code == 404
        assert host.post("/groups/locations", headers=hh).status_code == 409
        points = [{"lat":39.92, "lng":32.85},{"lat":39.93, "lng":32.86}]
        assert act(0,"locate").status_code == 422
        for i,p in enumerate(points):
            r = act(i, "locate", location=p, consent=True)
            assert set(r.json()) == {"seat","choices","ready","vote"} and r.headers["x-ortak-google-calls"] == "0"
        assert host.post("/groups/locations",headers=hh).json() == points
        scenario = host.post("/scenarios",json=scenario_body(),headers=hh).json()
        sid = scenario["id"]
        candidates = [PlaceCandidate(id=k,scenario_id=sid,place_id=k,name=k,address="test",category="cafe",rating=4,review_count=2,lat=39,lng=32,provider="google") for k in ["p1","p2"]]
        bundle = session_store._SESSION_SCENARIOS[sid]
        bundle.candidates = candidates
        ballot = {"scenario_id":sid,"candidates":["p1","p2"]}
        assert host.post("/groups/ballot",headers=hh,json=ballot).status_code == 422
        bundle.routes = [RouteMetric(id=c.id+u["id"],scenario_id=sid,user_id=u["id"],candidate_id=c.id,duration_seconds=120,distance_meters=200,provider="google") for c in candidates for u in scenario["users"]]
        assert host.post("/groups/ballot",headers=hh,json=ballot).status_code == 200
        assert act(0,"locate",location=points[0],consent=True).status_code == 409
        assert act(0,"vote",candidate_id="p1").json()["choices"][0]["votes"] == 1
        assert [c["votes"] for c in act(0,"vote",candidate_id="p2").json()["choices"]] == [0,1]
        assert act(1).json()["vote"] is None
        assert not act(0,"withdraw").json()["ready"] and not act(1).json()["choices"]
        assert host.delete("/groups/mine",headers=hh).status_code == 204 and act(0).status_code == 404
        seats = host.post("/groups",headers=hh,json={"size":2}).json()["seats"]
        now = group_invites.monotonic()
        monkeypatch.setattr(group_invites, "monotonic", lambda: now + 7201)
        assert act(0).status_code == 404 and host.get("/groups/mine").json() is None


def test_room_single_link_join_import_and_ballot(production, monkeypatch):
    from app.services import group_invites
    from app.schemas import PlaceCandidate, RouteMetric
    with client(production) as host, client(production) as guest:
        hh, gh = headers(host), headers(guest)
        lobby = host.post("/groups", headers=hh, json={"room": True, "name": " Cuma  ekibi "}).json()
        assert lobby["seats"] == [] and len(lobby["join"]) == 43 and lobby["capacity"] == get_settings().public_max_participants
        assert lobby["name"] == "Cuma ekibi" and lobby["saved"] is False
        assert host.post("/groups", headers=hh, json={"room": True}).status_code == 409
        assert guest.post("/groups/join", headers=gh, json={"join": "x" * 43, "name": "Ayşe"}).status_code == 404
        assert guest.post("/groups/join", headers=gh, json={"join": lobby["join"], "name": "   "}).status_code == 422
        joined = [guest.post("/groups/join", headers=gh, json={"join": lobby["join"], "name": n}).json() for n in ["Ayşe", " Mehmet  Can ", "Zeynep"]]
        assert [j["name"] for j in joined] == ["Ayşe", "Mehmet Can", "Zeynep"] and all(len(j["token"]) == 43 for j in joined)
        assert host.post("/groups/locations", headers=hh).status_code == 409
        def act(index, action="view", **kwargs):
            return guest.post("/groups/guest", headers=gh, json={"token": joined[index]["token"], "action": action, **kwargs})
        assert act(0, "locate", location={"lat": 39.92, "lng": 32.85}, travel_mode="plane").status_code == 422
        r = act(0, "locate", location={"lat": 39.92, "lng": 32.85}, travel_mode="transit")
        assert r.json()["ready"] and r.json()["travel_mode"] == "transit" and r.headers["x-ortak-google-calls"] == "0"
        act(2, "locate", location={"lat": 39.80, "lng": 32.80}, name="Zeynep K.")
        mine = host.get("/groups/mine").json()
        assert [(s["name"], s["ready"]) for s in mine["seats"]] == [("Ayşe", True), ("Mehmet Can", False), ("Zeynep K.", True)]
        points = host.post("/groups/locations", headers=hh).json()
        assert points == [{"lat": 39.92, "lng": 32.85, "label": "Ayşe", "travel_mode": "transit"},
                          {"lat": 39.80, "lng": 32.80, "label": "Zeynep K.", "travel_mode": None}]
        body = {"input_mode": "link", "session_only": True, "participant_locations": [
            {"label": p["label"], "value": f"{p['lat']},{p['lng']}", "travel_mode": p["travel_mode"]} for p in points]}
        scenario = host.post("/scenarios", json=body, headers=hh).json()
        sid = scenario["id"]
        bundle = session_store._SESSION_SCENARIOS[sid]
        bundle.candidates = [PlaceCandidate(id=k, scenario_id=sid, place_id=k, name=k, address="test", category="cafe", rating=4, review_count=2, lat=39, lng=32, provider="google") for k in ["p1", "p2"]]
        bundle.routes = [RouteMetric(id=c.id + u["id"], scenario_id=sid, user_id=u["id"], candidate_id=c.id, duration_seconds=120, distance_meters=200, provider="google") for c in bundle.candidates for u in scenario["users"]]
        assert host.post("/groups/ballot", headers=hh, json={"scenario_id": sid, "candidates": ["p1", "p2"]}).status_code == 200
        assert act(1, "vote", candidate_id="p1").status_code == 409
        assert act(2, "vote", candidate_id="p2").json()["choices"][1]["votes"] == 1
        assert guest.post("/groups/join", headers=gh, json={"join": lobby["join"], "name": "Geç"}).status_code == 409
        group_invites.groups[next(iter(group_invites.groups))].choices.clear()
        for i in range(get_settings().public_max_participants - 3):
            assert guest.post("/groups/join", headers=gh, json={"join": lobby["join"], "name": f"K{i}"}).status_code == 200
        assert guest.post("/groups/join", headers=gh, json={"join": lobby["join"], "name": "Fazla"}).status_code == 409


def test_saved_room_keeps_names_not_locations(production, monkeypatch):
    from app.services import group_invites
    with client(production) as host, client(production) as guest, client(production) as other:
        hh, gh, oh = headers(host), headers(guest), headers(other)
        room = host.post("/groups", headers=hh, json={"room": True}).json()
        a = guest.post("/groups/join", headers=gh, json={"join": room["join"], "name": "Ayşe"}).json()
        guest.post("/groups/guest", headers=gh, json={"token": a["token"], "action": "locate", "location": {"lat": 39.9, "lng": 32.8}, "travel_mode": "transit"})
        assert host.post("/groups/save", headers=hh, json={"name": "  "}).status_code == 422
        saved = host.post("/groups/save", headers=hh, json={"name": "Cuma ekibi"}).json()
        key = saved["owner_key"]
        assert saved["saved"] and len(key) == 43 and host.post("/groups/save", headers=hh, json={"name": "X"}).status_code == 409
        with get_conn() as conn:
            stored = [tuple(r) for r in conn.execute("SELECT name, travel_mode FROM saved_room_members")]
            dump = json.dumps([list(r) for t in ("saved_rooms", "saved_room_members") for r in conn.execute(f"SELECT * FROM {t}")])
        assert stored == [("Ayşe", "transit")]
        assert key not in dump and room["join"] not in dump and a["token"] not in dump and "39.9" not in dump
        assert host.post("/groups/rename", headers=hh, json={"name": "Cumartesi"}).json()["name"] == "Cumartesi"
        # Meeting ends: points are gone, the room and names remain.
        assert host.delete("/groups/mine", headers=hh).status_code == 204
        group_invites.groups.clear(); group_invites.hosts.clear()
        assert other.post("/groups/open", headers=oh, json={"key": "x" * 43}).status_code == 404
        reopened = other.post("/groups/open", headers=oh, json={"key": key}).json()
        assert reopened["name"] == "Cumartesi" and reopened["join"] is None
        assert reopened["seats"] == [{"name": "Ayşe", "ready": False, "travel_mode": "transit"}]
        # The member comes back with the token on their device, even before the host opens it.
        group_invites.groups.clear(); group_invites.hosts.clear()
        back = guest.post("/groups/guest", headers=gh, json={"token": a["token"]}).json()
        assert back["room_name"] == "Cumartesi" and back["name"] == "Ayşe" and not back["ready"]
        b = guest.post("/groups/join", headers=gh, json={"join": room["join"], "name": "Burak"}).json()
        assert b["seat"] == 2
        assert [s["name"] for s in other.post("/groups/open", headers=oh, json={"key": key}).json()["seats"]] == ["Ayşe", "Burak"]
        assert [s["name"] for s in other.post("/groups/remove", headers=oh, json={"seat": 2}).json()["seats"]] == ["Ayşe"]
        assert guest.post("/groups/guest", headers=gh, json={"token": b["token"]}).status_code == 404
        assert guest.post("/groups/guest", headers=gh, json={"token": a["token"], "action": "leave"}).json() == {"left": True}
        assert other.get("/groups/mine").json()["seats"] == []
        # Unused for 90 days: deleted. Explicit forget also deletes.
        with get_conn() as conn:
            conn.execute("UPDATE saved_rooms SET updated_at = 0")
        group_invites.purge_saved_rooms()
        group_invites.groups.clear(); group_invites.hosts.clear()
        assert other.post("/groups/open", headers=oh, json={"key": key}).status_code == 404
        r2 = host.post("/groups", headers=hh, json={"room": True}).json()
        k2 = host.post("/groups/save", headers=hh, json={"name": "Okul"}).json()["owner_key"]
        assert host.post("/groups/forget", headers=hh, json={"key": k2}).status_code == 204
        assert guest.post("/groups/join", headers=gh, json={"join": r2["join"], "name": "Ali"}).status_code == 404
        with get_conn() as conn:
            assert conn.execute("SELECT COUNT(*) FROM saved_rooms").fetchone()[0] == 0


def test_place_search_one_geocoding_call_and_typed_place_parse(production, monkeypatch):
    calls = []
    async def fake(url, params, operation, **kwargs):
        calls.append((params["address"], operation))
        return {"status": "OK", "results": [
            {"formatted_address": "Kale, Altındağ/Ankara", "geometry": {"location": {"lat": 39.9409, "lng": 32.8649}},
             "address_components": [{"long_name": "Ankara Kalesi"}]},
            {"formatted_address": "Bozuk", "geometry": {"location": {"lat": 120, "lng": 0}}}]}
    monkeypatch.setattr(location_parser, "google_request", fake)
    with client(production) as browser:
        h = headers(browser)
        found = browser.post("/locations/search", headers=h, json={"query": "  Ankara   Kalesi "})
        assert found.json() == [{"name": "Ankara Kalesi", "address": "Kale, Altındağ/Ankara", "lat": 39.9409, "lng": 32.8649}]
        assert calls == [("Ankara Kalesi", "geocoding_location")]
        assert browser.post("/locations/search", headers=h, json={"query": "a"}).status_code == 422
        assert browser.post("/locations/search", headers=h, json={"query": "39.92,32.85"}).json()[0]["lat"] == 39.92
        assert len(calls) == 1
        parsed = browser.post("/locations/parse", headers=h, json={"items": [{"label": "A", "value": "Mogan Gölü"}]}).json()[0]
        assert parsed["source"] == "google_geocoding" and parsed["location_input_type"] == "place_name" and parsed["lat"] == 39.9409
        assert calls[-1] == ("Mogan Gölü", "geocoding_location")
    async def failing(*args, **kwargs):
        raise RuntimeError("down")
    monkeypatch.setattr(location_parser, "google_request", failing)
    with client(production) as browser:
        assert browser.post("/locations/search", headers=headers(browser), json={"query": "Mogan"}).status_code == 503


def test_planner_shares_csrf_and_llm_rate_limits_without_google_calls(production):
    from app.services.public_safety import reserve_rate_limits
    with client(production) as browser:
        payload = {"city": "Ankara", "group_size": 3}
        assert browser.post("/plans/recommend", json=payload).status_code == 403
        result = browser.post("/plans/recommend", json=payload, headers=headers(browser))
        assert result.status_code == 200
        assert result.headers["x-ortak-google-calls"] == "0"
        assert result.headers["cache-control"] == "no-store"
    settings = get_settings()
    for path in ["/preferences/interpret", "/plans/interpret", "/plans/interpret"]:
        assert reserve_rate_limits(settings, "planner-rate", "192.0.2.25", path)
    assert not reserve_rate_limits(settings, "planner-rate", "192.0.2.25", "/preferences/interpret")


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
