"""Record an HTTP smoke test with fictional participants and verified Google sources."""
from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import math
import sys
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx
from pydantic import ValidationError


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.schemas import PreferenceSuggestion

PROFILES = {
    "balanced": {"rating": 34, "cost": 33, "proximity": 33},
    "rating": {"rating": 70, "cost": 15, "proximity": 15},
    "cost": {"rating": 15, "cost": 70, "proximity": 15},
    "proximity": {"rating": 15, "cost": 15, "proximity": 70},
}


def source_files() -> list[Path]:
    files = []
    for directory in (ROOT / "backend/app", ROOT / "backend/scripts", ROOT / "backend/tests", ROOT / "frontend/src"):
        files.extend(path for path in directory.rglob("*") if path.is_file() and path.suffix in {".py", ".js", ".jsx", ".css"})
    files.extend([ROOT / "backend/requirements.txt", ROOT / "frontend/package.json", ROOT / "frontend/package-lock.json"])
    return sorted(files)


def code_fingerprint() -> str:
    digest = hashlib.sha256()
    for path in source_files():
        digest.update(str(path.relative_to(ROOT)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def save_source_snapshot(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    with tarfile.open(directory / "source.tar.gz", "w:gz") as archive:
        for path in source_files():
            archive.add(path, arcname=str(path.relative_to(ROOT)))


def save_report(report: dict, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "run.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    stages = report["stages"]
    with (directory / "stages.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["stage", "http_status", "elapsed_seconds", "google_calls", "google_retries", "google_elapsed_ms"])
        writer.writeheader()
        writer.writerows({key: stage.get(key) for key in writer.fieldnames} for stage in stages)
    lines = [
        "# Google Maps Canlı Test Kaydı", "",
        f"- Tarih (UTC): {report['started_at_utc']}",
        f"- Durum: {report['status']}",
        f"- Kod sürümü (SHA-256): `{report['code_sha256']}`",
        "- Kaynak kodu ve bağımlılık sürümleri: `source.tar.gz` (anahtar ve veritabanı içermez).",
        f"- Gerçek Google HTTP çağrısı: {sum(stage.get('google_calls', 0) for stage in stages)}",
        f"- Onaylanan test bütçesi (TL): {report.get('authorized_test_limit_tl') or 'Henüz onaylanmadı'}",
        "- Planlanan çağrı / azami deneme: 11 / 33; yerel sayaç diğer uygulamaların kullanımını sınırlamaz.",
        f"- Neden: {report.get('reason') or 'Kontroller tamamlandı.'}", "",
        "| Aşama | HTTP | Süre (sn) | Google çağrısı | Yeniden deneme |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    lines.extend(f"| {stage['stage']} | {stage.get('http_status', '-')} | {stage['elapsed_seconds']} | {stage.get('google_calls', 0)} | {stage.get('google_retries', 0)} |" for stage in stages)
    lines.extend(["", "Bu kayıt yalnızca kurgusal katılımcılarla çalışır. Ham Google yanıtları, kişi konumları, mekân adları, puanları ve API anahtarları kaydedilmez. Kalıcı mekân referansları yalnızca place ID değerleridir.", "", "Bu küçük duman testi araştırma başarı hedeflerinin sağlandığını veya uygulamanın genel erişime hazır olduğunu kanıtlamaz. Google ücretleri Cloud Billing faturasından doğrulanır; çağrı sayısı fatura tutarı değildir.", ""])
    (directory / "report.md").write_text("\n".join(lines), encoding="utf-8")


async def evaluate(api_base: str, live: bool, output: Path, spending_limit_tl: float | None = None, with_llama: bool = False) -> dict:
    report = {
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "code_sha256": code_fingerprint(),
        "api_base": api_base,
        "status": "running",
        "live_google_verified": False,
        "fixture": {"city": "Ankara", "category": "cafe", "group_size": 3, "seed": 42, "radius_m": 1500, "max_candidates": 3},
        "stages": [],
        "checks": {},
        "billing_cost_tl": None,
        "authorized_test_limit_tl": spending_limit_tl,
        "with_llama": with_llama,
        "planned_google_calls": 11,
        "maximum_google_attempts": 33,
        "pricing_reference": "https://developers.google.com/maps/billing-and-pricing/pricing",
        "estimated_list_cost_usd_before_tax_credits": {"normal": 0.13, "all_requests_retried_twice": 0.39},
        "cost_estimate_note": "Google liste fiyatları: Geocoding 0.005 USD, Nearby Search Enterprise 0.035 USD, trafik verili Compute Routes Pro 0.010 USD/istek. Fatura tutarı değildir; kur, vergi ve ücretsiz kullanım ayrıca doğrulanır. Yerel çağrı sayacı parasal bir üst sınır değildir.",
        "source_archive": "source.tar.gz",
    }
    save_source_snapshot(output)
    save_report(report, output)
    async with httpx.AsyncClient(base_url=api_base, timeout=180, trust_env=False) as client:
        runtime = {}
        scenario_id = None
        async def stage(name: str, endpoint: str, payload: dict | None = None):
            started = time.perf_counter()
            entry = {"stage": name, "google_calls": 0, "google_retries": 0, "google_elapsed_ms": 0}
            try:
                response = await client.get(endpoint.lstrip("/")) if payload is None else await client.post(endpoint.lstrip("/"), json=payload)
                entry.update(
                    http_status=response.status_code,
                    google_calls=int(response.headers.get("X-ORTAK-Google-Calls", 0)),
                    google_retries=int(response.headers.get("X-ORTAK-Google-Retries", 0)),
                    google_elapsed_ms=float(response.headers.get("X-ORTAK-Google-Elapsed-Ms", 0)),
                )
                if response.is_error:
                    raise RuntimeError(f"{name} aşaması HTTP {response.status_code} döndürdü. Uygulamadaki API hatasını inceleyin.")
                return response.json()
            finally:
                entry["elapsed_seconds"] = round(time.perf_counter() - started, 3)
                report["stages"].append(entry)
                save_report(report, output)

        try:
            if api_base.startswith("https://"):
                runtime = await stage("runtime_config", "/runtime-config")
                parsed = urlparse(api_base)
                client.headers.update({"Origin": f"{parsed.scheme}://{parsed.netloc}", "X-ORTAK-CSRF": runtime.get("csrf_token", "")})
            health = await stage("health", "/health")
            report["health"] = {key: health.get(key) for key in ("status", "google_configured", "google_status", "google_services", "google_usage", "ai_provider", "ai_model", "ai_ready")}
            usage = health.get("google_usage", {})
            service_remaining = runtime.get("google_service_remaining") if api_base.startswith("https://") else usage.get("service_remaining")
            required_service_attempts = {"geocoding": 3, "places": 3, "routes": 27}
            if not health.get("google_configured"):
                report.update(status="blocked", reason="GOOGLE_MAPS_API_KEY tanımlı değil; canlı Google testi yapılmadı.")
            elif not live:
                report.update(status="preflight_only", reason="Ücret doğurabilecek Google çağrıları için --live seçeneği kullanılmadı.")
            elif spending_limit_tl is None or not math.isfinite(spending_limit_tl) or not 0 < spending_limit_tl <= 100:
                report.update(status="blocked", reason="Canlı test için kullanıcının onayladığı vergi dâhil test bütçesi --max-spend-tl ile belirtilmelidir.")
            elif not health.get("google_usage", {}).get("calls_enabled"):
                report.update(status="blocked", reason="Google Maps çağrıları uygulamada kapalı; faturalandırma/harcama onayı bekleniyor.")
            elif usage.get("budget_enforced") is not True or not isinstance(usage.get("budget_limit_tl"), (int, float)) or not 0 < usage["budget_limit_tl"] <= spending_limit_tl:
                report.update(status="blocked", reason="Backend kalıcı bütçe koruması açık ve onaylı test bütçesiyle sınırlı olmalıdır; ücretli istek gönderilmedi.")
            elif usage.get("available") is not True:
                report.update(status="blocked", reason="Backend bütçe, fiyat veya kullanım kaydı kontrolü geçmedi; ücretli istek gönderilmedi.")
            elif health.get("google_usage", {}).get("remaining_today", runtime.get("google_remaining_requests", 0)) < 33:
                report.update(status="blocked", reason="Yeniden denemeler dâhil 33 isteklik güvenli test için günlük yerel kota yetersiz.")
            elif not isinstance(service_remaining, dict) or any(
                type(service_remaining.get(key)) is not int or service_remaining[key] < count
                for key, count in required_service_attempts.items()
            ):
                report.update(status="blocked", reason="Google servis kotaları doğrulanamadı veya yeniden denemeli pilot için yetersiz.")
            elif with_llama and not (health.get("ai_provider") == "ollama" and health.get("ai_model") == "llama3:8b" and health.get("ai_ready") is True):
                report.update(status="blocked", reason="Mevcut Llama 3 8B hazır değil; başka sağlayıcıya geçilmedi ve ücretli Google isteği gönderilmedi.")
            else:
                fixture = report["fixture"]
                suggestion = None
                if with_llama:
                    suggestion = PreferenceSuggestion.model_validate(await stage("llama_preference", "/preferences/interpret", {
                        "text": "Fiyat uygunluğu daha önemli olsun; Kişi 1'e yakınlık iki kat önemli olsun.",
                        "participants": [{"id": f"user-{index}", "label": f"Kişi {index}", "delta_weight": 1} for index in range(1, 4)],
                        "criterion_weights": PROFILES["balanced"],
                    }))
                    report["checks"]["llama_preference"] = (
                        suggestion.source == "ollama" and suggestion.model == "llama3:8b"
                        and suggestion.criterion_weights.model_dump() == {"rating": 34, "cost": 70, "proximity": 33}
                        and suggestion.participant_proximity_weights == {"user-1": 2, "user-2": 1, "user-3": 1}
                        and suggestion.min_rating is None and suggestion.max_duration_minutes is None
                    )
                    if not report["checks"]["llama_preference"]:
                        raise RuntimeError("Llama önerisi beklenen tercihi karşılamadı; ücretli Google araması başlatılmadı.")
                    report["llama"] = {"source": suggestion.source, "model": suggestion.model,
                                       "criterion_weights": suggestion.criterion_weights.model_dump(),
                                       "participant_proximity_weights": suggestion.participant_proximity_weights}
                scenario = await stage("geocoding_and_scenario", "/scenarios", {key: fixture[key] for key in ("city", "category", "group_size", "seed", "radius_m")} | {"input_mode": "synthetic", "session_only": True})
                scenario_id = scenario["id"]
                candidates = await stage("places_new", "/candidates/search", {"scenario_id": scenario_id, "max_results": fixture["max_candidates"]})
                if len(candidates) < 3 or any(candidate["provider"] != "google" for candidate in candidates):
                    raise RuntimeError("En az üç gerçek Google adayı bulunamadı; sentetik veri canlı sonuç sayılmadı.")
                routes = await stage("routes_api", "/routes/matrix", {"scenario_id": scenario_id, "provider": "google"})
                expected_pairs = {(user["id"], candidate["id"]) for user in scenario["users"] for candidate in candidates}
                report["checks"]["complete_google_matrix"] = (
                    {(route["user_id"], route["candidate_id"]) for route in routes} == expected_pairs
                    and all(route["provider"] == "google" and math.isfinite(route["duration_seconds"]) and route["duration_seconds"] >= 0 for route in routes)
                )
                if not report["checks"]["complete_google_matrix"]:
                    raise RuntimeError("Rota matrisi eksik veya gerçek Google verisi olmayan satırlar içeriyor.")
                if suggestion:
                    result = await stage("llama_recommendation", "/recommendations", {
                        "scenario_id": scenario_id, "k": 3,
                        "criterion_weights": suggestion.criterion_weights.model_dump(),
                        "participant_proximity_weights": suggestion.participant_proximity_weights,
                    })
                    requested = suggestion.criterion_weights.model_dump()
                    total = sum(requested.values())
                    person_total = sum(suggestion.participant_proximity_weights.values())
                    expected_people = {key: value / person_total for key, value in suggestion.participant_proximity_weights.items()}
                    report["checks"]["llama_applied"] = (
                        len(result["recommendations"]) == 3
                        and all(abs(result["criterion_weights"][key] - value / total) <= 0.001 for key, value in requested.items())
                        and all(
                            {entry["user_id"] for entry in row["score_breakdown"]["proximity_contributions"]} == set(expected_people)
                            and all(abs(entry["weight"] - expected_people[entry["user_id"]]) <= 0.001 for entry in row["score_breakdown"]["proximity_contributions"])
                            for row in result["recommendations"]
                        )
                    )
                report["place_ids"] = [candidate["place_id"] for candidate in candidates]
                report["profiles"] = []
                for profile, weights in PROFILES.items():
                    result = await stage(f"profile_{profile}", "/recommendations", {"scenario_id": scenario_id, "k": 3, "criterion_weights": weights})
                    rows = result["recommendations"]
                    components_match = all(abs(row["score"] - sum(row["score_breakdown"][key] for key in ("rating_component", "cost_component", "proximity_component"))) <= 0.001 for row in rows)
                    report["checks"][f"profile_{profile}"] = bool(rows) and components_match and abs(sum(result["criterion_weights"].values()) - 1) <= 0.001
                    report["profiles"].append({"profile": profile, "requested_weights": weights, "effective_weights": result["criterion_weights"], "ranking_place_ids": [row["candidate"]["place_id"] for row in rows]})
                for value, metric in ((0, "t_sum_minutes"), (1, "t_max_minutes")):
                    result = await stage(f"lambda_{value}", "/recommendations", {"scenario_id": scenario_id, "scoring_mode": "report_lambda", "lambda_value": value, "k": 3})
                    rows = result["recommendations"]
                    report["checks"][f"lambda_{value}_extreme"] = bool(rows) and rows[0][metric] <= min(row[metric] for row in rows) + 0.02
                experiment = await stage("baseline_comparison", "/experiments/run", {"scenario_id": scenario_id, "k": 3, "random_repeats": 30})
                report["checks"]["baseline_methods"] = len(experiment["baselines"]) == 5
                report["checks"]["google_call_metadata"] = sum(item["google_calls"] for item in report["stages"]) >= 11
                report["checks"]["no_extra_google_calls_for_preferences"] = all(item["google_calls"] == 0 for item in report["stages"] if item["stage"].startswith(("profile_", "lambda_", "llama_")) or item["stage"] == "baseline_comparison")
                report["checks"]["attempt_limit"] = sum(item["google_calls"] for item in report["stages"]) <= 33
                report["live_google_verified"] = all(report["checks"].values())
                report["status"] = "passed" if report["live_google_verified"] else "failed"
        except (httpx.HTTPError, ValueError, KeyError, TypeError, RuntimeError, ValidationError) as exc:
            report.update(status="failed", reason=str(exc) if isinstance(exc, RuntimeError) else f"Test bağlantısı veya yanıtı okunamadı ({type(exc).__name__}).")
        finally:
            if scenario_id:
                try:
                    await client.delete(f"scenarios/{scenario_id}")
                except httpx.HTTPError:
                    report["cleanup_pending"] = True
    report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    report["code_changed_during_run"] = code_fingerprint() != report["code_sha256"]
    if report["code_changed_during_run"]:
        report.update(status="failed", live_google_verified=False, reason="Test sırasında kaynak kodu değişti; aynı sürümle tekrar çalıştırılmalıdır.")
    save_report(report, output)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--live", action="store_true", help="Gerçek Google çağrılarını açar: 1 geocoding, 1 Places, en çok 9 rota; yeniden denemeler ek çağrı yapabilir.")
    parser.add_argument("--with-llama", action="store_true", help="Google aramasından önce mevcut gerçek Llama 3 8B tercihini doğrular ve rota matrisine uygular.")
    parser.add_argument("--max-spend-tl", type=float, help="Kullanıcının onayladığı vergi dâhil test bütçesi; Google faturasını veya diğer kullanımları parasal olarak durdurmaz.")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "output/google_maps" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    args = parser.parse_args()
    result = asyncio.run(evaluate(args.api_base, args.live, args.output_dir, args.max_spend_tl, args.with_llama))
    print(json.dumps({"status": result["status"], "live_google_verified": result["live_google_verified"], "reason": result.get("reason"), "output_dir": str(args.output_dir)}, ensure_ascii=False))
    sys.exit(0 if result["status"] == "passed" else 2 if result["status"] in {"blocked", "preflight_only"} else 1)
