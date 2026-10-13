import asyncio
import json
import sys
from pathlib import Path

import httpx

sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts import evaluate_google_maps


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
            return httpx.Response(200, json={"google_configured": True, "google_usage": {"calls_enabled": True, "remaining_today": 33}})
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
        return httpx.Response(200, json={"google_configured": True, "google_usage": {"calls_enabled": True, "remaining_today": 33}})
    install_mock(monkeypatch, handler)
    report = asyncio.run(evaluate_google_maps.evaluate("http://127.0.0.1:8000", True, tmp_path))
    assert report["status"] == "blocked"
    assert requests == ["/health"]


def test_live_run_does_not_bypass_disabled_google_calls(monkeypatch, tmp_path):
    requests = []
    def handler(request):
        requests.append(request.url.path)
        return httpx.Response(200, json={"google_configured": True, "google_usage": {"calls_enabled": False, "remaining_today": 33}})
    install_mock(monkeypatch, handler)
    report = asyncio.run(evaluate_google_maps.evaluate("http://127.0.0.1:8000", True, tmp_path, spending_limit_tl=100))
    assert report["status"] == "blocked"
    assert requests == ["/health"]


def test_live_run_requires_capacity_for_retries(monkeypatch, tmp_path):
    requests = []
    def handler(request):
        requests.append(request.url.path)
        return httpx.Response(200, json={"google_configured": True, "google_usage": {"calls_enabled": True, "remaining_today": 32}})
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
        return httpx.Response(200, json={"google_configured": True, "google_usage": {"calls_enabled": True, "remaining_today": 33}})
    install_mock(monkeypatch, handler)
    report = asyncio.run(evaluate_google_maps.evaluate("http://127.0.0.1:8000", True, tmp_path, spending_limit_tl=1000))
    assert report["status"] == "blocked" and requests == ["/health"]
