"""Restricted entry point for the instance's OCI Run Command service account."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import stat
import subprocess
import sys


ROOT = Path("/opt/ortak/deploy")
LOCK = Path("/run/lock/ortak-command-admin.lock")
ACTIONS = ("status", "provision", "verify", "apply", "rollback", "warmup", "health", "backup")
ENVIRONMENT = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "HOME": "/root", "LANG": "C.UTF-8"}


def trusted(path: Path, *, directory=False, private=False):
    info = path.lstat()
    kind = stat.S_ISDIR if directory else stat.S_ISREG
    if not kind(info.st_mode) or info.st_uid != 0 or info.st_mode & (0o077 if private else 0o022):
        raise ValueError("untrusted_installation")


def check_layout(*, configuration=True):
    for path in (*reversed(ROOT.parents), ROOT):
        trusted(path, directory=True)
    trusted(ROOT / "operations.py")
    trusted(ROOT / "compose.yaml")
    # Compose overlays and release records must not be writable by ocarun or API users.
    trusted(ROOT / "private", directory=True, private=True)
    if configuration:
        trusted(ROOT / ".env", private=True)


@contextmanager
def exclusive_operation():
    fd = os.open(LOCK, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o077 or info.st_nlink != 1:
            raise ValueError("untrusted_lock")
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(fd)


def execute(action: str):
    if action not in ACTIONS:
        raise ValueError("unsupported_action")
    if os.geteuid() != 0:
        raise PermissionError("root_required")
    check_layout(configuration=action not in {"status", "provision"})
    with exclusive_operation():
        if action == "status":
            result = subprocess.run(["/usr/bin/systemctl", "is-active", "docker"],
                                    capture_output=True, text=True, timeout=15, env=ENVIRONMENT, cwd="/")
            return {"ok": True, "action": action, "docker_active": result.returncode == 0,
                    "configuration_present": (ROOT / ".env").is_file()}
        if action == "provision":
            program = Path("/usr/local/libexec/ortak-provision.py")
            for parent in reversed(program.parents):
                trusted(parent, directory=True)
            trusted(program, private=True)
            argv = ["/usr/bin/python3", "-I", str(program)]
        else:
            argv = ["/usr/bin/python3", "-I", str(ROOT / "operations.py"), action]
        result = subprocess.run(argv, capture_output=True, text=True,
                                timeout=3600 if action == "provision" else 900, env=ENVIRONMENT, cwd=ROOT)
        # Even a failing Compose invocation may include private configuration in its output.
        return {"ok": result.returncode == 0, "action": action, "returncode": result.returncode}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=ACTIONS)
    args = parser.parse_args(argv)
    try:
        result = execute(args.action)
    except BlockingIOError:
        result = {"ok": False, "action": args.action, "error": "operation_in_progress"}
    except (OSError, ValueError, subprocess.SubprocessError):
        result = {"ok": False, "action": args.action, "error": "operation_failed"}
    print(json.dumps(result))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
