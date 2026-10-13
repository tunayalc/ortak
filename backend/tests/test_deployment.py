from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from app.config import Settings, get_settings
from app.db import get_conn, init_db
from app.services import google_usage, usage_guard

sys.path.append(str(Path(__file__).resolve().parents[1]))
from scripts.backup_database import backup, export_ledger, import_ledger
from scripts.deployment_state import DeploymentState, utcnow
from test_public_release import production

sys.path.append(str(Path(__file__).resolve().parents[2]))
from deploy import operations


def test_empty_price_timestamp_allows_disabled_initial_setup():
    settings = Settings(_env_file=None, GOOGLE_PRICE_VERIFIED_AT="", GOOGLE_MAPS_CALLS_ENABLED=False)
    assert settings.google_price_verified_at is None
    assert settings.google_maps_calls_enabled is False


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


@pytest.mark.parametrize("fail", [False, True])
def test_ledger_transfer_only_exposes_private_copy_and_always_cleans_up(tmp_path, monkeypatch, fail):
    source = tmp_path / "ledger.json"
    original = '{"version": 1, "usage": []}'
    source.write_text(original)
    monkeypatch.setattr(operations, "ROOT", tmp_path)
    monkeypatch.setattr(operations, "configuration", lambda: {})
    monkeypatch.setattr(operations.os, "geteuid", lambda: 0)
    ownership = []
    monkeypatch.setattr(operations.os, "chown", lambda path, uid, gid: ownership.append((Path(path), uid, gid)))
    mounts = []

    def compose(*args, **kwargs):
        directory, target, access = args[args.index("-v") + 1].split(":")
        directory = Path(directory)
        mounts.append(directory)
        assert target == "/transfer" and access == "ro"
        assert directory != tmp_path / "private"
        assert args[:3] == ("run", "--rm", "--no-deps")
        assert args[-4:] == ("python", "scripts/backup_database.py", "import-ledger", "/transfer/ledger.json")
        assert (directory / "ledger.json").read_text() == original
        assert directory.stat().st_mode & 0o777 == 0o700
        assert (directory / "ledger.json").stat().st_mode & 0o777 == 0o600
        assert set(ownership) == {(directory, 10001, 10001), (directory / "ledger.json", 10001, 10001)}
        if fail:
            raise subprocess.CalledProcessError(1, "docker", stderr="private diagnostic")

    monkeypatch.setattr(operations, "compose", compose)
    if fail:
        with pytest.raises(subprocess.CalledProcessError):
            operations.import_ledger(source)
    else:
        operations.import_ledger(source)
    assert len(mounts) == 1
    assert not mounts[0].exists()
    assert source.read_text() == original
    assert (tmp_path / "private").stat().st_mode & 0o777 == 0o700


def test_ledger_transfer_requires_root_before_docker_or_file_access(monkeypatch, tmp_path):
    monkeypatch.setattr(operations.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(operations, "configuration", lambda: pytest.fail("No Docker call before UID validation"))
    with pytest.raises(ValueError, match="sudo"):
        operations.import_ledger(tmp_path / "missing.json")
