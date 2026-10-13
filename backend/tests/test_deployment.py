from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
from pathlib import Path
import sqlite3
import sys

import pytest

from app.config import get_settings
from app.db import get_conn, init_db
from app.services import google_usage, usage_guard

sys.path.append(str(Path(__file__).resolve().parents[1]))
from scripts.backup_database import backup, export_ledger, import_ledger
from scripts.deployment_state import DeploymentState, utcnow
from test_public_release import production


def test_state_parallel_claim_only_one_wins(tmp_path):
    path = tmp_path / "state.json"
    def claim(_):
        try:
            DeploymentState(path).claim("source")
            return True
        except ValueError:
            return False
    with ThreadPoolExecutor(max_workers=10) as pool:
        assert sum(pool.map(claim, range(10))) == 1
    state = json.loads(path.read_text())
    assert state["stages"]["source"]["attempts"] == 1


def test_capacity_hourly_and_dependencies(tmp_path):
    store = DeploymentState(tmp_path / "state.json")
    with pytest.raises(ValueError, match="Ön koşullar"):
        store.claim("free_capacity")
    store.claim("oracle_account")
    store.finish("oracle_account", "passed", "Verified")
    store.claim("free_capacity")
    store.finish("free_capacity", "blocked", "No free capacity")
    with pytest.raises(ValueError, match="bir saat"):
        store.claim("free_capacity")


def test_three_attempt_limit_and_no_premature_success(tmp_path):
    store = DeploymentState(tmp_path / "state.json")
    with pytest.raises(ValueError):
        store.finish("source", "passed", "No evidence")
    for _ in range(3):
        store.claim("source")
        store.finish("source", "blocked", "Failure")
    with pytest.raises(ValueError, match="Üç"):
        store.claim("source")


def test_observation_cannot_finish_before_24h(tmp_path):
    store = DeploymentState(tmp_path / "state.json")
    with store.edit() as state:
        state["stages"]["external_access"]["status"] = "passed"
    store.claim("observation")
    with pytest.raises(ValueError, match="24 saat"):
        store.finish("observation", "passed", "Too early")


def test_per_service_quota_is_atomic(production):
    def reserve(_):
        try:
            return google_usage.reserve_call("geocoding_location", 1)
        except google_usage.GoogleUsageBlocked:
            return None
    with ThreadPoolExecutor(max_workers=10) as pool:
        assert sum(result is not None for result in pool.map(reserve, range(10))) == 3
    with pytest.raises(google_usage.GoogleUsageBlocked, match="servisinin"):
        google_usage.reserve_call("geocoding", 1)
    assert google_usage.usage_status()["used_today"] == 3


def test_missing_guard_and_rolled_back_counter_fail_closed(production):
    google_usage.reserve_call("places_nearby_new", 1)
    with get_conn() as conn:
        conn.execute("DELETE FROM google_api_usage")
    with pytest.raises(google_usage.GoogleUsageBlocked, match="sayacı"):
        google_usage.reserve_call("places_nearby_new", 1)
    assert google_usage.usage_status()["available"] is False


def test_guard_disk_failure_stops_before_dispatch(production, monkeypatch):
    def fail(_):
        raise OSError("Disk full")
    monkeypatch.setattr(usage_guard, "write", fail)
    with pytest.raises(google_usage.GoogleUsageBlocked, match="diske"):
        google_usage.reserve_call("places_nearby_new", 1)
    assert google_usage.usage_status()["used_today"] == 0


def test_backup_and_transfer_preserve_usage_only(production, tmp_path, monkeypatch):
    google_usage.reserve_call("routes_compute_routes", 1)
    from app.db import _database_path
    source = _database_path()
    target = tmp_path / "backup.sqlite3"
    backup(source, target)
    with sqlite3.connect(target) as conn:
        assert conn.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        assert conn.execute("SELECT COUNT(*) FROM google_api_usage").fetchone()[0] == 1
    ledger = tmp_path / "ledger.json"
    export_ledger(ledger)
    assert set(json.loads(ledger.read_text())) == {"version", "usage"}
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'destination.db'}")
    get_settings.cache_clear()
    import_ledger(ledger)
    import_ledger(ledger)
    assert google_usage.usage_status()["used_today"] == 1
    with get_conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM scenarios").fetchone()[0] == 0
