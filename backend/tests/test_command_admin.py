"""The OCI command account must not become an unrestricted root shell."""
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from types import SimpleNamespace

import pytest

sys.path.append(str(Path(__file__).resolve().parents[2]))
from deploy import command_admin as admin


@pytest.fixture
def authorized_admin(monkeypatch, tmp_path):
    monkeypatch.setattr(admin.os, "geteuid", lambda: 0)
    monkeypatch.setattr(admin, "check_layout", lambda **_: None)
    monkeypatch.setattr(admin, "LOCK", tmp_path / "operation.lock")
    original = os.fstat
    monkeypatch.setattr(admin.os, "fstat", lambda fd: SimpleNamespace(
        st_uid=0, st_mode=original(fd).st_mode, st_nlink=original(fd).st_nlink))


@pytest.mark.parametrize("action", ["verify", "apply", "rollback", "warmup", "health", "backup"])
def test_admin_only_runs_fixed_isolated_entry_point(authorized_admin, monkeypatch, capsys, action):
    calls = []
    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(returncode=0, stdout="private configuration", stderr="private failure")
    monkeypatch.setattr(admin.subprocess, "run", run)
    assert admin.main([action]) == 0
    assert calls[0][0] == ["/usr/bin/python3", "-I", "/opt/ortak/deploy/operations.py", action]
    options = calls[0][1]
    assert options["env"] == admin.ENVIRONMENT
    assert "shell" not in options and options["capture_output"] is True
    assert "private" not in capsys.readouterr().out


@pytest.mark.parametrize("args", [
    ["shell"], ["exec"], ["import-ledger", "/etc/shadow"], ["apply", "; id"],
    ["health", "--ledger", "/etc/shadow"], ["initialize-empty-ledger"],
    ["apply", "--root", "/tmp/attacker"], ["enable-google"],
])
def test_admin_rejects_extra_arguments_and_privileged_backdoors(monkeypatch, args):
    monkeypatch.setattr(admin, "execute", lambda _: pytest.fail("must reject before execution"))
    with pytest.raises(SystemExit) as error:
        admin.main(args)
    assert error.value.code == 2


def test_admin_refuses_non_root(monkeypatch):
    monkeypatch.setattr(admin.os, "geteuid", lambda: 1000)
    with pytest.raises(PermissionError):
        admin.execute("apply")


@pytest.mark.parametrize("mode,uid", [
    (stat.S_IFLNK | 0o777, 0), (stat.S_IFREG | 0o666, 0),
    (stat.S_IFREG | 0o644, 1000), (stat.S_IFDIR | 0o755, 0),
])
def test_admin_rejects_untrusted_programs(monkeypatch, mode, uid):
    monkeypatch.setattr(Path, "lstat", lambda _: SimpleNamespace(st_mode=mode, st_uid=uid))
    with pytest.raises(ValueError):
        admin.trusted(Path("/opt/ortak/deploy/operations.py"))


def test_private_configuration_must_not_be_readable_by_other_users(monkeypatch):
    monkeypatch.setattr(Path, "lstat", lambda _: SimpleNamespace(st_mode=stat.S_IFREG | 0o644, st_uid=0))
    with pytest.raises(ValueError):
        admin.trusted(Path("/opt/ortak/deploy/.env"), private=True)


def test_admin_refuses_parallel_operation(authorized_admin, capsys):
    with admin.exclusive_operation():
        assert admin.main(["apply"]) == 1
    assert json.loads(capsys.readouterr().out)["error"] == "operation_in_progress"


def test_admin_lock_cannot_be_redirected_to_another_file(authorized_admin, tmp_path):
    target = tmp_path / "untouched"
    target.write_text("unchanged")
    admin.LOCK.symlink_to(target)
    with pytest.raises(OSError):
        with admin.exclusive_operation():
            pytest.fail("must not follow symlink")
    assert target.read_text() == "unchanged"


def test_status_does_not_need_or_print_configuration(authorized_admin, monkeypatch, capsys):
    checks = []
    monkeypatch.setattr(admin, "check_layout", lambda **kwargs: checks.append(kwargs))
    monkeypatch.setattr(admin.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=0))
    assert admin.main(["status"]) == 0
    assert checks == [{"configuration": False}]
    result = json.loads(capsys.readouterr().out)
    assert result["docker_active"] is True
    assert set(result) == {"ok", "action", "docker_active", "configuration_present"}


def test_admin_redacts_subprocess_failure(authorized_admin, monkeypatch, capsys):
    def fail(*_, **__):
        raise subprocess.CalledProcessError(1, "private command", stderr="secret")
    monkeypatch.setattr(admin.subprocess, "run", fail)
    assert admin.main(["backup"]) == 1
    assert json.loads(capsys.readouterr().out) == {"ok": False, "action": "backup", "error": "operation_failed"}


def test_admin_installer_requires_explicit_approval_before_any_install():
    script = Path(__file__).resolve().parents[2] / "deploy/install_command_admin.sh"
    subprocess.run(["bash", "-n", str(script)], capture_output=True, check=True)
    result = subprocess.run(["bash", str(script)], capture_output=True, text=True)
    assert result.returncode == 2
    assert "nothing installed" in result.stderr
    assert "NOPASSWD:ALL" not in script.read_text()
