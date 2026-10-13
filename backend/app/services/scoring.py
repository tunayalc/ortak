from __future__ import annotations

import statistics
import uuid

from ..db import dump_json, get_conn
from ..schemas import (
    Coordinate,
    ConstraintStatus,
    CriterionWeights,
    EffectiveWeights,
    PerUserDuration,
    PlaceCandidate,
    PriorityWeights,
    ProximityContribution,
    Recommendation,
    RecommendationRequest,
    RecommendationResponse,
    ScoreBreakdown,
)
from .google_maps import list_candidates, list_route_metrics
from .geo import haversine_m
from .scenario import get_scenario


PROFILE_LAMBDAS: dict[str, float] = {
    "balanced": 0.5,
    "fairness": 1.0,
    "efficiency": 0.0,
    "quality": 0.5,
}

QUALITY_WEIGHTS = {
    "rating": 0.50,
    "review": 0.30,
    "category": 0.20,
}

ALL_DELTA_FOCUS_ID = "__all_delta__"

COST_SOURCE_LABELS = {
    "manual": "Manuel maliyet",
    "google_price_level": "Google fiyat seviyesi",
    "unknown": "Bilinmiyor; nötr kabul edildi",
    "none": "Maliyet kullanılmadı",
}

FOCUS_SOURCE_LABELS = {
    "none": "Odak yakınlığı kullanılmadı",
    "focus_location": "Özel odak noktası",
    "delta_weighted_participants": "Delta ağırlıklı tüm kişiler",
    "participant_delta": "Kişi yakınlık ağırlıkları",
    "focus_user": "Seçili kişi",
    "focus_location+delta_weighted_participants": "Özel odak noktası + delta ağırlıklı tüm kişiler",
    "focus_location+focus_user": "Özel odak noktası + seçili kişi",
}


def min_max_normalize(values: list[float], invert: bool = False) -> list[float]:
    if not values:
        return []
    min_value = min(values)
    max_value = max(values)
    if max_value == min_value:
        return [1.0 for _ in values]
    else:
        normalized = [(value - min_value) / (max_value - min_value) for value in values]
    if invert:
        return [1 - value for value in normalized]
    return normalized


def google_directions_url(candidate: PlaceCandidate, mode: str) -> str:
    return (
        "https://www.google.com/maps/dir/?api=1"
        f"&destination={candidate.lat},{candidate.lng}"
        f"&travelmode={mode}"
    )


def _weights_from_lambda(lambda_value: float) -> EffectiveWeights:
    return EffectiveWeights(
        fairness=round(lambda_value, 4),
        efficiency=round(1 - lambda_value, 4),
        quality=0.0,
    )


def _normalize_priority_weights(weights: PriorityWeights) -> PriorityWeights:
    total = weights.report + weights.quality + weights.cost + weights.focus
    if total <= 0:
        raise ValueError("Gelişmiş öncelik için en az bir ağırlık sıfırdan büyük olmalıdır.")
    return PriorityWeights(
        report=round(weights.report / total, 4),
        quality=round(weights.quality / total, 4),
        cost=round(weights.cost / total, 4),
        focus=round(weights.focus / total, 4),
    )


def _normalize_criterion_weights(weights: CriterionWeights) -> CriterionWeights:
    total = weights.rating + weights.cost + weights.proximity
    if total <= 0:
        raise ValueError("Seçim kriterleri için en az bir ağırlık sıfırdan büyük olmalıdır.")
    return CriterionWeights(
        rating=round(weights.rating / total, 4),
        cost=round(weights.cost / total, 4),
        proximity=round(weights.proximity / total, 4),
    )


def resolve_effective_weights(payload: RecommendationRequest) -> tuple[EffectiveWeights, str, float]:
    if payload.advanced_preferences_enabled:
        missing = [
            name
            for name, value in {
                "fairness_weight": payload.fairness_weight,
                "efficiency_weight": payload.efficiency_weight,
                "quality_weight": payload.quality_weight,
            }.items()
            if value is None
        ]
        if missing:
            raise ValueError(f"Gelişmiş tercihler için şu değerler zorunludur: {', '.join(missing)}")
        fairness = float(payload.fairness_weight or 0)
        efficiency = float(payload.efficiency_weight or 0)
        total = fairness + efficiency
        if total <= 0:
            raise ValueError("λ hesaplamak için adalet veya verimlilik ağırlığı sıfırdan büyük olmalıdır.")
        lambda_value = round(fairness / total, 4)
        return _weights_from_lambda(lambda_value), "advanced_lambda_weights", lambda_value

    if payload.lambda_value is not None:
        return _weights_from_lambda(payload.lambda_value), "lambda", payload.lambda_value

    lambda_value = PROFILE_LAMBDAS[payload.priority_profile]
    return _weights_from_lambda(lambda_value), f"profile:{payload.priority_profile}", lambda_value


