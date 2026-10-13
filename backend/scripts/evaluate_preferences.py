"""Live local-model evaluation using only fixed, fictional preferences."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.schemas import PreferenceInterpretRequest
from app.services.preference_interpreter import interpret_preferences, llm_status


CASES = [
    ("rating", "Mekân puanı en önemli kriter olsun.", {}, {"priority": "rating"}),
    ("cost", "Fiyat uygunluğu daha önemli olsun.", {}, {"priority": "cost"}),
    ("proximity", "Kişilere yakınlık daha önemli olsun.", {}, {"priority": "proximity"}),
    ("person_2x", "Ayşe’ye yakınlık iki kat önemli olsun.", {}, {"people": [2, 1]}),
    ("balanced", "Kişiler dengeli olsun, herkes eşit önemde.", {"people": [2, 0.5]}, {"people": [1, 1]}),
    ("rating_limit", "Mekânın puanı en az 4 olsun.", {}, {"min_rating": 4}),
    ("duration_limit", "Kimsenin yolculuğu 20 dakikayı aşmasın.", {}, {"max_duration_minutes": 20}),
    ("ambiguous", "Bana yakın olsun.", {}, {"people": [1, 1], "warning": True}),
    ("money", "Bütçemiz 300 TL, uygun fiyatlı olsun.", {}, {"priority": "cost", "warning": True}),
    ("typo", "Fyat uygunlğu daha önmli olsun.", {}, {"priority": "cost"}),
    ("combined", "Fiyat önemli olsun; Ayşe’ye iki kat yakın olsun, puanı en az 4 olsun.", {}, {"priority": "cost", "people": [2, 1], "min_rating": 4}),
    ("preserve", "Puan daha önemli olsun.", {"people": [1.5, 0.8], "min_rating": 4, "max_duration_minutes": 30}, {"priority": "rating"}),
]


def check(result, payload, expected):
    checks = {}
    before = payload.criterion_weights.model_dump()
    after = result.criterion_weights.model_dump()
    priority = expected.get("priority")
    checks["criteria"] = (
        after[priority] > before[priority] and after[priority] > max(value for key, value in after.items() if key != priority)
        if priority else after == before
    )
    checks["unspecified_criteria"] = all(after[key] == value for key, value in before.items() if key != priority)
    expected_people = expected.get("people", [person.delta_weight for person in payload.participants])
    checks["people"] = result.participant_proximity_weights == dict(zip(["user-1", "user-2"], expected_people))
    for key in ("min_rating", "max_duration_minutes"):
        checks[key] = getattr(result, key) == expected.get(key, getattr(payload, key))
    checks["warning"] = bool(result.warnings) if expected.get("warning") else True
    checks["provider"] = result.source == "ollama" and result.model == get_settings().ollama_model
    return checks


async def evaluate(repeats):
    settings = get_settings()
    if settings.llm_provider != "ollama":
        raise RuntimeError("Canlı değerlendirme yalnızca yerel Ollama sağlayıcısıyla çalışır.")
    status = await llm_status()
    if not status["ai_ready"]:
        raise RuntimeError(f"Yerel model hazır değil: {status['ai_status']}")
    async with httpx.AsyncClient(timeout=3, trust_env=False) as client:
        version = (await client.get(f"{settings.ollama_base_url}/api/version")).json()
        models = (await client.get(f"{settings.ollama_base_url}/api/tags")).json()["models"]
    results = []
    for repeat in range(repeats):
        for name, text, initial, expected in CASES:
            people = initial.get("people", [1, 1])
            payload = PreferenceInterpretRequest(
                text=text,
                participants=[
                    {"id": "user-1", "label": "Ayşe", "delta_weight": people[0]},
                    {"id": "user-2", "label": "Bora", "delta_weight": people[1]},
                ],
                min_rating=initial.get("min_rating"),
                max_duration_minutes=initial.get("max_duration_minutes"),
            )
            started = time.perf_counter()
            entry = {"case": name, "repeat": repeat + 1}
            try:
                result = await interpret_preferences(payload)
                checks = check(result, payload, expected)
                entry.update(passed=all(checks.values()), checks=checks, suggestion=result.model_dump())
            except Exception as exc:
                entry.update(passed=False, error=str(exc))
            entry["seconds"] = round(time.perf_counter() - started, 3)
            results.append(entry)
            print(json.dumps(entry, ensure_ascii=False), flush=True)
    return {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "provider": settings.llm_provider,
        "model": settings.ollama_model,
        "ollama": version,
        "model_details": next(item for item in models if item["name"] == settings.ollama_model),
        "passed": sum(item["passed"] for item in results),
        "total": len(results),
        "results": results,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, choices=range(1, 6), default=1)
    args = parser.parse_args()
    report = asyncio.run(evaluate(args.repeats))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Passed: {report['passed']}/{report['total']}")
    sys.exit(0 if report["passed"] == report["total"] else 1)
