import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.db import dump_json, get_conn, init_db
from app.schemas import Coordinate, PlaceCandidate, RecommendationRequest, RouteMetric, Scenario, SyntheticUser
from app.services import session_store
from app.services.scoring import google_directions_url, min_max_normalize, recommend, resolve_effective_weights


def test_product_filters_allow_one_or_zero_without_stale_results(monkeypatch, tmp_path):
    _seed_recommendation_case(monkeypatch, tmp_path)
    single = recommend(RecommendationRequest(scenario_id="s1", min_rating=5))
    assert single.valid_alternatives == 1
    assert len(single.recommendations) == 1
    empty = recommend(RecommendationRequest(scenario_id="s1", max_duration_minutes=1))
    assert empty.valid_alternatives == 0 and empty.recommendations == []


def test_min_max_normalize_inverts_duration_scores():
    assert min_max_normalize([10, 20, 30], invert=True) == [1.0, 0.5, 0.0]


def test_min_max_normalize_handles_constant_values():
    assert min_max_normalize([7, 7, 7], invert=True) == [1.0, 1.0, 1.0]


def test_google_directions_url_contains_destination_and_mode():
    candidate = PlaceCandidate(
        id="c1",
        scenario_id="s1",
        place_id="p1",
        name="Test",
        address="Test address",
        category="cafe",
        rating=4.5,
        review_count=120,
        lat=39.9,
        lng=32.8,
        provider="synthetic",
    )
    url = google_directions_url(candidate, "driving")
    assert "destination=39.9,32.8" in url
    assert "travelmode=driving" in url


def test_balanced_profile_uses_report_default_weights_when_lambda_is_omitted():
    weights, source, lambda_value = resolve_effective_weights(
        RecommendationRequest(scenario_id="s1", priority_profile="balanced")
    )
    assert weights.fairness == 0.5
    assert weights.efficiency == 0.5
    assert weights.quality == 0
    assert source == "profile:balanced"
    assert lambda_value == 0.5


def test_advanced_weights_are_resolved_to_lambda_axis():
    weights, source, lambda_value = resolve_effective_weights(
        RecommendationRequest(
            scenario_id="s1",
            advanced_preferences_enabled=True,
            fairness_weight=7,
            efficiency_weight=2,
            quality_weight=1,
        )
    )
    assert weights.fairness == 0.7778
    assert weights.efficiency == 0.2222
    assert weights.quality == 0
    assert source == "advanced_lambda_weights"
    assert lambda_value == 0.7778


def test_lambda_one_is_pure_fairness_axis():
    weights, source, _lambda_value = resolve_effective_weights(
        RecommendationRequest(
            scenario_id="s1",
            priority_profile="quality",
            lambda_value=1,
        )
    )
    assert weights.fairness == 1
    assert weights.efficiency == 0
    assert weights.quality == 0
    assert source == "lambda"


def _seed_recommendation_case(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'scoring.db'}")
    get_settings.cache_clear()
    init_db()
    users = [
        {"id": "u1", "label": "Katılımcı 1", "lat": 39.9, "lng": 32.8},
        {"id": "u2", "label": "Katılımcı 2", "lat": 39.91, "lng": 32.81},
    ]
    candidates = [
        ("c_eff", "Verimli", 3.5, 10),
        ("c_fair", "Adil", 4.0, 50),
        ("c_quality", "Kaliteli", 5.0, 1000),
    ]
    durations = {
        "c_eff": [5, 15],
        "c_fair": [11, 11],
        "c_quality": [5, 15],
    }
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO scenarios (id, city, category, group_size, travel_mode, radius_m, seed, users_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("s1", "Ankara", "cafe", 2, "driving", 2500, 42, dump_json(users)),
        )
        for index, (candidate_id, name, rating, review_count) in enumerate(candidates, 1):
            conn.execute(
                """
                INSERT INTO place_candidates
                (id, scenario_id, place_id, name, address, category, rating, review_count, lat, lng, provider, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate_id,
                    "s1",
                    f"place-{candidate_id}",
                    name,
                    "Adres",
                    "cafe",
                    rating,
                    review_count,
                    39.9 + index / 100,
                    32.8 + index / 100,
                    "synthetic",
                    "{}",
                ),
            )
            for user_index, duration in enumerate(durations[candidate_id], 1):
                conn.execute(
                    """
                    INSERT INTO route_metrics
                    (id, scenario_id, user_id, candidate_id, duration_seconds, distance_meters, provider, raw_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"r-{candidate_id}-{user_index}",
                        "s1",
                        f"u{user_index}",
                        candidate_id,
                        duration * 60,
                        duration * 100,
                        "synthetic",
                        "{}",
                    ),
                )