def _quality_details(candidates: list[PlaceCandidate], category: str) -> dict[str, dict[str, float]]:
    ratings = min_max_normalize([candidate.rating for candidate in candidates])
    reviews = min_max_normalize([float(candidate.review_count) for candidate in candidates])
    scores: dict[str, dict[str, float]] = {}
    for index, candidate in enumerate(candidates):
        category_match = (
            1.0
            if category.lower() in candidate.category.lower()
            or category.lower() in candidate.name.lower()
            else 0.0
        )
        quality_norm = (
            QUALITY_WEIGHTS["rating"] * ratings[index]
            + QUALITY_WEIGHTS["review"] * reviews[index]
            + QUALITY_WEIGHTS["category"] * category_match
        )
        scores[candidate.id] = {
            "quality_norm": quality_norm,
            "rating_norm": ratings[index],
            "review_norm": reviews[index],
            "category_match": category_match,
        }
    return scores


def _cost_details(
    candidates: list[PlaceCandidate],
    manual_costs: dict[str, float],
) -> dict[str, dict[str, float | str | None]]:
    raw_values: dict[str, float | None] = {}
    sources: dict[str, str] = {}
    for candidate in candidates:
        if candidate.id in manual_costs:
            raw_values[candidate.id] = float(manual_costs[candidate.id])
            sources[candidate.id] = "manual"
        elif candidate.manual_cost is not None:
            raw_values[candidate.id] = float(candidate.manual_cost)
            sources[candidate.id] = "manual"
        elif candidate.price_level is not None:
            raw_values[candidate.id] = float(candidate.price_level)
            sources[candidate.id] = "google_price_level"
        else:
            raw_values[candidate.id] = None
            sources[candidate.id] = "unknown"

    known_items = [(candidate_id, value) for candidate_id, value in raw_values.items() if value is not None]
    normalized_known = min_max_normalize([float(value) for _candidate_id, value in known_items], invert=True)
    known_scores = {
        candidate_id: normalized_known[index]
        for index, (candidate_id, _value) in enumerate(known_items)
    }
    return {
        candidate.id: {
            "cost_norm": known_scores.get(candidate.id, 0.5),
            "cost_value": raw_values[candidate.id],
            "cost_source": sources[candidate.id],
        }
        for candidate in candidates
    }


def _cost_source_label(source: str) -> str:
    return COST_SOURCE_LABELS.get(source, source)


def _focus_source_label(source: str) -> str:
    return FOCUS_SOURCE_LABELS.get(source, source)


def _resolve_focus_mode(
    focus_location: Coordinate | None,
    focus_user_id: str | None,
    focus_mode: str | None,
    advanced_priority_enabled: bool,
) -> str:
    if focus_mode:
        return focus_mode
    if focus_location is not None and focus_user_id == ALL_DELTA_FOCUS_ID:
        return "custom_location_and_delta"
    if focus_location is not None:
        return "custom_location"
    if focus_user_id == ALL_DELTA_FOCUS_ID:
        return "delta_weighted_participants"
    if focus_user_id:
        return "single_user"
    if advanced_priority_enabled:
        return "delta_weighted_participants"
    return "none"


def _focus_groups(
    scenario_users: dict[str, object],
    focus_location: Coordinate | None,
    focus_user_id: str | None,
    focus_mode: str,
) -> tuple[list[list[tuple[float, float, float]]], str]:
    groups: list[list[tuple[float, float, float]]] = []
    sources: list[str] = []
    if focus_mode == "none":
        return groups, "none"
    if focus_mode in {"custom_location", "custom_location_and_delta"}:
        if focus_location is None:
            raise ValueError("Odak noktası için Google Maps linki veya lat,lng koordinatı gereklidir.")
        groups.append([(focus_location.lat, focus_location.lng, 1.0)])
        sources.append("focus_location")
    if focus_mode in {"delta_weighted_participants", "custom_location_and_delta"}:
        groups.append(
            [
                (user.lat, user.lng, max(float(user.delta_weight), 0.001))
                for user in scenario_users.values()
            ]
        )
        sources.append("delta_weighted_participants")
    if focus_mode == "single_user":
        if not focus_user_id or focus_user_id == ALL_DELTA_FOCUS_ID:
            raise ValueError("Tek kişiye yakınlık için geçerli bir odak kişi seçilmelidir.")
        user = scenario_users.get(focus_user_id)
        if user is None:
            raise ValueError("Odak kişi bulunamadı.")
        groups.append([(user.lat, user.lng, max(float(user.delta_weight), 0.001))])
        sources.append("focus_user")
    return groups, "+".join(sources) if sources else "none"


