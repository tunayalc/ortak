from __future__ import annotations

import math
import random

from ..schemas import (
    BaselineResult,
    ExperimentRequest,
    ExperimentResponse,
    ExperimentStatistic,
    RecommendationRequest,
    TargetCheck,
)
from .geo import centroid, haversine_m
from .google_maps import list_candidates, list_route_metrics
from .scenario import get_scenario
from .scoring import recommend


PROFILE_LABELS = {
    "balanced": "Dengeli",
    "fairness": "Daha Adil",
    "efficiency": "Daha Kısa",
    "quality": "Dengeli",
}


def _pct_delta(model_value: float, baseline_value: float) -> float | None:
    if baseline_value == 0:
        return None
    return round(((model_value - baseline_value) / baseline_value) * 100, 2)


def _metric_for_candidate(candidate_id: str, metrics: list) -> dict[str, float]:
    durations = [metric.duration_seconds / 60 for metric in metrics if metric.candidate_id == candidate_id]
    if not durations:
        return {"t_avg": 0, "t_sum": 0, "t_max": 0, "variance": 0}
    avg = sum(durations) / len(durations)
    variance = sum((value - avg) ** 2 for value in durations) / len(durations)
    return {"t_avg": avg, "t_sum": sum(durations), "t_max": max(durations), "variance": variance}


def _metric_for_user_durations(durations_by_user: dict[str, float]) -> dict[str, float]:
    durations = list(durations_by_user.values())
    if not durations:
        return {"t_avg": 0, "t_sum": 0, "t_max": 0, "variance": 0}
    avg = sum(durations) / len(durations)
    variance = sum((value - avg) ** 2 for value in durations) / len(durations)
    return {"t_avg": avg, "t_sum": sum(durations), "t_max": max(durations), "variance": variance}


def _durations_by_user(candidate_id: str, metrics: list) -> dict[str, float]:
    return {
        metric.user_id: metric.duration_seconds / 60
        for metric in metrics
        if metric.candidate_id == candidate_id
    }


def _complete_candidates(candidates: list, metrics: list, user_count: int) -> list:
    return [
        candidate
        for candidate in candidates
        if len(_durations_by_user(candidate.id, metrics)) == user_count
    ]


def _rank_abs(values: list[float]) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    position = 0
    while position < len(indexed):
        end = position
        while end + 1 < len(indexed) and indexed[end + 1][1] == indexed[position][1]:
            end += 1
        average_rank = (position + 1 + end + 1) / 2
        for offset in range(position, end + 1):
            ranks[indexed[offset][0]] = average_rank
        position = end + 1
    return ranks


def _wilcoxon_signed_rank(differences: list[float]) -> tuple[float | None, float | None]:
    non_zero = [value for value in differences if abs(value) > 1e-9]
    sample_size = len(non_zero)
    if sample_size == 0:
        return None, None
    ranks = _rank_abs([abs(value) for value in non_zero])
    w_positive = sum(rank for rank, value in zip(ranks, non_zero) if value > 0)
    w_negative = sum(rank for rank, value in zip(ranks, non_zero) if value < 0)
    w_stat = min(w_positive, w_negative)
    if sample_size < 2:
        return round(w_stat, 4), None
    mean = sample_size * (sample_size + 1) / 4
    variance = sample_size * (sample_size + 1) * (2 * sample_size + 1) / 24
    z_score = (abs(w_stat - mean) - 0.5) / math.sqrt(variance)
    p_value = math.erfc(abs(z_score) / math.sqrt(2))
    return round(w_stat, 4), round(p_value, 4)


def _cohens_dz(differences: list[float]) -> float | None:
    if len(differences) < 2:
        return None
    mean = sum(differences) / len(differences)
    variance = sum((value - mean) ** 2 for value in differences) / (len(differences) - 1)
    if variance == 0:
        return None
    return round(mean / math.sqrt(variance), 4)


