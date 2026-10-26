from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import importlib.util
from ipaddress import ip_address, ip_network
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from types import SimpleNamespace

import pytest
import yaml

from app.config import Settings, get_settings
from app.db import get_conn, init_db
from app.services import google_usage, usage_guard

sys.path.append(str(Path(__file__).resolve().parents[1]))
from scripts.backup_database import backup, export_ledger, import_ledger
from scripts.deployment_state import DeploymentState, utcnow
from test_public_release import production

sys.path.append(str(Path(__file__).resolve().parents[2]))
from deploy import operations


@pytest.mark.parametrize("os_id,version,expected", [
    ("ol", "9", "oracle-linux-9"),
    ("ol", "9.7", "oracle-linux-9"),
    ("ubuntu", "24.04", "ubuntu-24.04"),
])
def test_bootstrap_readonly_platform_check(os_id, version, expected):
    script = Path(__file__).resolve().parents[2] / "deploy/bootstrap.sh"
    result = subprocess.run(["bash", str(script), "--check-platform", os_id, version], capture_output=True, text=True)
    assert result.returncode == 0
    assert result.stdout.strip() == expected


@pytest.mark.parametrize("os_id,version", [("ol", "8.10"), ("ol", "10"), ("ubuntu", "24.10"), ("debian", "12")])
def test_bootstrap_rejects_unreviewed_platforms_without_installing(os_id, version):
    script = Path(__file__).resolve().parents[2] / "deploy/bootstrap.sh"
    result = subprocess.run(["bash", str(script), "--check-platform", os_id, version], capture_output=True, text=True)
    assert result.returncode == 1
    assert result.stdout == ""
    assert "nothing installed" in result.stderr


def test_bootstrap_shell_syntax():
    script = Path(__file__).resolve().parents[2] / "deploy/bootstrap.sh"
    subprocess.run(["bash", "-n", str(script)], check=True, capture_output=True)


def test_api_persistent_directories_have_private_selinux_labels():
    config = yaml.safe_load((Path(__file__).resolve().parents[2] / "deploy/compose.yaml").read_text())
    mounts = config["services"]["api"]["volumes"]
    assert mounts == ["./data:/data:Z", "./guard:/guard:Z", "./backups:/backups:Z"]


def test_warmup_requires_installed_model_and_confirms_loaded(monkeypatch):
    def configuration(**kwargs):
        assert kwargs == {"require_google_disabled": False}
        return {"services": {"api": {"environment": {"OLLAMA_MODEL": "llama3:8b"}}}}
    monkeypatch.setattr(operations, "configuration", configuration)
    calls = []

    def compose(*args, **kwargs):
        calls.append((args, kwargs))
        if args[-1] == "list":
            return SimpleNamespace(stdout="NAME ID\nllama3:8b abc\n")
        if args[-1] == "ps":
            return SimpleNamespace(stdout="NAME ID\nllama3:8b abc\n")
        return SimpleNamespace(stdout="")

    monkeypatch.setattr(operations, "compose", compose)
    operations.warmup()
    assert [args[-1] for args, _ in calls] == ["list", "", "ps"]
    assert calls[1][0][-2:] == ("llama3:8b", "")
    assert calls[1][1]["timeout"] == 240


def test_warmup_never_pulls_missing_model(monkeypatch):
    monkeypatch.setattr(operations, "configuration", lambda **_: {"services": {"api": {"environment": {"OLLAMA_MODEL": "llama3:8b"}}}})
    calls = []

    def compose(*args, **kwargs):
        calls.append(args)
        return SimpleNamespace(stdout="NAME ID\n")

    monkeypatch.setattr(operations, "compose", compose)
    with pytest.raises(ValueError, match="otomatik indirme"):
        operations.warmup()
    assert len(calls) == 1 and calls[0][-1] == "list"


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("require_disabled", [False, True])
def test_read_only_warmup_allows_live_google_but_release_changes_remain_guarded(monkeypatch, enabled, require_disabled):
    config = {"services": {name: {"image": f"ghcr.io/tunayalc/ortak-{name}@sha256:" + "0" * 64}
                            for name in ("api", "web", "ollama")}}
    config["services"]["web"]["environment"] = {"PUBLIC_HOST": "ortak.example.test"}
    env = {"PUBLIC_BASE_URL": "https://ortak.example.test", "SESSION_SECRET": "x" * 40,
           "GOOGLE_MAPS_CALLS_ENABLED": str(enabled).lower()}
    config["services"]["api"]["environment"] = env
    monkeypatch.setattr(operations, "compose", lambda *args: SimpleNamespace(stdout=json.dumps(config)))
    if enabled and require_disabled:
        with pytest.raises(ValueError, match="kapalı"):
            operations.configuration()
    else:
        result = operations.configuration(require_google_disabled=require_disabled)
        assert result["services"]["api"]["environment"] == env


def test_public_proxy_and_api_have_distinct_static_ips():
    config = yaml.safe_load((Path(__file__).resolve().parents[2] / "deploy/compose.yaml").read_text())
    network = ip_network(config["networks"]["public"]["ipam"]["config"][0]["subnet"])
    proxy = ip_address(config["services"]["web"]["networks"]["public"]["ipv4_address"])
    api = ip_address(config["services"]["api"]["networks"]["public"]["ipv4_address"])
    assert proxy == ip_address("172.30.0.2")  # uvicorn trusts only this proxy address.
    assert api != proxy
    assert api in network and api != network.network_address + 1