def _focus_details(
    candidates: list[PlaceCandidate],
    groups: list[list[tuple[float, float, float]]],
) -> dict[str, float]:
    if not groups:
        return {candidate.id: 0.5 for candidate in candidates}
    group_scores: list[list[float]] = []
    for group in groups:
        distances = []
        total_weight = sum(weight for _lat, _lng, weight in group)
        for candidate in candidates:
            weighted_distance = (
                sum(
                    haversine_m(candidate.lat, candidate.lng, lat, lng) * weight
                    for lat, lng, weight in group
                )
                / total_weight
            )
            distances.append(weighted_distance)
        group_scores.append(min_max_normalize(distances, invert=True))

    return {
        candidate.id: sum(scores[index] for scores in group_scores) / len(group_scores)
        for index, candidate in enumerate(candidates)
    }


def _effective_scoring_mode(payload: RecommendationRequest) -> str:
    if payload.scoring_mode != "criteria_delta":
        return payload.scoring_mode
    if payload.advanced_priority_enabled:
        return "advanced_priority"
    if (
        payload.lambda_value is not None
        or payload.advanced_preferences_enabled
        or payload.priority_profile != "balanced"
    ):
        return "report_lambda"
    return "criteria_delta"


def _normalized_participant_weights(
    scenario_users: dict[str, object],
    overrides: dict[str, float],
) -> dict[str, float]:
    raw_weights: dict[str, float] = {}
    for user_id, user in scenario_users.items():
        raw = overrides.get(user_id, getattr(user, "delta_weight", 1.0))
        if raw < 0:
            raise ValueError("Kişi yakınlık ağırlıkları negatif olamaz.")
        raw_weights[user_id] = float(raw)
    total = sum(raw_weights.values())
    if total <= 0:
        raise ValueError("Kişi yakınlığı için en az bir kişi ağırlığı sıfırdan büyük olmalıdır.")
    return {user_id: weight / total for user_id, weight in raw_weights.items()}


def _participant_proximity_details(
    candidates: list[PlaceCandidate],
    scenario_users: dict[str, object],
    participant_weights: dict[str, float],
) -> dict[str, dict[str, object]]:
    if not scenario_users:
        return {
            candidate.id: {"proximity_norm": 0.5, "contributions": []}
            for candidate in candidates
        }
    closeness_by_user: dict[str, list[float]] = {}
    distances_by_user: dict[str, list[float]] = {}
    for user_id, user in scenario_users.items():
        distances = [
            haversine_m(candidate.lat, candidate.lng, user.lat, user.lng)
            for candidate in candidates
        ]
        distances_by_user[user_id] = distances
        closeness_by_user[user_id] = min_max_normalize(distances, invert=True)

    details: dict[str, dict[str, object]] = {}
    for candidate_index, candidate in enumerate(candidates):
        contributions: list[ProximityContribution] = []
        proximity_norm = 0.0
        for user_id, user in scenario_users.items():
            weight = participant_weights[user_id]
            closeness = closeness_by_user[user_id][candidate_index]
            component = weight * closeness
            proximity_norm += component
            contributions.append(
                ProximityContribution(
                    user_id=user_id,
                    label=user.label,
                    weight=round(weight, 4),
                    closeness_norm=round(closeness, 4),
                    component=round(component, 4),
                    distance_km=round(distances_by_user[user_id][candidate_index] / 1000, 2),
                )
            )
        contributions.sort(key=lambda item: item.component, reverse=True)
        details[candidate.id] = {
            "proximity_norm": proximity_norm,
            "contributions": contributions,
        }
    return details