def _paired_statistics(
    method: str,
    model_by_user: dict[str, float],
    baseline_by_user: dict[str, float],
) -> ExperimentStatistic:
    differences = [
        baseline_by_user[user_id] - model_duration
        for user_id, model_duration in model_by_user.items()
        if user_id in baseline_by_user
    ]
    if not differences:
        return ExperimentStatistic(
            baseline_method=method,
            wilcoxon_w=None,
            approximate_p_value=None,
            effect_size_dz=None,
            mean_paired_improvement_minutes=0,
            interpretation="Eşleşmiş kullanıcı süreleri bulunamadı.",
        )
    w_stat, p_value = _wilcoxon_signed_rank(differences)
    effect = _cohens_dz(differences)
    mean_improvement = sum(differences) / len(differences)
    direction = "iyileşme" if mean_improvement > 0 else "kötüleşme" if mean_improvement < 0 else "eşitlik"
    return ExperimentStatistic(
        baseline_method=method,
        wilcoxon_w=w_stat,
        approximate_p_value=p_value,
        effect_size_dz=effect,
        mean_paired_improvement_minutes=round(mean_improvement, 2),
        interpretation=(
            f"Model bu temel yönteme göre kişi başına ortalama {abs(mean_improvement):.2f} dk "
            f"{direction} gösteriyor."
        ),
    )


