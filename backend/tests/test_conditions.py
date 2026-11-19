import asyncio
import json

import httpx
import pytest

from app.config import Settings
from app.schemas import UserConditions, RecommendationRequest
from app.services.conditions import read_conditions, explicit_criteria
from app.services import meeting_planner as planner
from app.services.scoring import recommend
from test_scoring import _seed_recommendation_case


@pytest.mark.parametrize("text,scope,amount", [
    ("Dört kişi toplam 2.000 TL", "group", 2000),
    ("kişi başı 500 TL", "per_person", 500),
    ("Toplam 1.250,50 lira", "group", 1250.5),
])
def test_explicit_money_units(text, scope, amount):
    result, questions = read_conditions(text, UserConditions())
    assert not questions
    assert result.budget_limit.scope == scope and result.budget_limit.amount == amount


@pytest.mark.parametrize("text", ["500 TL olsun", "toplam kişi başı 500 TL", "toplam 500 TL ya da 800 TL"])
def test_ambiguous_money_does_not_replace_previous_limit(text):
    previous = UserConditions(budget_limit={"amount": 1000, "scope": "group"})
    result, questions = read_conditions(text, previous)
    assert questions and result == previous


def test_conditions_survive_follow_up_and_explicit_exclusion():
    initial, _ = read_conditions("Toplam 2000 TL, müze olmasın, alkolsüz olsun", UserConditions())
    result, questions = read_conditions("daha sakin olsun", initial)
    assert not questions and result == initial
    assert result.excluded_categories == ["museum"]
    assert result.required_features == ["alcohol_free"]
    allowed, _ = read_conditions("müze olabilir", result)
    assert not allowed.excluded_categories and allowed.budget_limit == result.budget_limit


def test_price_level_never_proves_try_budget(monkeypatch, tmp_path):
    _seed_recommendation_case(monkeypatch, tmp_path)
    conditions = UserConditions(budget_limit={"amount": 600, "scope": "group"})
    result = recommend(RecommendationRequest(scenario_id="s1", conditions=conditions))
    assert result.recommendations == [] and result.conditions == conditions
    costs = {"c_eff": 250, "c_fair": 350, "c_quality": 800}
    result = recommend(RecommendationRequest(scenario_id="s1", conditions=conditions, manual_candidate_costs=costs))
    assert [r.candidate.id for r in result.recommendations] == ["c_eff"]
    conditions.budget_limit.scope = "per_person"
    result = recommend(RecommendationRequest(scenario_id="s1", conditions=conditions, manual_candidate_costs=costs))
    assert {r.candidate.id for r in result.recommendations} == {"c_eff", "c_fair"}


def test_unverified_feature_and_exclusions_fail_closed(monkeypatch, tmp_path):
    _seed_recommendation_case(monkeypatch, tmp_path)
    for condition in [{"required_features": ["quiet"]}, {"excluded_categories": ["cafe"]}]:
        result = recommend(RecommendationRequest(scenario_id="s1", conditions=condition))
        assert result.recommendations == []


def interpret(monkeypatch, text, current, returned, **kwargs):
    monkeypatch.setattr(planner, "get_settings", lambda: Settings(_env_file=None, LLM_PROVIDER="ollama"))
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={
            "done": True, "message": {"content": json.dumps(returned)},
        }))) as client:
            return await planner.interpret_plan(planner.PlanInterpretRequest(text=text, current=current, **kwargs), client)
    return asyncio.run(run())


def test_follow_up_cannot_change_unmentioned_fields(monkeypatch):
    current = planner.PlanBrief(city="Ankara", group_size=4, duration_minutes=180, pace="active",
                                conditions={"budget_limit": {"amount": 2000, "scope": "group"}, "excluded_categories": ["museum"]})
    hallucinated = planner.PlanBrief(city="İzmir", group_size=8, duration_minutes=60, pace="relaxed").model_dump()
    result = interpret(monkeypatch, "Daha sakin olsun, önceki bütçe kalsın", current, hallucinated)
    assert result.brief.city == "Ankara" and result.brief.group_size == 4
    assert result.brief.duration_minutes == 180 and result.brief.pace == "relaxed"
    assert result.brief.conditions == current.conditions