def recommend(payload: RecommendationRequest) -> RecommendationResponse:
    scenario = get_scenario(payload.scenario_id)
    candidates = list_candidates(payload.scenario_id)
    metrics = list_route_metrics(payload.scenario_id)
    if not candidates:
        raise ValueError("Aday mekân bulunamadı. Önce /candidates/search uç noktası çalıştırılmalıdır.")
    if not metrics:
        raise ValueError("Rota matrisi bulunamadı. Önce /routes/matrix uç noktası çalıştırılmalıdır.")

    by_candidate: dict[str, list] = {candidate.id: [] for candidate in candidates}
    for metric in metrics:
        by_candidate.setdefault(metric.candidate_id, []).append(metric)

    complete_candidates = [
        candidate for candidate in candidates if len(by_candidate.get(candidate.id, [])) == len(scenario.users)
    ]
    if not complete_candidates:
        raise ValueError("Tam rota matrisi olan aday bulunamadı.")
    if payload.min_rating is not None:
        complete_candidates = [candidate for candidate in complete_candidates if candidate.rating >= payload.min_rating]
    if payload.category:
        complete_candidates = [
            candidate
            for candidate in complete_candidates
            if payload.category.lower() in candidate.category.lower() or payload.category.lower() in candidate.name.lower()
        ]

    user_by_id = {user.id: user for user in scenario.users}
    stats = []
    for candidate in complete_candidates:
        candidate_metrics = by_candidate[candidate.id]
        raw_durations = [metric.duration_seconds / 60 for metric in candidate_metrics]
        adjusted_durations = [
            (metric.duration_seconds / 60) * user_by_id[metric.user_id].delta_weight
            for metric in candidate_metrics
        ]
        durations = adjusted_durations if payload.use_adjusted_durations else raw_durations
        distances = [metric.distance_meters / 1000 for metric in candidate_metrics]
        t_avg = statistics.mean(durations)
        t_sum = sum(durations)
        t_max = max(durations)
        variance = statistics.pvariance(durations) if len(durations) > 1 else 0.0
        if payload.max_duration_minutes is not None and t_max > payload.max_duration_minutes:
            continue
        stats.append(
            {
                "candidate": candidate,
                "metrics": candidate_metrics,
                "durations": durations,
                "raw_durations": raw_durations,
                "adjusted_durations": adjusted_durations,
                "distances": distances,
                "t_avg": t_avg,
                "t_sum": t_sum,
                "t_max": t_max,
                "variance": variance,
            }
        )
    effective_scoring_mode = _effective_scoring_mode(payload)
    if len(stats) < 3 and effective_scoring_mode != "criteria_delta":
        raise ValueError("Rapor hedefi için filtrelerden sonra en az üç geçerli alternatif gereklidir.")

    effective_weights, preference_source, effective_lambda = resolve_effective_weights(payload)
    priority_weights = (
        _normalize_priority_weights(payload.priority_weights)
        if effective_scoring_mode == "advanced_priority"
        else PriorityWeights(report=1.0, quality=0.0, cost=0.0, focus=0.0)
    )
    criterion_weights = (
        _normalize_criterion_weights(payload.criterion_weights)
        if effective_scoring_mode == "criteria_delta"
        else CriterionWeights(rating=0.0, cost=0.0, proximity=0.0)
    )
    decision_mode = effective_scoring_mode
    fairness_values = min_max_normalize([item["t_max"] for item in stats], invert=True)
    efficiency_values = min_max_normalize([item["t_sum"] for item in stats], invert=True)
    quality = _quality_details([item["candidate"] for item in stats], scenario.category)
    cost = _cost_details([item["candidate"] for item in stats], payload.manual_candidate_costs)
    effective_focus_mode = _resolve_focus_mode(
        payload.focus_location,
        payload.focus_user_id,
        payload.focus_mode,
        effective_scoring_mode == "advanced_priority",
    )
    focus_groups, focus_source = _focus_groups(
        user_by_id,
        payload.focus_location,
        payload.focus_user_id,
        effective_focus_mode,
    )
    focus_source_label = _focus_source_label(focus_source)
    focus = _focus_details([item["candidate"] for item in stats], focus_groups)
    participant_weights = _normalized_participant_weights(
        user_by_id,
        payload.participant_proximity_weights,
    )
    proximity = _participant_proximity_details(
        [item["candidate"] for item in stats],
        user_by_id,
        participant_weights,
    )

    ranked = []
    for index, item in enumerate(stats):
        fairness_norm = fairness_values[index]
        efficiency_norm = efficiency_values[index]
        quality_info = quality[item["candidate"].id]
        quality_score = quality_info["quality_norm"]
        cost_info = cost[item["candidate"].id]
        cost_norm = float(cost_info["cost_norm"])
        focus_norm = focus[item["candidate"].id]
        proximity_info = proximity[item["candidate"].id]
        proximity_norm = float(proximity_info["proximity_norm"])
        rating_norm = float(quality_info["rating_norm"])
        report_score = (
            effective_weights.fairness * fairness_norm
            + effective_weights.efficiency * efficiency_norm
        )
        score = report_score
        if effective_scoring_mode == "advanced_priority":
            score = (
                priority_weights.report * report_score
                + priority_weights.quality * quality_score
                + priority_weights.cost * cost_norm
                + priority_weights.focus * focus_norm
            )
        elif effective_scoring_mode == "criteria_delta":
            score = (
                criterion_weights.rating * rating_norm
                + criterion_weights.cost * cost_norm
                + criterion_weights.proximity * proximity_norm
            )
        ranked.append(
            {
                **item,
                "fairness_norm": fairness_norm,
                "efficiency_norm": efficiency_norm,
                "report_score": report_score,
                "quality_score": quality_score,
                "quality_info": quality_info,
                "cost_info": cost_info,
                "cost_norm": cost_norm,
                "focus_norm": focus_norm,
                "proximity_norm": proximity_norm,
                "proximity_contributions": proximity_info["contributions"],
                "rating_norm": rating_norm,
                "score": score,
            }
        )

    ranked.sort(key=lambda item: (item["score"], item["quality_score"], item["candidate"].rating), reverse=True)
    recommendations: list[Recommendation] = []
    for rank, item in enumerate(ranked[: payload.k], 1):
        per_user = []
        for metric in item["metrics"]:
            user = user_by_id[metric.user_id]
            raw_duration = metric.duration_seconds / 60
            adjusted_duration = raw_duration * user.delta_weight
            per_user.append(
                PerUserDuration(
                    user_id=user.id,
                    label=user.label,
                    duration_minutes=round(adjusted_duration if payload.use_adjusted_durations else raw_duration, 1),
                    distance_km=round(metric.distance_meters / 1000, 2),
                    raw_duration_minutes=round(raw_duration, 1),
                    adjusted_duration_minutes=round(adjusted_duration, 1),
                    delta_weight=round(user.delta_weight, 2),
                )
            )
        per_user.sort(key=lambda row: row.user_id)
        if effective_scoring_mode == "criteria_delta":
            strongest_people = sorted(
                item["proximity_contributions"],
                key=lambda contribution: contribution.component,
                reverse=True,
            )[:2]
            people_text = ", ".join(
                f"{person.label} {person.distance_km:.1f} km"
                for person in strongest_people
            )
            explanation = (
                f"Puan {item['rating_norm']:.2f}, fiyat uygunluğu {item['cost_norm']:.2f} "
                f"ve kişi yakınlığı {item['proximity_norm']:.2f} skorlarıyla seçildi."
            )
            if people_text:
                explanation += f" Yakınlıkta en belirgin katkı: {people_text}."
        else:
            explanation = (
                f"En uzun yolculuk {item['t_max']:.1f} dk, toplam grup süresi {item['t_sum']:.1f} dk. "
                f"λ={effective_lambda:.2f}; kalite skoru yalnızca eşitlik bozucu/açıklama bileşeni olarak kullanıldı."
            )
        if payload.use_adjusted_durations and effective_scoring_mode != "criteria_delta":
            explanation += " Kişisel delta katsayıları süre metriklerine uygulandı."
        if effective_scoring_mode == "advanced_priority":
            explanation += " Gelişmiş kullanıcı öncelikleri final skora dahil edildi."
            if priority_weights.focus > 0:
                explanation += f" Odak yakınlığı {focus_source_label} yaklaşımıyla hesaplandı."
        directions_note = (
            "Etik kapsam gereği bağlantı yalnızca hedef mekânı içerir; "
            "başlangıç konumu Google Maps üzerinde kullanıcı tarafından seçilir."
        )
        min_rating_passed = payload.min_rating is None or item["candidate"].rating >= payload.min_rating
        max_duration_passed = (
            payload.max_duration_minutes is None
            or item["t_max"] <= payload.max_duration_minutes
        )
        recommendations.append(
            Recommendation(
                rank=rank,
                candidate=item["candidate"].model_copy(
                    update={"manual_cost": payload.manual_candidate_costs.get(item["candidate"].id)}
                ),
                score=round(item["score"], 4),
                fairness_norm=round(item["fairness_norm"], 4),
                efficiency_norm=round(item["efficiency_norm"], 4),
                quality_score=round(item["quality_score"], 4),
                t_avg_minutes=round(item["t_avg"], 2),
                t_sum_minutes=round(item["t_sum"], 2),
                t_max_minutes=round(item["t_max"], 2),
                variance_minutes=round(item["variance"], 2),
                per_user=per_user,
                explanation=explanation,
                directions_url=google_directions_url(item["candidate"], scenario.travel_mode),
                directions_note=directions_note,
                effective_weights=effective_weights,
                preference_source=preference_source,
                priority_profile=payload.priority_profile,
                score_breakdown=ScoreBreakdown(
                    fairness_component=round(effective_weights.fairness * item["fairness_norm"], 4),
                    efficiency_component=round(effective_weights.efficiency * item["efficiency_norm"], 4),
                    quality_component=round(priority_weights.quality * item["quality_score"], 4),
                    rating_component=round(criterion_weights.rating * item["rating_norm"], 4),
                    report_component=round(priority_weights.report * item["report_score"], 4),
                    cost_component=round(
                        (
                            criterion_weights.cost
                            if effective_scoring_mode == "criteria_delta"
                            else priority_weights.cost
                        )
                        * item["cost_norm"],
                        4,
                    ),
                    focus_component=round(priority_weights.focus * item["focus_norm"], 4),
                    proximity_component=round(criterion_weights.proximity * item["proximity_norm"], 4),
                    fairness_norm=round(item["fairness_norm"], 4),
                    efficiency_norm=round(item["efficiency_norm"], 4),
                    quality_norm=round(item["quality_score"], 4),
                    report_score=round(item["report_score"], 4),
                    cost_norm=round(item["cost_norm"], 4),
                    focus_norm=round(item["focus_norm"], 4),
                    proximity_norm=round(item["proximity_norm"], 4),
                    rating_norm=round(item["quality_info"]["rating_norm"], 4),
                    review_norm=round(item["quality_info"]["review_norm"], 4),
                    category_match=round(item["quality_info"]["category_match"], 4),
                    proximity_contributions=item["proximity_contributions"],
                ),
                constraint_status=ConstraintStatus(
                    category_match=item["quality_info"]["category_match"] > 0,
                    min_rating_passed=min_rating_passed,
                    max_duration_passed=max_duration_passed,
                    complete_route_matrix=len(item["metrics"]) == len(scenario.users),
                ),
                decision_mode=decision_mode,
                priority_weights=priority_weights,
                criterion_weights=criterion_weights,
                cost_source=_cost_source_label(str(item["cost_info"]["cost_source"])),
                focus_source="Kişi yakınlık ağırlıkları"
                if effective_scoring_mode == "criteria_delta"
                else focus_source_label,
                focus_mode="participant_delta"
                if effective_scoring_mode == "criteria_delta"
                else effective_focus_mode,
            )
        )

    run_id = str(uuid.uuid4())
    if not scenario.session_only:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO recommendation_runs (id, scenario_id, lambda_value, k, filters_json, results_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    payload.scenario_id,
                    effective_lambda if effective_lambda is not None else 0,
                    payload.k,
                    dump_json(
                        {
                            "max_duration_minutes": payload.max_duration_minutes,
                            "min_rating": payload.min_rating,
                            "category": payload.category,
                            "priority_profile": payload.priority_profile,
                            "advanced_preferences_enabled": payload.advanced_preferences_enabled,
                            "effective_weights": effective_weights.model_dump(),
                            "lambda_value": effective_lambda,
                            "preference_source": preference_source,
                            "advanced_priority_enabled": payload.advanced_priority_enabled,
                            "priority_weights": priority_weights.model_dump(),
                            "scoring_mode": effective_scoring_mode,
                            "criterion_weights": criterion_weights.model_dump(),
                            "participant_proximity_weights": participant_weights,
                            "use_adjusted_durations": payload.use_adjusted_durations,
                            "focus_user_id": payload.focus_user_id,
                            "focus_mode": effective_focus_mode,
                        }
                    ),
                    dump_json([recommendation.model_dump() for recommendation in recommendations]),
                ),
            )
    return RecommendationResponse(
        run_id=run_id,
        scenario=scenario,
        lambda_value=effective_lambda,
        effective_weights=effective_weights,
        preference_source=preference_source,
        priority_profile=payload.priority_profile,
        valid_alternatives=len(stats),
        recommendations=recommendations,
        decision_mode=decision_mode,
        priority_weights=priority_weights,
        criterion_weights=criterion_weights,
        focus_mode="participant_delta"
        if effective_scoring_mode == "criteria_delta"
        else effective_focus_mode,
    )
