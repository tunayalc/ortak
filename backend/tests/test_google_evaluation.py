import asyncio
import json
import shutil
import subprocess
import sys
from pathlib import Path

import httpx
import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts import evaluate_google_maps


def test_pilot_cli_imports_schema_in_container_layout(tmp_path):
    backend = Path(__file__).resolve().parents[1]
    runtime = tmp_path / "runtime"
    (runtime / "scripts").mkdir(parents=True)
    (runtime / "app").mkdir()
    shutil.copy(backend / "scripts/evaluate_google_maps.py", runtime / "scripts")
    shutil.copy(backend / "app/schemas.py", runtime / "app")
    result = subprocess.run(
        [sys.executable, "-I", str(runtime / "scripts/evaluate_google_maps.py"), "--help"],
        cwd=tmp_path, capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert "--with-llama" in result.stdout


def healthy(**usage):
    return {"google_configured": True, "google_usage": {
        "calls_enabled": True, "available": True, "budget_enforced": True,
        "budget_limit_tl": 100, "remaining_today": 33, **usage,
    }, "ai_provider": "ollama", "ai_model": "llama3:8b", "ai_ready": True}


def install_mock(monkeypatch, handler):
    original = httpx.AsyncClient
    monkeypatch.setattr(evaluate_google_maps.httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))


def test_unconfigured_live_run_records_blocker_without_google_requests(monkeypatch, tmp_path):
    requests = []
    def handler(request):
        requests.append(request.url.path)
        return httpx.Response(200, json={"status": "ok", "google_configured": False, "google_status": "unconfigured"})
    install_mock(monkeypatch, handler)
    report = asyncio.run(evaluate_google_maps.evaluate("http://127.0.0.1:8000", True, tmp_path))
    assert requests == ["/health"]
    assert report["status"] == "blocked"
    assert report["live_google_verified"] is False
    assert json.loads((tmp_path / "run.json").read_text())["status"] == "blocked"
    assert (tmp_path / "stages.csv").exists()
    assert (tmp_path / "report.md").exists()


def test_configured_key_without_live_flag_does_not_start_billable_work(monkeypatch, tmp_path):
    requests = []
    def handler(request):
        requests.append(request.url.path)
        return httpx.Response(200, json={"status": "ok", "google_configured": True})
    install_mock(monkeypatch, handler)
    report = asyncio.run(evaluate_google_maps.evaluate("http://127.0.0.1:8000", False, tmp_path))
    assert requests == ["/health"]
    assert report["status"] == "preflight_only"


def test_synthetic_places_never_pass_as_live_google(monkeypatch, tmp_path):
    requests = []
    def handler(request):
        path = request.url.path
        requests.append(path)
        if path == "/health":
            return httpx.Response(200, json=healthy())
        if path == "/scenarios":
            return httpx.Response(200, json={"id": "fake-scenario", "users": []})
        return httpx.Response(200, json=[{"provider": "synthetic"} for _ in range(3)])
    install_mock(monkeypatch, handler)
    report = asyncio.run(evaluate_google_maps.evaluate("http://127.0.0.1:8000", True, tmp_path, spending_limit_tl=100))
    assert report["status"] == "failed"
    assert report["live_google_verified"] is False
    assert "/routes/matrix" not in requests


def test_live_run_requires_explicit_test_budget(monkeypatch, tmp_path):
    requests = []
    def handler(request):
        requests.append(request.url.path)
        return httpx.Response(200, json=healthy())
    install_mock(monkeypatch, handler)
    report = asyncio.run(evaluate_google_maps.evaluate("http://127.0.0.1:8000", True, tmp_path))
    assert report["status"] == "blocked"
    assert requests == ["/health"]


def test_live_run_does_not_bypass_disabled_google_calls(monkeypatch, tmp_path):
    requests = []
    def handler(request):
        requests.append(request.url.path)
        return httpx.Response(200, json=healthy(calls_enabled=False))
    install_mock(monkeypatch, handler)
    report = asyncio.run(evaluate_google_maps.evaluate("http://127.0.0.1:8000", True, tmp_path, spending_limit_tl=100))
    assert report["status"] == "blocked"
    assert requests == ["/health"]


def test_live_run_requires_capacity_for_retries(monkeypatch, tmp_path):
    requests = []
    def handler(request):
        requests.append(request.url.path)
        return httpx.Response(200, json=healthy(remaining_today=32))
    install_mock(monkeypatch, handler)
    report = asyncio.run(evaluate_google_maps.evaluate("http://127.0.0.1:8000", True, tmp_path, spending_limit_tl=100))
    assert report["status"] == "blocked"
    assert requests == ["/health"]


def test_https_preflight_failure_is_recorded_not_left_running(monkeypatch, tmp_path):
    install_mock(monkeypatch, lambda request: httpx.Response(503, json={"detail": "unavailable"}))
    report = asyncio.run(evaluate_google_maps.evaluate("https://ortak.test/api/", False, tmp_path))
    assert report["status"] == "failed"
    assert json.loads((tmp_path / "run.json").read_text())["status"] == "failed"