def test_new_topic_drops_previous_conditions(monkeypatch):
    current = planner.PlanBrief(city="Ankara", group_size=4, conditions={"excluded_categories": ["museum"]})
    result = interpret(monkeypatch, "Yeni bir buluşma: İzmir üç kişi", current,
                       planner.PlanBrief(city="İzmir", group_size=3).model_dump(), context_mode="new")
    assert result.brief.city == "İzmir" and result.brief.conditions == UserConditions()


def test_ordinal_uses_only_offered_plans(monkeypatch):
    current = planner.PlanBrief(city="Ankara", group_size=3)
    result = interpret(monkeypatch, "ikincisi", current, {}, offered_plan_ids=["food", "nature"])
    assert result.selected_plan_id == "nature" and result.brief == current
    unknown = interpret(monkeypatch, "ikincisi", current, {})
    assert unknown.selected_plan_id is None and unknown.questions


def test_plan_handoff_preserves_conditions():
    brief = planner.PlanBrief(city="Ankara", group_size=4, conditions={"budget_limit": {"amount": 2000, "scope": "group"}, "excluded_categories": ["cafe"]})
    result = planner.recommend_plans(brief)
    assert result.plans and all(plan.category != "cafe" for plan in result.plans)
    assert all(plan.handoff.conditions == brief.conditions for plan in result.plans)
    assert any("doğrulanamaz" in message for message in result.warnings)


def test_explicit_priority_numbers_are_not_replaced_by_preset():
    assert explicit_criteria("Puan ağırlığı yüzde 85 olsun") == {"rating": 85}
    assert explicit_criteria("Fiyat önemli, ağırlığı 80 olsun") == {}
    assert explicit_criteria("Fiyat ağırlığı 80 olsun") == {}
    assert explicit_criteria("Puan iki kat önemli olsun") == {}
    assert explicit_criteria("Puan önemli olmasın; fiyat önemli olsun") == {"rating": 10, "cost": 70}
    with pytest.raises(ValueError, match="çelişen"):
        explicit_criteria("Puan önemli olsun; puan önemli olmasın")


def test_previous_selection_uses_displayed_order(monkeypatch):
    current = planner.PlanBrief(city="Ankara", group_size=3)
    result = interpret(monkeypatch, "bunu değil öncekini", current, {}, offered_plan_ids=["food", "nature"], selected_plan_id="nature")
    assert result.selected_plan_id == "food"


def test_coordinated_exclusions_and_negated_hard_conditions():
    result, questions = read_conditions("Kafe ve restoran olmasın", UserConditions())
    assert set(result.excluded_categories) == {"cafe", "restaurant"} and not questions
    prior = UserConditions(required_features=["quiet", "alcohol_free"])
    result, questions = read_conditions("Sessiz olması zorunlu değil", prior)
    assert result.required_features == ["alcohol_free"] and not questions
    result, questions = read_conditions("Alkolsüz olmasın", prior)
    assert questions and result == prior


def test_missing_rating_and_mixed_price_units_are_neutral():
    from app.services.scoring import _quality_details, _cost_details
    from app.schemas import PlaceCandidate
    base = dict(scenario_id="s", place_id="test", name="Test", address="", category="cafe", lat=39.9, lng=32.8, review_count=0, provider="synthetic")
    candidates = [PlaceCandidate(id="a", rating=0, price_level=2, **base), PlaceCandidate(id="b", rating=4, **base)]
    assert _quality_details(candidates, "cafe")["a"]["rating_norm"] == 0.5
    costs = _cost_details(candidates, {"b": 200})
    assert costs["a"]["cost_norm"] == costs["b"]["cost_norm"] == 0.5
    assert costs["a"]["cost_source"] == "synthetic_price_level" and costs["b"]["cost_source"] == "manual"


def test_typo_evidence_is_grounded_without_accepting_unrelated_priority():
    from app.schemas import PreferenceInterpretRequest
    from app.services.preference_edits import apply_edits
    text = "Fyat uygunlğu daha önmli olsun."
    request = PreferenceInterpretRequest(text=text, participants=[{"id": "user-1", "label": "A"}, {"id": "user-2", "label": "B"}])
    raw = {"edits": [{"target": "cost", "person_id": None, "value": 70, "evidence": "Fyat uygunlğu daha önmli"}]}
    result = apply_edits(raw, request, text)
    assert result["criterion_weights"] == {"rating": 34, "cost": 70, "proximity": 33}
    raw["edits"][0]["evidence"] = "Güzel bir gün olsun"
    with pytest.raises(ValueError):
        apply_edits(raw, request, "Güzel bir gün olsun")