@pytest.mark.parametrize("path", [
    "backend/scripts/ortak.usage-guard.json",
    "backend/tests/ortak.usage-guard.json.lock",
    "deploy/guard/usage.json",
    "deploy/data/ledger.json",
])
def test_public_scan_rejects_private_usage_guard(path):
    script = Path(__file__).resolve().parents[2] / "scripts/scan_public.py"
    spec = importlib.util.spec_from_file_location("scan_public", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.allowed(path) is False


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


def test_ledger_import_enriches_only_missing_cost_and_is_idempotent(production, tmp_path):
    google_usage.reserve_call("routes_compute_routes", 1)
    with get_conn() as conn:
        original = dict(conn.execute("SELECT * FROM google_api_usage WHERE id = 1").fetchone())
        conn.execute("UPDATE google_api_usage SET estimated_cost_tl = NULL WHERE id = 1")
    ledger = tmp_path / "enriched.json"
    ledger.write_text(json.dumps({"version": 1, "usage": [original]}))
    import_ledger(ledger)
    import_ledger(ledger)
    with get_conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM google_api_usage").fetchone()[0] == 1
        assert conn.execute("SELECT estimated_cost_tl FROM google_api_usage WHERE id = 1").fetchone()[0] == original["estimated_cost_tl"]
        usage_guard.verify(conn)


def test_ledger_import_rejects_other_conflict_without_partial_merge(production, tmp_path):
    google_usage.reserve_call("routes_compute_routes", 1)
    with get_conn() as conn:
        original = dict(conn.execute("SELECT * FROM google_api_usage WHERE id = 1").fetchone())
        conn.execute("UPDATE google_api_usage SET estimated_cost_tl = NULL WHERE id = 1")
    extra = dict(original, id=2)
    conflicting = dict(original, outcome="different")
    ledger = tmp_path / "conflict.json"
    ledger.write_text(json.dumps({"version": 1, "usage": [extra, conflicting]}))
    with pytest.raises(ValueError, match="Çakışan"):
        import_ledger(ledger)
    with get_conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM google_api_usage").fetchone()[0] == 1
        assert conn.execute("SELECT estimated_cost_tl FROM google_api_usage WHERE id = 1").fetchone()[0] is None
        usage_guard.verify(conn)


@pytest.mark.parametrize("fail", [False, True])
def test_ledger_transfer_only_exposes_private_copy_and_always_cleans_up(tmp_path, monkeypatch, fail):
    source = tmp_path / "ledger.json"
    original = '{"version": 1, "usage": []}'
    source.write_text(original)
    monkeypatch.setattr(operations, "ROOT", tmp_path)
    monkeypatch.setattr(operations, "configuration", lambda: {})
    monkeypatch.setattr(operations.os, "geteuid", lambda: 0)
    backups = tmp_path / "backups"
    backups.mkdir(mode=0o700)
    ownership = []
    monkeypatch.setattr(operations.os, "chown", lambda path, uid, gid: ownership.append((Path(path), uid, gid)))
    original_stat = Path.stat
    monkeypatch.setattr(Path, "stat", lambda path, *args, **kwargs: SimpleNamespace(st_uid=10001, st_mode=0o40700) if path == backups else original_stat(path, *args, **kwargs))
    staged_paths = []

    def compose(*args, **kwargs):
        assert args[:3] == ("exec", "-T", "api")
        assert args[3:6] == ("python", "scripts/backup_database.py", "import-ledger")
        staged = backups / Path(args[-1]).name
        staged_paths.append(staged)
        assert args[-1] == f"/backups/{staged.name}"
        assert staged.read_text() == original
        assert staged.stat().st_mode & 0o777 == 0o600
        assert ownership == [(staged, 10001, 10001)]
        if fail:
            raise subprocess.CalledProcessError(1, "docker", stderr="private diagnostic")

    monkeypatch.setattr(operations, "compose", compose)
    if fail:
        with pytest.raises(subprocess.CalledProcessError):
            operations.import_ledger(source)
    else:
        operations.import_ledger(source)
    assert len(staged_paths) == 1
    assert not staged_paths[0].exists()
    assert source.read_text() == original


def test_ledger_transfer_requires_root_before_docker_or_file_access(monkeypatch, tmp_path):
    monkeypatch.setattr(operations.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(operations, "configuration", lambda: pytest.fail("No Docker call before UID validation"))
    with pytest.raises(ValueError, match="sudo"):
        operations.import_ledger(tmp_path / "missing.json")


def test_local_pilot_enforces_budget_without_production_mode(production, monkeypatch):
    monkeypatch.setenv("APP_ENVIRONMENT", "development")
    monkeypatch.setenv("GOOGLE_BUDGET_ENFORCEMENT_ENABLED", "true")
    monkeypatch.setenv("GOOGLE_BUDGET_LIMIT_TL", "1.5")
    get_settings.cache_clear()
    assert not get_settings().production
    assert get_settings().google_budget_protected
    google_usage.reserve_call("routes_compute_routes", 1)
    with pytest.raises(google_usage.GoogleUsageBlocked, match="bütçesi"):
        google_usage.reserve_call("routes_compute_routes", 1)
    assert google_usage.usage_status()["estimated_cost_tl"] == 1


@pytest.mark.parametrize("missing", ["prices", "guard"])
def test_local_pilot_requires_verified_prices_and_existing_guard(production, monkeypatch, missing):
    monkeypatch.setenv("APP_ENVIRONMENT", "development")
    monkeypatch.setenv("GOOGLE_BUDGET_ENFORCEMENT_ENABLED", "true")
    if missing == "prices":
        monkeypatch.setenv("GOOGLE_UNIT_PRICES_TL", "{}")
    else:
        usage_guard.guard_path().unlink()
    get_settings.cache_clear()
    with pytest.raises(google_usage.GoogleUsageBlocked):
        google_usage.reserve_call("geocoding", 1)
    assert google_usage.usage_status()["available"] is False
    with get_conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM google_api_usage").fetchone()[0] == 0