def test_pilot_cannot_increase_authorized_ceiling(monkeypatch, tmp_path):
    requests = []
    def handler(request):
        requests.append(request.url.path)
        return httpx.Response(200, json=healthy())
    install_mock(monkeypatch, handler)
    report = asyncio.run(evaluate_google_maps.evaluate("http://127.0.0.1:8000", True, tmp_path, spending_limit_tl=1000))
    assert report["status"] == "blocked" and requests == ["/health"]


@pytest.mark.parametrize("usage", [{"budget_enforced": False}, {"budget_limit_tl": 101}, {"available": False}])
def test_backend_must_enforce_approved_budget_before_billable_calls(monkeypatch, tmp_path, usage):
    requests = []
    def handler(request):
        requests.append(request.url.path)
        return httpx.Response(200, json=healthy(**usage))
    install_mock(monkeypatch, handler)
    report = asyncio.run(evaluate_google_maps.evaluate("http://127.0.0.1:8000", True, tmp_path, 100))
    assert report["status"] == "blocked"
    assert requests == ["/health"]


def test_unavailable_llama_stops_before_google_work(monkeypatch, tmp_path):
    requests = []
    def handler(request):
        requests.append(request.url.path)
        return httpx.Response(200, json={**healthy(), "ai_ready": False})
    install_mock(monkeypatch, handler)
    report = asyncio.run(evaluate_google_maps.evaluate("http://127.0.0.1:8000", True, tmp_path, 100, True))
    assert report["status"] == "blocked"
    assert requests == ["/health"]


@pytest.mark.parametrize("model", ["llama3:8b", "qwen2.5:3b"])
def test_mocked_llama_workflow_and_preference_reuse(monkeypatch, tmp_path, model):
    requests = []
    def handler(request):
        path = request.url.path
        body = json.loads(request.content) if request.method == "POST" else {}
        requests.append(path)
        if path == "/health":
            return httpx.Response(200, json=healthy())
        if path == "/preferences/interpret":
            assert all(set(person) == {"id", "label", "delta_weight"} for person in body["participants"])
            return httpx.Response(200, json={"source": "ollama", "model": model,
                "criterion_weights": {"rating": 34, "cost": 70, "proximity": 33},
                "participant_proximity_weights": {"user-1": 2, "user-2": 1, "user-3": 1},
                "explanation": "Kurgusal test cevabı."})
        if path == "/scenarios" and request.method == "POST":
            return httpx.Response(200, headers={"X-ORTAK-Google-Calls": "1"}, json={"id": "fictional", "users": [{"id": f"user-{i}"} for i in range(1, 4)]})
        if path == "/candidates/search":
            return httpx.Response(200, headers={"X-ORTAK-Google-Calls": "1"}, json=[{"id": f"candidate-{i}", "place_id": f"fixture-{i}", "provider": "google"} for i in range(1, 4)])
        if path == "/routes/matrix":
            return httpx.Response(200, headers={"X-ORTAK-Google-Calls": "9"}, json=[{"user_id": f"user-{i}", "candidate_id": f"candidate-{j}", "provider": "google", "duration_seconds": 60} for i in range(1, 4) for j in range(1, 4)])
        if path == "/recommendations":
            weights = body.get("criterion_weights", {"rating": 34, "cost": 33, "proximity": 33})
            total = sum(weights.values())
            people = body.get("participant_proximity_weights", dict.fromkeys(["user-1", "user-2", "user-3"], 1))
            person_total = sum(people.values())
            return httpx.Response(200, json={"criterion_weights": {key: value / total for key, value in weights.items()},
                "recommendations": [{"candidate": {"place_id": f"fixture-{i}"}, "score": 0.5,
                    "t_sum_minutes": i, "t_max_minutes": i, "score_breakdown": {"rating_component": 0.2,
                        "cost_component": 0.1, "proximity_component": 0.2,
                        "proximity_contributions": [{"user_id": key, "weight": value / person_total} for key, value in people.items()]}}
                    for i in range(1, 4)]})
        if path == "/experiments/run":
            return httpx.Response(200, json={"baselines": [{}] * 5})
        return httpx.Response(204)
    install_mock(monkeypatch, handler)
    report = asyncio.run(evaluate_google_maps.evaluate("http://127.0.0.1:8000", True, tmp_path, 100, True))
    if model != "llama3:8b":
        assert report["status"] == "failed"
        assert "/scenarios" not in requests
    else:
        assert report["status"] == "passed"
        assert report["checks"]["llama_applied"] is True
        assert report["checks"]["no_extra_google_calls_for_preferences"] is True
        assert sum(item["google_calls"] for item in report["stages"]) == 11
        assert "/scenarios/fictional" in requests
        assert "text" not in report["llama"]
        assert "Kurgusal test cevabı." not in json.dumps(report)
