from __future__ import annotations

from typing import Optional

from pydantic import BaseModel as PydanticModel, ConfigDict, Field, field_validator


class BaseModel(PydanticModel):
    model_config = ConfigDict(allow_inf_nan=False)


class Coordinate(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class SyntheticUser(BaseModel):
    id: str = Field(max_length=80)
    label: str = Field(min_length=1, max_length=80)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    source: str = "synthetic"
    location_input_type: str = "synthetic"
    delta_weight: float = Field(default=1.0, ge=0.5, le=2.0)


class ParticipantLocationInput(BaseModel):
    label: str = Field(max_length=80)
    value: str = Field(max_length=2048)
    delta_weight: float = Field(default=1.0, ge=0.5, le=2.0)


class ParsedLocation(BaseModel):
    label: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    source: str
    location_input_type: str
    delta_weight: float = Field(default=1.0, ge=0.5, le=2.0)
    error: Optional[str] = None


class LocationParseRequest(BaseModel):
    items: list[ParticipantLocationInput] = Field(default_factory=list, min_length=1, max_length=12)


class ScenarioCreate(BaseModel):
    city: str = Field(default="Ankara", min_length=1, max_length=80)
    category: str = Field(default="cafe", min_length=1, max_length=80)
    group_size: int = Field(default=5, ge=2, le=12)
    travel_mode: str = "driving"
    radius_m: int = Field(default=2500, ge=500, le=15000)
    seed: int = Field(default=42, ge=0)
    users: Optional[list[SyntheticUser]] = Field(default=None, min_length=2, max_length=12)
    synthetic_fixture: bool = False
    input_mode: str = "synthetic"
    session_only: bool = False
    participant_locations: Optional[list[ParticipantLocationInput]] = Field(default=None, min_length=2, max_length=12)

    @field_validator("travel_mode")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        allowed = {"driving", "walking", "transit", "bicycling"}
        normalized = value.lower().strip()
        if normalized not in allowed:
            raise ValueError(f"travel_mode must be one of {sorted(allowed)}")
        return normalized

    @field_validator("input_mode")
    @classmethod
    def validate_input_mode(cls, value: str) -> str:
        allowed = {"synthetic", "link"}
        normalized = value.lower().strip()
        if normalized not in allowed:
            raise ValueError(f"input_mode must be one of {sorted(allowed)}")
        return normalized


class Scenario(BaseModel):
    id: str
    city: str
    category: str
    group_size: int
    travel_mode: str
    radius_m: int
    seed: int
    users: list[SyntheticUser]
    session_only: bool = False
    input_mode: str = "synthetic"


class CandidateSearchRequest(BaseModel):
    scenario_id: str
    max_results: int = Field(default=12, ge=3, le=30)
    radius_m: Optional[int] = Field(default=None, ge=500, le=15000)


class PlaceCandidate(BaseModel):
    id: str
    scenario_id: str
    place_id: str
    name: str
    address: str
    category: str
    rating: float
    review_count: int
    lat: float
    lng: float
    provider: str
    price_level: Optional[int] = Field(default=None, ge=0, le=4)
    manual_cost: Optional[float] = Field(default=None, ge=0)
    attributions: list[dict[str, str]] = Field(default_factory=list)


class RouteMatrixRequest(BaseModel):
    scenario_id: str
    provider: str = "auto"

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        allowed = {"auto", "google", "osrm", "synthetic"}
        normalized = value.lower().strip()
        if normalized not in allowed:
            raise ValueError(f"provider must be one of {sorted(allowed)}")
        return normalized


class RouteMetric(BaseModel):
    id: str
    scenario_id: str
    user_id: str
    candidate_id: str
    duration_seconds: float
    distance_meters: float
    provider: str


class PriorityWeights(BaseModel):
    report: float = Field(default=70, ge=0)
    quality: float = Field(default=10, ge=0)
    cost: float = Field(default=10, ge=0)
    focus: float = Field(default=10, ge=0)


class CriterionWeights(BaseModel):
    rating: float = Field(default=34, ge=0)
    cost: float = Field(default=33, ge=0)
    proximity: float = Field(default=33, ge=0)


class PreferenceParticipant(BaseModel):
    id: str = Field(pattern=r"^user-[1-9][0-9]?$", max_length=40)
    label: str = Field(min_length=1, max_length=80)
    delta_weight: float = Field(default=1.0, ge=0.5, le=2.0)


class PreferenceInterpretRequest(BaseModel):
    text: str = Field(min_length=5, max_length=500)
    participants: list[PreferenceParticipant] = Field(min_length=2, max_length=12)
    criterion_weights: CriterionWeights = Field(default_factory=CriterionWeights)
    min_rating: Optional[float] = Field(default=None, ge=0, le=5)
    max_duration_minutes: Optional[float] = Field(default=None, ge=1)


class PreferenceSuggestion(BaseModel):
    criterion_weights: CriterionWeights
    participant_proximity_weights: dict[str, float]
    min_rating: Optional[float] = Field(default=None, ge=0, le=5)
    max_duration_minutes: Optional[float] = Field(default=None, ge=1)
    explanation: str
    warnings: list[str] = Field(default_factory=list)
    source: str = "ollama"
    model: str = ""


class RecommendationRequest(BaseModel):
    scenario_id: str
    scoring_mode: str = "criteria_delta"
    lambda_value: Optional[float] = Field(default=None, ge=0, le=1)
    k: int = Field(default=5, ge=1, le=20)
    max_duration_minutes: Optional[float] = Field(default=None, ge=1)
    min_rating: Optional[float] = Field(default=None, ge=0, le=5)
    category: Optional[str] = None
    priority_profile: str = "balanced"
    fairness_weight: Optional[float] = Field(default=None, ge=0)
    efficiency_weight: Optional[float] = Field(default=None, ge=0)
    quality_weight: Optional[float] = Field(default=None, ge=0)
    advanced_preferences_enabled: bool = False
    advanced_priority_enabled: bool = False
    priority_weights: PriorityWeights = Field(default_factory=PriorityWeights)
    criterion_weights: CriterionWeights = Field(default_factory=CriterionWeights)
    participant_proximity_weights: dict[str, float] = Field(default_factory=dict)
    manual_candidate_costs: dict[str, float] = Field(default_factory=dict)
    focus_location: Optional[Coordinate] = None
    focus_user_id: Optional[str] = None
    focus_mode: Optional[str] = None
    use_adjusted_durations: bool = False

    @field_validator("priority_profile")
    @classmethod
    def validate_priority_profile(cls, value: str) -> str:
        allowed = {"balanced", "fairness", "efficiency", "quality"}
        normalized = value.lower().strip()
        if normalized not in allowed:
            raise ValueError(f"priority_profile must be one of {sorted(allowed)}")
        return normalized

    @field_validator("scoring_mode")
    @classmethod
    def validate_scoring_mode(cls, value: str) -> str:
        allowed = {"criteria_delta", "report_lambda", "advanced_priority"}
        normalized = value.lower().strip()
        if normalized not in allowed:
            raise ValueError(f"scoring_mode must be one of {sorted(allowed)}")
        return normalized

    @field_validator("focus_mode")
    @classmethod
    def validate_focus_mode(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        allowed = {
            "none",
            "delta_weighted_participants",
            "single_user",
            "custom_location",
            "custom_location_and_delta",
        }
        normalized = value.lower().strip()
        if normalized not in allowed:
            raise ValueError(f"focus_mode must be one of {sorted(allowed)}")
        return normalized


class PerUserDuration(BaseModel):
    user_id: str
    label: str
    duration_minutes: float
    distance_km: float
    raw_duration_minutes: float
    adjusted_duration_minutes: float
    delta_weight: float


class EffectiveWeights(BaseModel):
    fairness: float
    efficiency: float
    quality: float


class ProximityContribution(BaseModel):
    user_id: str
    label: str
    weight: float
    closeness_norm: float
    component: float
    distance_km: float


class ScoreBreakdown(BaseModel):
    fairness_component: float
    efficiency_component: float
    quality_component: float
    rating_component: float = 0.0
    report_component: float = 0.0
    cost_component: float = 0.0
    focus_component: float = 0.0
    proximity_component: float = 0.0
    fairness_norm: float
    efficiency_norm: float
    quality_norm: float
    report_score: float = 0.0
    cost_norm: float = 0.5
    focus_norm: float = 0.5
    proximity_norm: float = 0.5
    rating_norm: float
    review_norm: float
    category_match: float
    proximity_contributions: list[ProximityContribution] = Field(default_factory=list)


class ConstraintStatus(BaseModel):
    category_match: bool
    min_rating_passed: bool
    max_duration_passed: bool
    complete_route_matrix: bool


class Recommendation(BaseModel):
    rank: int
    candidate: PlaceCandidate
    score: float
    fairness_norm: float
    efficiency_norm: float
    quality_score: float
    t_avg_minutes: float
    t_sum_minutes: float
    t_max_minutes: float
    variance_minutes: float
    per_user: list[PerUserDuration]
    explanation: str
    directions_url: str
    directions_note: str
    effective_weights: EffectiveWeights
    preference_source: str
    priority_profile: str
    score_breakdown: ScoreBreakdown
    constraint_status: ConstraintStatus
    decision_mode: str = "report_lambda"
    priority_weights: PriorityWeights = Field(default_factory=PriorityWeights)
    criterion_weights: CriterionWeights = Field(default_factory=CriterionWeights)
    cost_source: str = "none"
    focus_source: str = "none"
    focus_mode: str = "none"


class RecommendationResponse(BaseModel):
    run_id: str
    scenario: Scenario
    lambda_value: Optional[float]
    effective_weights: EffectiveWeights
    preference_source: str
    priority_profile: str
    valid_alternatives: int
    recommendations: list[Recommendation]
    decision_mode: str = "report_lambda"
    priority_weights: PriorityWeights = Field(default_factory=PriorityWeights)
    criterion_weights: CriterionWeights = Field(default_factory=CriterionWeights)
    focus_mode: str = "none"


class ExperimentRequest(BaseModel):
    scenario_id: str
    scoring_mode: str = "criteria_delta"
    lambda_value: Optional[float] = Field(default=None, ge=0, le=1)
    k: int = Field(default=5, ge=1, le=20)
    priority_profile: str = "balanced"
    fairness_weight: Optional[float] = Field(default=None, ge=0)
    efficiency_weight: Optional[float] = Field(default=None, ge=0)
    quality_weight: Optional[float] = Field(default=None, ge=0)
    advanced_preferences_enabled: bool = False
    random_repeats: int = Field(default=30, ge=5, le=200)
    advanced_priority_enabled: bool = False
    priority_weights: PriorityWeights = Field(default_factory=PriorityWeights)
    criterion_weights: CriterionWeights = Field(default_factory=CriterionWeights)
    participant_proximity_weights: dict[str, float] = Field(default_factory=dict)
    manual_candidate_costs: dict[str, float] = Field(default_factory=dict)
    focus_location: Optional[Coordinate] = None
    focus_user_id: Optional[str] = None
    focus_mode: Optional[str] = None
    use_adjusted_durations: bool = False

    @field_validator("priority_profile")
    @classmethod
    def validate_experiment_profile(cls, value: str) -> str:
        allowed = {"balanced", "fairness", "efficiency", "quality"}
        normalized = value.lower().strip()
        if normalized not in allowed:
            raise ValueError(f"priority_profile must be one of {sorted(allowed)}")
        return normalized

    @field_validator("scoring_mode")
    @classmethod
    def validate_experiment_scoring_mode(cls, value: str) -> str:
        allowed = {"criteria_delta", "report_lambda", "advanced_priority"}
        normalized = value.lower().strip()
        if normalized not in allowed:
            raise ValueError(f"scoring_mode must be one of {sorted(allowed)}")
        return normalized

    @field_validator("focus_mode")
    @classmethod
    def validate_experiment_focus_mode(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        allowed = {
            "none",
            "delta_weighted_participants",
            "single_user",
            "custom_location",
            "custom_location_and_delta",
        }
        normalized = value.lower().strip()
        if normalized not in allowed:
            raise ValueError(f"focus_mode must be one of {sorted(allowed)}")
        return normalized


class BaselineResult(BaseModel):
    method: str
    candidate_name: str
    t_avg_minutes: float
    t_sum_minutes: float
    t_max_minutes: float
    variance_minutes: float
    delta_t_max_pct: Optional[float]
    delta_t_avg_pct: Optional[float]
    delta_variance_pct: Optional[float]
    repeat_count: Optional[int] = None


class ExperimentStatistic(BaseModel):
    baseline_method: str
    wilcoxon_w: Optional[float]
    approximate_p_value: Optional[float]
    effect_size_dz: Optional[float]
    mean_paired_improvement_minutes: float
    interpretation: str


class TargetCheck(BaseModel):
    baseline_method: str
    max_duration_target_met: bool
    average_duration_target_met: bool
    variance_target_met: bool


class ExperimentResponse(BaseModel):
    scenario_id: str
    selected_model_candidate: str
    valid_alternatives: int
    effective_weights: EffectiveWeights
    preference_source: str
    priority_profile: str
    baselines: list[BaselineResult]
    statistics: list[ExperimentStatistic]
    target_checks: list[TargetCheck]
    summary: str
