import asyncio
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.db import init_db
from app.schemas import ParticipantLocationInput, ScenarioCreate, SyntheticUser, UserConditions
from app.services import google_maps
from app.services.places_catalog import CATALOG, balanced, google_types, match_category, normalize_categories
from app.services.scenario import create_scenario


def test_catalog_covers_events_beyond_the_original_five():
    assert {"paintball", "bowling", "escape_room", "go_kart", "cinema", "karaoke", "spa", "climbing"} <= set(CATALOG)
    assert len(CATALOG) >= 40
    assert "bar" not in CATALOG["billiards"]["types"]
    assert CATALOG["paintball"]["types"][0] == "paintball_center" and CATALOG["go_kart"]["types"] == ["go_karting_venue"]


def test_generated_client_lists_are_current():
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run([sys.executable, str(root / "scripts" / "sync_catalog.py"), "--check"], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout


def test_multiple_categories_are_normalised_and_limited():
    assert normalize_categories(["cafe", "Bowling", "cafe"]) == ["cafe", "bowling"]
    assert normalize_categories(None, "park") == ["park"]
    with pytest.raises(ValueError):
        normalize_categories(["cafe", "unknown"])
    with pytest.raises(ValueError):
        normalize_categories(["cafe", "bowling", "park", "museum", "spa", "karaoke"])


def test_google_types_are_one_union_and_places_are_matched_honestly():
    assert google_types(["cafe", "bowling"]) == ["cafe", "bowling_alley"]
    assert match_category(["cafe", "paintball"], ["amusement_center"], "Savaş Paintball Alanı") == "paintball"
    assert match_category(["cafe", "bowling"], ["bowling_alley"], "Strike") == "bowling"
    assert match_category(["cafe", "bowling"], ["car_wash"], "Bilinmeyen") is None
    assert match_category(["board_game"], [], "Köşe Kahve") is None
    # Name-only categories never claim a place just because of a broad Google type.
    assert match_category(["board_game"], ["cafe"], "Köşe Kahve") is None
    assert match_category(["board_game", "cafe"], ["cafe"], "Köşe Kahve") == "cafe"
    assert match_category(["escape_room"], ["amusement_center"], "KAÇIŞ ODASI ANKARA") == "escape_room"
    assert match_category(["climbing"], ["sports_club"], "TIRMANIŞ MERKEZİ") == "climbing"


def test_results_are_balanced_across_selected_categories():
    items = [("cafe", "c1"), ("cafe", "c2"), ("cafe", "c3"), ("paintball", "p1"), ("cafe", "c4")]
    assert balanced(items, ["cafe", "paintball"], 3) == ["c1", "p1", "c2"]
    assert balanced(items, ["paintball"], 3) == ["p1"]


def test_google_search_drops_unmatched_places_and_balances(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'g.db'}")
    get_settings.cache_clear()
    init_db()
    scenario = asyncio.run(create_scenario(ScenarioCreate(
        input_mode="link", session_only=True, categories=["cafe", "paintball"],
        participant_locations=[ParticipantLocationInput(label="A", value="39.92,32.85"),
                               ParticipantLocationInput(label="B", value="39.93,32.86")])))
    places = [{"id": f"c{i}", "displayName": {"text": f"Kafe {i}"}, "types": ["cafe"], "location": {"latitude": 39.9, "longitude": 32.8}} for i in range(5)]
    places.insert(3, {"id": "p1", "displayName": {"text": "Arena Paintball"}, "types": ["paintball_center"], "location": {"latitude": 39.9, "longitude": 32.8}})
    places.append({"id": "x", "displayName": {"text": "Oto Yıkama"}, "types": ["car_wash"], "location": {"latitude": 39.9, "longitude": 32.8}})
    sent = {}

    async def fake_post(url, body, method, mask):
        sent.update(body)
        return {"places": places}

    monkeypatch.setattr(google_maps, "_google_post", fake_post)
    monkeypatch.setattr(google_maps, "ensure_operation_capacity", lambda ops: None)
    monkeypatch.setattr(type(get_settings()), "has_google_key", property(lambda self: True))
    found = asyncio.run(google_maps.search_candidates(scenario.id, 3, None))
    assert sent["maxResultCount"] == 20 and sent["includedTypes"] == ["cafe", "paintball_center", "adventure_sports_center"]
    assert [c.place_id for c in found] == ["c0", "p1", "c1"]
    assert [c.category for c in found] == ["cafe", "paintball", "cafe"]


def test_excluded_categories_accept_new_types_only():
    assert UserConditions(excluded_categories=["paintball", "paintball"]).excluded_categories == ["paintball"]
    with pytest.raises(ValueError):
        UserConditions(excluded_categories=["not-a-venue"])


def test_scenario_keeps_every_category_and_each_persons_travel_mode(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'venues.db'}")
    get_settings.cache_clear()
    init_db()
    scenario = asyncio.run(create_scenario(ScenarioCreate(
        input_mode="link", session_only=True, categories=["cafe", "paintball"],
        participant_locations=[
            ParticipantLocationInput(label="A", value="39.92,32.85", travel_mode="transit"),
            ParticipantLocationInput(label="B", value="39.93,32.86"),
        ])))
    assert scenario.categories == ["cafe", "paintball"] and scenario.category == "cafe"
    assert [user.travel_mode for user in scenario.users] == ["transit", None]
    with pytest.raises(ValueError):
        ParticipantLocationInput(label="C", value="39.9,32.8", travel_mode="teleport")


def test_synthetic_routes_use_each_persons_own_mode(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'modes.db'}")
    get_settings.cache_clear()
    init_db()
    scenario = asyncio.run(create_scenario(ScenarioCreate(
        synthetic_fixture=True, travel_mode="driving", categories=["cafe", "bowling"],
        users=[SyntheticUser(id="u1", label="Yaya", lat=39.90, lng=32.80, travel_mode="walking"),
               SyntheticUser(id="u2", label="Araçlı", lat=39.90, lng=32.80)])))
    asyncio.run(google_maps.search_candidates(scenario.id, 4, None))
    metrics = asyncio.run(google_maps.build_route_matrix(scenario.id, "synthetic"))
    by_user = {}
    for metric in metrics:
        by_user.setdefault(metric.user_id, []).append(metric.duration_seconds)
    assert len(metrics) == 8
    assert sum(by_user["u1"]) > sum(by_user["u2"])


def test_missing_transit_route_names_the_person_and_mode(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'r.db'}")
    get_settings.cache_clear()
    init_db()
    scenario = asyncio.run(create_scenario(ScenarioCreate(
        input_mode="link", session_only=True,
        participant_locations=[ParticipantLocationInput(label="Ayşe", value="39.92,32.85", travel_mode="transit"),
                               ParticipantLocationInput(label="Can", value="39.93,32.86")])))
    asyncio.run(google_maps.search_candidates(scenario.id, 3, None))

    async def no_route(*args, **kwargs):
        raise RuntimeError("Google Routes bu kişi ve mekân arasında uygun rota bulamadı.")

    monkeypatch.setattr(google_maps, "_google_route", no_route)
    monkeypatch.setattr(google_maps, "ensure_operation_capacity", lambda ops: None)
    with pytest.raises(google_maps.RouteUnavailable, match="Ayşe için toplu taşıma rotası bulunamadı"):
        asyncio.run(google_maps.build_route_matrix(scenario.id, "google"))


def test_directions_link_omits_mode_when_people_travel_differently():
    from app.services.scoring import google_directions_url
    from app.schemas import PlaceCandidate
    place = PlaceCandidate(id="1", scenario_id="s", place_id="p", name="n", address="", category="cafe",
                           rating=4, review_count=1, lat=39.9, lng=32.8, provider="google")
    assert "travelmode" not in google_directions_url(place, None)
    assert google_directions_url(place, "transit").endswith("&travelmode=transit")
