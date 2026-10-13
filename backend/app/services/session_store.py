from __future__ import annotations

import time
from dataclasses import dataclass, field

from ..schemas import PlaceCandidate, RouteMetric, Scenario
from ..config import get_settings
from .request_context import current_session


SESSION_TTL_SECONDS = 2 * 60 * 60


@dataclass
class SessionScenarioBundle:
    scenario: Scenario
    expires_at: float
    owner: str | None = None
    candidates: list[PlaceCandidate] = field(default_factory=list)
    routes: list[RouteMetric] = field(default_factory=list)


_SESSION_SCENARIOS: dict[str, SessionScenarioBundle] = {}


def _now() -> float:
    return time.time()


def cleanup_expired() -> None:
    now = _now()
    expired = [
        scenario_id
        for scenario_id, bundle in _SESSION_SCENARIOS.items()
        if bundle.expires_at <= now
    ]
    for scenario_id in expired:
        _SESSION_SCENARIOS.pop(scenario_id, None)


def put_scenario(scenario: Scenario) -> None:
    cleanup_expired()
    ensure_capacity()
    _SESSION_SCENARIOS[scenario.id] = SessionScenarioBundle(
        scenario=scenario,
        expires_at=_now() + SESSION_TTL_SECONDS - 60,
        owner=current_session.get(),
    )


def ensure_capacity() -> None:
    cleanup_expired()
    if not get_settings().production:
        return
    owner = current_session.get()
    if owner is None:
        raise ValueError("Geçerli bir oturum gereklidir.")
    owned = sum(bundle.owner == owner for bundle in _SESSION_SCENARIOS.values())
    if len(_SESSION_SCENARIOS) >= 100 or owned >= 2:
        raise ValueError("Oturum kapasitesi doldu. Önce mevcut senaryonuzu silin; yeni Google çağrısı yapılmadı.")


def _bundle(scenario_id: str) -> SessionScenarioBundle | None:
    cleanup_expired()
    bundle = _SESSION_SCENARIOS.get(scenario_id)
    if bundle is not None and get_settings().production and bundle.owner != current_session.get():
        return None
    return bundle


def delete_scenario(scenario_id: str) -> bool:
    if _bundle(scenario_id) is None:
        return False
    _SESSION_SCENARIOS.pop(scenario_id, None)
    return True


def get_scenario(scenario_id: str) -> Scenario | None:
    bundle = _bundle(scenario_id)
    if bundle is None:
        return None
    return bundle.scenario


def is_session_scenario(scenario_id: str) -> bool:
    return get_scenario(scenario_id) is not None


def list_candidates(scenario_id: str) -> list[PlaceCandidate] | None:
    bundle = _bundle(scenario_id)
    if bundle is None:
        return None
    return list(bundle.candidates)


def save_candidates(scenario_id: str, candidates: list[PlaceCandidate]) -> bool:
    bundle = _bundle(scenario_id)
    if bundle is None:
        return False
    bundle.candidates = list(candidates)
    return True


def list_routes(scenario_id: str) -> list[RouteMetric] | None:
    bundle = _bundle(scenario_id)
    if bundle is None:
        return None
    return list(bundle.routes)


def save_route(metric: RouteMetric) -> bool:
    bundle = _bundle(metric.scenario_id)
    if bundle is None:
        return False
    bundle.routes = [
        route
        for route in bundle.routes
        if not (
            route.user_id == metric.user_id
            and route.candidate_id == metric.candidate_id
        )
    ]
    bundle.routes.append(metric)
    return True