def test_lambda_zero_and_one_match_min_sum_and_min_max(monkeypatch, tmp_path):
    _seed_recommendation_case(monkeypatch, tmp_path)

    efficient = recommend(RecommendationRequest(scenario_id="s1", lambda_value=0, k=3))
    fair = recommend(RecommendationRequest(scenario_id="s1", lambda_value=1, k=3))

    assert efficient.recommendations[0].candidate.name == "Kaliteli"
    assert efficient.recommendations[0].t_sum_minutes == 20
    assert efficient.recommendations[0].score_breakdown.quality_component == 0
    assert fair.recommendations[0].candidate.name == "Adil"
    assert fair.recommendations[0].t_max_minutes == 11


def test_quality_only_breaks_ties(monkeypatch, tmp_path):
    _seed_recommendation_case(monkeypatch, tmp_path)

    response = recommend(RecommendationRequest(scenario_id="s1", lambda_value=0, k=3))

    assert response.recommendations[0].candidate.name == "Kaliteli"
    assert response.recommendations[1].candidate.name == "Verimli"
    assert response.recommendations[0].score == response.recommendations[1].score
    assert response.valid_alternatives == 3


def test_person_delta_changes_duration_metrics_when_enabled(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'delta.db'}")
    get_settings.cache_clear()
    init_db()
    users = [
        {"id": "u1", "label": "Öncelikli", "lat": 39.9, "lng": 32.8, "delta_weight": 2.0},
        {"id": "u2", "label": "Esnek", "lat": 39.91, "lng": 32.81, "delta_weight": 0.5},
    ]
    candidates = [
        ("c_delta", "Delta Dostu", [5, 20]),
        ("c_balanced", "Dengeli Ham", [12, 12]),
        ("c_bad", "Uzak", [30, 30]),
    ]
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO scenarios (id, city, category, group_size, travel_mode, radius_m, seed, users_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("s_delta", "Ankara", "cafe", 2, "driving", 2500, 42, dump_json(users)),
        )
        for index, (candidate_id, name, durations) in enumerate(candidates, 1):
            conn.execute(
                """
                INSERT INTO place_candidates
                (id, scenario_id, place_id, name, address, category, rating, review_count, lat, lng, provider, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (candidate_id, "s_delta", candidate_id, name, "Adres", "cafe", 4, 100, 39.9 + index / 100, 32.8, "synthetic", "{}"),
            )
            for user_index, duration in enumerate(durations, 1):
                conn.execute(
                    """
                    INSERT INTO route_metrics
                    (id, scenario_id, user_id, candidate_id, duration_seconds, distance_meters, provider, raw_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (f"r-{candidate_id}-{user_index}", "s_delta", f"u{user_index}", candidate_id, duration * 60, 1000, "synthetic", "{}"),
                )

    raw = recommend(RecommendationRequest(scenario_id="s_delta", lambda_value=1, k=3))
    adjusted = recommend(
        RecommendationRequest(
            scenario_id="s_delta",
            lambda_value=1,
            k=3,
            use_adjusted_durations=True,
        )
    )

    assert raw.recommendations[0].candidate.name == "Dengeli Ham"
    assert adjusted.recommendations[0].candidate.name == "Delta Dostu"
    assert adjusted.recommendations[0].per_user[0].adjusted_duration_minutes == 10


def test_advanced_cost_priority_can_override_quality_tie_break(monkeypatch, tmp_path):
    _seed_recommendation_case(monkeypatch, tmp_path)

    response = recommend(
        RecommendationRequest(
            scenario_id="s1",
            lambda_value=0,
            k=3,
            advanced_priority_enabled=True,
            priority_weights={"report": 0, "quality": 0, "cost": 100, "focus": 0},
            manual_candidate_costs={"c_eff": 1, "c_quality": 5, "c_fair": 5},
        )
    )

    assert response.decision_mode == "advanced_priority"
    assert response.recommendations[0].candidate.name == "Verimli"
    assert response.recommendations[0].score_breakdown.cost_norm == 1


def test_criteria_weights_are_normalized(monkeypatch, tmp_path):
    _seed_recommendation_case(monkeypatch, tmp_path)

    response = recommend(
        RecommendationRequest(
            scenario_id="s1",
            scoring_mode="criteria_delta",
            criterion_weights={"rating": 100, "cost": 100, "proximity": 100},
            k=3,
        )
    )

    assert response.decision_mode == "criteria_delta"
    assert response.criterion_weights.rating == 0.3333
    assert response.criterion_weights.cost == 0.3333
    assert response.criterion_weights.proximity == 0.3333


def test_criteria_rating_weight_promotes_high_rating_candidate(monkeypatch, tmp_path):
    _seed_recommendation_case(monkeypatch, tmp_path)

    response = recommend(
        RecommendationRequest(
            scenario_id="s1",
            scoring_mode="criteria_delta",
            criterion_weights={"rating": 100, "cost": 0, "proximity": 0},
            k=3,
        )
    )

    assert response.recommendations[0].candidate.name == "Kaliteli"
    assert response.recommendations[0].score_breakdown.rating_component == 1


def test_criteria_cost_weight_promotes_low_cost_candidate(monkeypatch, tmp_path):
    _seed_recommendation_case(monkeypatch, tmp_path)

    response = recommend(
        RecommendationRequest(
            scenario_id="s1",
            scoring_mode="criteria_delta",
            criterion_weights={"rating": 0, "cost": 100, "proximity": 0},
            manual_candidate_costs={"c_eff": 1, "c_quality": 5, "c_fair": 5},
            k=3,
        )
    )

    assert response.recommendations[0].candidate.name == "Verimli"
    assert response.recommendations[0].score_breakdown.cost_component == 1


def _seed_focus_case(monkeypatch, tmp_path, db_name: str = "focus_delta.db") -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / db_name}")
    get_settings.cache_clear()
    init_db()
    users = [
        {"id": "u1", "label": "Ben", "lat": 39.9, "lng": 32.8, "delta_weight": 2.0},
        {"id": "u2", "label": "Diğer", "lat": 39.95, "lng": 32.85, "delta_weight": 1.0},
    ]
    candidates = [
        ("c_near_me", "Bana Yakın", 39.901, 32.801),
        ("c_near_other", "Diğerine Yakın", 39.95, 32.85),
        ("c_far", "Uzak", 40.0, 32.95),
    ]
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO scenarios (id, city, category, group_size, travel_mode, radius_m, seed, users_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("s_focus", "Ankara", "cafe", 2, "walking", 2500, 42, dump_json(users)),
        )
        for candidate_id, name, lat, lng in candidates:
            conn.execute(
                """
                INSERT INTO place_candidates
                (id, scenario_id, place_id, name, address, category, rating, review_count, lat, lng, provider, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (candidate_id, "s_focus", candidate_id, name, "Adres", "cafe", 4, 100, lat, lng, "synthetic", "{}"),
            )
            for user_id in ("u1", "u2"):
                conn.execute(
                    """
                    INSERT INTO route_metrics
                    (id, scenario_id, user_id, candidate_id, duration_seconds, distance_meters, provider, raw_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (f"r-{candidate_id}-{user_id}", "s_focus", user_id, candidate_id, 600, 1000, "synthetic", "{}"),
                )


def test_delta_weighted_focus_prefers_more_important_person(monkeypatch, tmp_path):
    _seed_focus_case(monkeypatch, tmp_path)

    response = recommend(
        RecommendationRequest(
            scenario_id="s_focus",
            lambda_value=0.5,
            k=3,
            advanced_priority_enabled=True,
            priority_weights={"report": 0, "quality": 0, "cost": 0, "focus": 100},
            focus_mode="delta_weighted_participants",
        )
    )

    assert response.recommendations[0].candidate.name == "Bana Yakın"
    assert response.focus_mode == "delta_weighted_participants"
    assert response.recommendations[0].focus_source == "Delta ağırlıklı tüm kişiler"
    assert response.recommendations[0].score_breakdown.focus_norm == 1


def test_criteria_person_delta_promotes_more_important_person(monkeypatch, tmp_path):
    _seed_focus_case(monkeypatch, tmp_path, "criteria_person_delta.db")

    response = recommend(
        RecommendationRequest(
            scenario_id="s_focus",
            scoring_mode="criteria_delta",
            criterion_weights={"rating": 0, "cost": 0, "proximity": 100},
            participant_proximity_weights={"u1": 2, "u2": 1},
            k=3,
        )
    )

    assert response.recommendations[0].candidate.name == "Bana Yakın"
    assert response.recommendations[0].score_breakdown.proximity_component > 0.7
    assert response.recommendations[0].score_breakdown.proximity_contributions[0].user_id == "u1"


def test_criteria_balanced_people_use_equal_proximity_weights(monkeypatch, tmp_path):
    _seed_focus_case(monkeypatch, tmp_path, "criteria_balanced_people.db")

    response = recommend(
        RecommendationRequest(
            scenario_id="s_focus",
            scoring_mode="criteria_delta",
            criterion_weights={"rating": 0, "cost": 0, "proximity": 100},
            participant_proximity_weights={"u1": 1, "u2": 1},
            k=3,
        )
    )
    weights = {
        row.user_id: row.weight
        for row in response.recommendations[0].score_breakdown.proximity_contributions
    }

    assert weights == {"u1": 0.5, "u2": 0.5}


def test_focus_mode_defaults_to_delta_weighted_participants_when_advanced(monkeypatch, tmp_path):
    _seed_focus_case(monkeypatch, tmp_path, "focus_default.db")

    response = recommend(
        RecommendationRequest(
            scenario_id="s_focus",
            lambda_value=0.5,
            k=3,
            advanced_priority_enabled=True,
            priority_weights={"report": 0, "quality": 0, "cost": 0, "focus": 100},
        )
    )

    assert response.focus_mode == "delta_weighted_participants"
    assert response.recommendations[0].candidate.name == "Bana Yakın"


def test_single_user_focus_mode_uses_selected_person(monkeypatch, tmp_path):
    _seed_focus_case(monkeypatch, tmp_path, "focus_single.db")

    response = recommend(
        RecommendationRequest(
            scenario_id="s_focus",
            lambda_value=0.5,
            k=3,
            advanced_priority_enabled=True,
            priority_weights={"report": 0, "quality": 0, "cost": 0, "focus": 100},
            focus_mode="single_user",
            focus_user_id="u2",
        )
    )

    assert response.focus_mode == "single_user"
    assert response.recommendations[0].candidate.name == "Diğerine Yakın"
    assert response.recommendations[0].focus_source == "Seçili kişi"


def test_custom_location_focus_mode_uses_focus_coordinate(monkeypatch, tmp_path):
    _seed_focus_case(monkeypatch, tmp_path, "focus_location.db")

    response = recommend(
        RecommendationRequest(
            scenario_id="s_focus",
            lambda_value=0.5,
            k=3,
            advanced_priority_enabled=True,
            priority_weights={"report": 0, "quality": 0, "cost": 0, "focus": 100},
            focus_mode="custom_location",
            focus_location=Coordinate(lat=39.95, lng=32.85),
        )
    )

    assert response.focus_mode == "custom_location"
    assert response.recommendations[0].candidate.name == "Diğerine Yakın"
    assert response.recommendations[0].focus_source == "Özel odak noktası"


def test_custom_location_and_delta_focus_mode_reports_combined_source(monkeypatch, tmp_path):
    _seed_focus_case(monkeypatch, tmp_path, "focus_combined.db")

    response = recommend(
        RecommendationRequest(
            scenario_id="s_focus",
            lambda_value=0.5,
            k=3,
            advanced_priority_enabled=True,
            priority_weights={"report": 0, "quality": 0, "cost": 0, "focus": 100},
            focus_mode="custom_location_and_delta",
            focus_location=Coordinate(lat=39.95, lng=32.85),
        )
    )

    assert response.focus_mode == "custom_location_and_delta"
    assert response.recommendations[0].focus_source == "Özel odak noktası + delta ağırlıklı tüm kişiler"


def test_none_focus_mode_keeps_focus_neutral(monkeypatch, tmp_path):
    _seed_focus_case(monkeypatch, tmp_path, "focus_none.db")

    response = recommend(
        RecommendationRequest(
            scenario_id="s_focus",
            lambda_value=0.5,
            k=3,
            advanced_priority_enabled=True,
            priority_weights={"report": 0, "quality": 0, "cost": 0, "focus": 100},
            focus_mode="none",
        )
    )

    assert response.focus_mode == "none"
    assert response.recommendations[0].focus_source == "Odak yakınlığı kullanılmadı"
    assert response.recommendations[0].score_breakdown.focus_norm == 0.5


def test_session_only_recommendation_run_is_not_persisted(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'session_recommend.db'}")
    get_settings.cache_clear()
    init_db()
    scenario = Scenario(
        id="s_session",
        city="Ankara",
        category="cafe",
        group_size=2,
        travel_mode="walking",
        radius_m=2500,
        seed=42,
        users=[
            SyntheticUser(id="user-1", label="A", lat=39.9, lng=32.8, delta_weight=1.2),
            SyntheticUser(id="user-2", label="B", lat=39.91, lng=32.81, delta_weight=1.0),
        ],
        session_only=True,
        input_mode="link",
    )
    session_store.put_scenario(scenario)
    candidates = [
        PlaceCandidate(
            id=f"c{index}",
            scenario_id="s_session",
            place_id=f"p{index}",
            name=f"Aday {index}",
            address="Adres",
            category="cafe",
            rating=4.2,
            review_count=100,
            lat=39.9 + index / 100,
            lng=32.8,
            provider="synthetic",
        )
        for index in range(1, 4)
    ]
    assert session_store.save_candidates("s_session", candidates)
    for candidate_index, candidate in enumerate(candidates, 1):
        for user_index, user in enumerate(scenario.users, 1):
            assert session_store.save_route(
                RouteMetric(
                    id=f"r-{candidate.id}-{user.id}",
                    scenario_id="s_session",
                    user_id=user.id,
                    candidate_id=candidate.id,
                    duration_seconds=(candidate_index + user_index + 8) * 60,
                    distance_meters=1000,
                    provider="synthetic",
                )
            )

    response = recommend(RecommendationRequest(scenario_id="s_session", k=3))

    assert response.recommendations
    with get_conn() as conn:
        count = conn.execute("SELECT COUNT(*) AS total FROM recommendation_runs").fetchone()["total"]
    assert count == 0