def run_experiment(payload: ExperimentRequest) -> ExperimentResponse:
    scenario = get_scenario(payload.scenario_id)
    candidates = list_candidates(payload.scenario_id)
    metrics = list_route_metrics(payload.scenario_id)
    if not candidates or not metrics:
        raise ValueError("Deneylerden önce aday arama ve rota matrisi çalıştırılmalıdır.")
    valid_candidates = _complete_candidates(candidates, metrics, len(scenario.users))
    if len(valid_candidates) < 3:
        raise ValueError("Deney için en az üç tam rota matrisli geçerli alternatif gereklidir.")

    model_response = recommend(
        RecommendationRequest(
            scenario_id=payload.scenario_id,
            scoring_mode=payload.scoring_mode,
            lambda_value=payload.lambda_value,
            k=payload.k,
            priority_profile=payload.priority_profile,
            fairness_weight=payload.fairness_weight,
            efficiency_weight=payload.efficiency_weight,
            quality_weight=payload.quality_weight,
            advanced_preferences_enabled=payload.advanced_preferences_enabled,
            advanced_priority_enabled=payload.advanced_priority_enabled,
            priority_weights=payload.priority_weights,
            criterion_weights=payload.criterion_weights,
            participant_proximity_weights=payload.participant_proximity_weights,
            manual_candidate_costs=payload.manual_candidate_costs,
            focus_location=payload.focus_location,
            focus_user_id=payload.focus_user_id,
            focus_mode=payload.focus_mode,
            use_adjusted_durations=payload.use_adjusted_durations,
        )
    )
    model_top = model_response.recommendations[0]
    model_metrics = {
        "t_avg": model_top.t_avg_minutes,
        "t_sum": model_top.t_sum_minutes,
        "t_max": model_top.t_max_minutes,
        "variance": model_top.variance_minutes,
    }
    model_by_user = {
        item.user_id: item.duration_minutes
        for item in model_top.per_user
    }

    scenario_centroid = centroid(scenario.users)
    center_candidate = min(
        valid_candidates,
        key=lambda candidate: haversine_m(scenario_centroid[0], scenario_centroid[1], candidate.lat, candidate.lng),
    )
    min_sum_candidate = min(valid_candidates, key=lambda candidate: _metric_for_candidate(candidate.id, metrics)["t_sum"])
    min_max_candidate = min(valid_candidates, key=lambda candidate: _metric_for_candidate(candidate.id, metrics)["t_max"])
    rng = random.Random(f"{scenario.seed}:{payload.scenario_id}:{payload.random_repeats}")
    random_choices = [rng.choice(valid_candidates) for _ in range(payload.random_repeats)]
    random_user_values: dict[str, list[float]] = {user.id: [] for user in scenario.users}
    for candidate in random_choices:
        for user_id, duration in _durations_by_user(candidate.id, metrics).items():
            random_user_values[user_id].append(duration)
    random_by_user = {
        user_id: sum(values) / len(values)
        for user_id, values in random_user_values.items()
        if values
    }
    random_metrics = _metric_for_user_durations(random_by_user)

    baseline_defs = [
        ("ORTAK tercih modeli", model_top.candidate, model_metrics, model_by_user, None),
        (
            "Rastgele seçim ortalaması",
            None,
            random_metrics,
            random_by_user,
            payload.random_repeats,
        ),
        (
            "Coğrafi merkez",
            center_candidate,
            _metric_for_candidate(center_candidate.id, metrics),
            _durations_by_user(center_candidate.id, metrics),
            None,
        ),
        (
            "Minimum-toplam süre",
            min_sum_candidate,
            _metric_for_candidate(min_sum_candidate.id, metrics),
            _durations_by_user(min_sum_candidate.id, metrics),
            None,
        ),
        (
            "Minimum-maksimum süre",
            min_max_candidate,
            _metric_for_candidate(min_max_candidate.id, metrics),
            _durations_by_user(min_max_candidate.id, metrics),
            None,
        ),
    ]
    results: list[BaselineResult] = []
    statistics: list[ExperimentStatistic] = []
    target_checks: list[TargetCheck] = []
    for method, candidate, values, durations_by_user, repeat_count in baseline_defs:
        result = BaselineResult(
            method=method,
            candidate_name=candidate.name if candidate is not None else "Çoklu rastgele tekrar",
            t_avg_minutes=round(values["t_avg"], 2),
            t_sum_minutes=round(values["t_sum"], 2),
            t_max_minutes=round(values["t_max"], 2),
            variance_minutes=round(values["variance"], 2),
            delta_t_max_pct=None
            if method == "ORTAK tercih modeli"
            else _pct_delta(model_metrics["t_max"], values["t_max"]),
            delta_t_avg_pct=None
            if method == "ORTAK tercih modeli"
            else _pct_delta(model_metrics["t_avg"], values["t_avg"]),
            delta_variance_pct=None
            if method == "ORTAK tercih modeli"
            else _pct_delta(model_metrics["variance"], values["variance"]),
            repeat_count=repeat_count,
        )
        results.append(result)
        if method != "ORTAK tercih modeli":
            statistics.append(
                _paired_statistics(method, model_by_user, durations_by_user)
            )
            target_checks.append(
                TargetCheck(
                    baseline_method=method,
                    max_duration_target_met=(
                        result.delta_t_max_pct is not None and result.delta_t_max_pct <= -15
                    ),
                    average_duration_target_met=(
                        result.delta_t_avg_pct is not None and result.delta_t_avg_pct <= 5
                    ),
                    variance_target_met=(
                        result.delta_variance_pct is not None and result.delta_variance_pct <= -15
                    ),
                )
            )

    improved = [
        item
        for item in results[1:]
        if item.delta_t_max_pct is not None and item.delta_t_max_pct <= -15
    ]
    summary = (
        f"{model_top.candidate.name} seçildi. {PROFILE_LABELS.get(model_response.priority_profile, model_response.priority_profile)} profiliyle model, "
        f"{len(improved)} temel yöntem karşısında maksimum bireysel sürede hedeflenen %15 iyileşmeyi yakaladı."
    )
    return ExperimentResponse(
        scenario_id=payload.scenario_id,
        selected_model_candidate=model_top.candidate.name,
        valid_alternatives=model_response.valid_alternatives,
        effective_weights=model_response.effective_weights,
        preference_source=model_response.preference_source,
        priority_profile=model_response.priority_profile,
        baselines=results,
        statistics=statistics,
        target_checks=target_checks,
        summary=summary,
    )
