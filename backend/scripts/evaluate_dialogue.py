"""Explicit local Llama acceptance; no Google calls, persisted prompts or model downloads."""
import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import Settings, get_settings
from app.schemas import PreferenceInterpretRequest, UserConditions
from app.services.meeting_planner import PlanBrief, PlanInterpretRequest, interpret_plan, recommend_plans
from app.services.preference_interpreter import interpret_preferences


async def main():
    Settings.model_config["env_file"] = None
    import os
    os.environ.update(LLM_PROVIDER="ollama", OLLAMA_MODEL="llama3:8b", GOOGLE_MAPS_API_KEY="", GOOGLE_MAPS_CALLS_ENABLED="false")
    get_settings.cache_clear()
    rows = []
    current = PlanBrief(city="Ankara", group_size=4, duration_minutes=120, pace="active",
                        conditions=UserConditions(budget_limit={"amount": 2000, "scope": "group"}, excluded_categories=["museum"]))
    cases = [
        ("simple", "Ankara'da üç arkadaş bir saat sohbet edelim.", PlanBrief(), {}, lambda r: r.brief.city == "Ankara" and r.brief.group_size == 3 and r.brief.duration_minutes == 60),
        ("typo", "ankarada uc kisi ekonomik biseyler yapalim", PlanBrief(), {}, lambda r: r.brief.group_size == 3 and r.brief.budget == "low"),
        ("total_budget", "Ankara'da dört kişi toplam 2.000 TL, müze olmasın.", PlanBrief(), {}, lambda r: r.brief.conditions.budget_limit.amount == 2000 and r.brief.conditions.budget_limit.scope == "group" and "museum" in r.brief.conditions.excluded_categories),
        ("per_person", "Kişi başı 500 TL olsun.", current, {}, lambda r: r.brief.conditions.budget_limit.scope == "per_person" and r.brief.group_size == 4),
        ("follow_up", "Daha sakin olsun, önceki bütçe kalsın.", current, {}, lambda r: r.brief.pace == "relaxed" and r.brief.group_size == 4 and r.brief.conditions == current.conditions),
        ("ambiguous_person", "O kişi gelmeyecek.", current, {}, lambda r: bool(r.questions) and r.brief.group_size == 4),
        ("ambiguous_budget", "500 TL olsun.", current, {}, lambda r: bool(r.questions) and r.brief.conditions == current.conditions),
        ("new_topic", "Yeni bir buluşma: İzmir, iki kişi yemek yiyelim.", current, {"context_mode": "new"}, lambda r: r.brief.city == "İzmir" and r.brief.group_size == 2 and not r.brief.conditions.budget_limit),
        ("ordinal", "ikincisi", current, {"offered_plan_ids": ["food", "nature"]}, lambda r: r.selected_plan_id == "nature"),
        ("conflict", "Hem açık alan hem kapalı alan zorunlu olsun.", current, {}, lambda r: bool(r.questions)),
    ]
    for name, text, context, extra, check in cases:
        started = time.monotonic()
        try:
            result = await interpret_plan(PlanInterpretRequest(text=text, current=context, **extra))
            passed = bool(check(result))
            plans = recommend_plans(result.brief)
            passed = passed and all(plan.category not in result.brief.conditions.excluded_categories for plan in plans.plans)
            row = {"case": name, "passed": passed, "failure_layer": None if passed else "interpretation_or_context"}
            if not passed:
                row["actual"] = result.brief.model_dump(exclude={"city", "area"})
        except Exception as exc:
            row = {"case": name, "passed": False, "failure_layer": "adapter_or_validation", "error_type": type(exc).__name__}
        row["seconds"] = round(time.monotonic() - started, 2)
        rows.append(row)
        print(json.dumps(row), flush=True)
    conversation = PlanBrief()
    for name, text, check in [
        ("chain_initial", "Ankara'da üç kişi toplam 1500 TL ile buluşalım, müze olmasın.", lambda b: b.city == "Ankara" and b.group_size == 3 and b.conditions.budget_limit.amount == 1500 and "museum" in b.conditions.excluded_categories),
        ("chain_follow_up", "Daha sakin olsun, önceki bütçe kalsın.", lambda b: b.city == "Ankara" and b.group_size == 3 and b.conditions.budget_limit.amount == 1500 and "museum" in b.conditions.excluded_categories and b.pace == "relaxed"),
        ("chain_new_topic", "Yeni konu: İzmir, iki kişi yemek yiyelim.", lambda b: b.city == "İzmir" and b.group_size == 2 and not b.conditions.budget_limit and not b.conditions.excluded_categories),
    ]:
        started = time.monotonic()
        try:
            result = await interpret_plan(PlanInterpretRequest(text=text, current=conversation))
            passed = bool(check(result.brief)) and not result.questions
            if passed:
                conversation = result.brief
            row = {"case": name, "passed": passed, "failure_layer": None if passed else "context"}
        except Exception as exc:
            row = {"case": name, "passed": False, "failure_layer": "adapter_or_validation", "error_type": type(exc).__name__}
        row["seconds"] = round(time.monotonic() - started, 2)
        rows.append(row)
        print(json.dumps(row), flush=True)
    people = [{"id": f"user-{i}", "label": f"Kişi {i}"} for i in (1, 2, 3)]
    for name, text, check in [
        ("criteria_combined", "Fiyat uygunluğu daha önemli olsun; Kişi 1'e yakınlık iki kat önemli olsun.", lambda r: r.criterion_weights.cost == 70 and r.participant_proximity_weights["user-1"] == 2),
        ("criteria_negative", "Puan önemli değil, fiyat önemli olsun.", lambda r: r.criterion_weights.rating < 34 and r.criterion_weights.cost == 70),
        ("criteria_budget", "Toplam 2000 TL, müze olmasın; yakınlık önemli olsun.", lambda r: r.conditions.budget_limit.scope == "group" and "museum" in r.conditions.excluded_categories and r.criterion_weights.proximity == 70),
    ]:
        started = time.monotonic()
        try:
            result = await interpret_preferences(PreferenceInterpretRequest(text=text, participants=people))
            passed = bool(check(result))
            row = {"case": name, "passed": passed, "failure_layer": None if passed else "interpretation_or_context"}
            if not passed:
                row["actual"] = {"weights": result.criterion_weights.model_dump(), "conditions": result.conditions.model_dump(), "questions": len(result.questions)}
        except Exception as exc:
            row = {"case": name, "passed": False, "failure_layer": "adapter_or_validation", "error_type": type(exc).__name__}
        row["seconds"] = round(time.monotonic() - started, 2)
        rows.append(row)
        print(json.dumps(row), flush=True)
    print(json.dumps({"passed": sum(row["passed"] for row in rows), "total": len(rows), "google_calls": 0, "model": "llama3:8b"}))
    return all(row["passed"] for row in rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", required=True)
    parser.parse_args()
    sys.exit(0 if asyncio.run(main()) else 1)
