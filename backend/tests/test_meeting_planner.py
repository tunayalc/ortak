import asyncio
import json
import sys
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

sys.path.append(str(Path(__file__).resolve().parents[1]))
from app.config import Settings
from app.main import app
from app.services import meeting_planner as planner
from app.services.preference_interpreter import PreferenceServiceError


def brief(**kwargs):
    return planner.PlanBrief(city="Ankara", group_size=3, **kwargs)


def test_missing_context_asks_instead_of_inventing():
    result = planner.recommend_plans(planner.PlanBrief())
    assert not result.plans
    assert len(result.questions) == 2


def test_numbered_neighborhood_is_not_treated_as_a_precise_address():
    assert brief(area="100. Yıl").area == "100. Yıl"


@pytest.mark.parametrize("environment,interests,minutes", [
    ("outdoor", ["nature"], 60), ("indoor", ["food"], 90),
    ("any", [], 30), ("any", ["study", "creative"], 360),
])
def test_constraints_steps_handoff_and_no_price_promises(environment, interests, minutes):
    result = planner.recommend_plans(brief(environment=environment, interests=interests, duration_minutes=minutes))
    assert result.plans
    for item in result.plans:
        assert sum(step.minutes for step in item.steps) == item.duration_minutes <= minutes
        assert all(step.minutes > 0 for step in item.steps)
        assert item.handoff.group_size == 3 and item.handoff.city == "Ankara"
        assert sum(item.handoff.criterion_weights.values()) == 100
        assert set(item.handoff.model_dump()) == {"city", "category", "group_size", "criterion_weights"}
        assert "price" not in item.model_dump()
        if interests:
            assert item.id in interests
        if environment == "outdoor":
            assert item.category == "park"


def test_no_silent_relaxation_of_incompatible_constraints():
    result = planner.recommend_plans(brief(environment="outdoor", interests=["study"], duration_minutes=30))
    assert result.plans == [] and result.questions


def test_budget_is_relative_not_cash_guarantee():
    result = planner.recommend_plans(brief(budget="low", area="Gölbaşı"))
    assert result.plans[0].category in {"park", "library"}
    assert all(plan.handoff.criterion_weights["cost"] == 60 for plan in result.plans)
    assert any("garantisi yoktur" in warning for warning in result.warnings)
    assert any("Semt" in warning for warning in result.warnings)


def test_production_participant_limit(monkeypatch):
    monkeypatch.setattr(planner, "get_settings", lambda: Settings(_env_file=None, APP_ENVIRONMENT="production", SESSION_SECRET="a" * 48, PUBLIC_BASE_URL="https://example.test", LLM_PROVIDER="ollama", OLLAMA_MODEL="llama3:8b"))
    result = planner.recommend_plans(planner.PlanBrief(city="Ankara", group_size=12))
    assert not result.plans and result.questions


@pytest.mark.parametrize("patch", [
    {"city": "39.92,32.85"}, {"area": "No: 8/15"}, {"group_size": 1},
    {"group_size": 2.5}, {"duration_minutes": 29}, {"duration_minutes": float("inf")},
    {"budget": "free"}, {"interests": ["fake_event"]}, {"unexpected": "data"},
])
def test_input_validation(patch):
    with pytest.raises(ValidationError):
        planner.PlanBrief.model_validate({**brief().model_dump(), **patch})


def call_model(monkeypatch, handler, text="Ankara'da üç arkadaş iki saat sohbet etmek istiyoruz."):
    monkeypatch.setattr(planner, "get_settings", lambda: Settings(_env_file=None, LLM_PROVIDER="ollama", OLLAMA_MODEL="llama3:8b"))
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await planner.interpret_plan(planner.PlanInterpretRequest(text=text), client)
    return asyncio.run(run())


def test_real_adapter_contract_and_authoritative_metadata(monkeypatch):
    sent = []
    def handler(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={"done": True, "done_reason": "stop", "model": "fake-model", "message": {"content": brief(interests=["conversation"]).model_dump_json()}})
    result = call_model(monkeypatch, handler)
    assert result.source == "ollama" and result.model == "llama3:8b"
    assert result.brief.group_size == 3
    assert sent[0]["stream"] is False
    assert sent[0]["options"]["temperature"] == 0
    assert sent[0]["format"]["additionalProperties"] is False


@pytest.mark.parametrize("response", [
    {"done": False}, {"done": True, "message": {"content": "invalid"}},
    {"done": True, "done_reason": "length", "message": {"content": "{}"}},
    {"done": True, "message": {"content": '{"group_size": 999}'}},
    {"done": True, "message": {"content": '{"source": "google"}'}},
    {"done": True, "message": {"content": '{}'}},
])
def test_invalid_model_outputs_fail_closed(monkeypatch, response):
    with pytest.raises(PreferenceServiceError):
        call_model(monkeypatch, lambda request: httpx.Response(200, json=response))


@pytest.mark.parametrize("text", ["39.92,32.85 konumundan geleceğiz", "https://maps.google.com üç kişi", "Evimin no: 8 adresindeyiz", "Bana test@example.com adresinden yaz"])
def test_precise_private_input_rejected_before_model(monkeypatch, text):
    def handler(request):
        pytest.fail("Private input should never reach model")
    with pytest.raises(PreferenceServiceError) as exc:
        call_model(monkeypatch, handler, text)
    assert exc.value.status_code == 400


def test_timeout_and_unavailable_model(monkeypatch):
    def handler(request):
        raise httpx.ReadTimeout("test")
    with pytest.raises(PreferenceServiceError) as exc:
        call_model(monkeypatch, handler)
    assert exc.value.status_code == 504
    monkeypatch.setattr(planner, "get_settings", lambda: Settings(_env_file=None, LLM_PROVIDER="disabled"))
    with pytest.raises(PreferenceServiceError) as exc:
        asyncio.run(planner.interpret_plan(planner.PlanInterpretRequest(text="Üç arkadaş buluşalım.")))
    assert exc.value.status_code == 503
    assert planner.recommend_plans(brief()).plans


def test_plan_endpoint_does_not_call_google_or_persist_scenarios(monkeypatch):
    from app import main
    def forbidden(*args, **kwargs):
        pytest.fail("Planner must not touch venue engine or persistence")
    for name in ["get_conn", "create_scenario", "search_candidates", "build_route_matrix", "recommend"]:
        monkeypatch.setattr(main, name, forbidden)
    response = TestClient(app).post("/plans/recommend", json=brief().model_dump())
    assert response.status_code == 200
    assert response.headers["x-ortak-google-calls"] == "0"
    assert response.json()["plans"]


def test_unmentioned_place_is_not_accepted_from_model(monkeypatch):
    def handler(request):
        invented = planner.PlanBrief(city="Antalya", area="Konyaaltı", group_size=3).model_dump_json()
        return httpx.Response(200, json={"done": True, "message": {"content": invented}})
    result = call_model(monkeypatch, handler, "Üç arkadaş sohbet etmek istiyoruz.")
    assert result.brief.city == "" and result.brief.area == ""
    assert planner.recommend_plans(result.brief).plans == []
