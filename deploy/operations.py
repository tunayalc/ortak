"""Server-side release, read-only health and backups. Does not enable Google."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
IMAGE = re.compile(r"^[a-z0-9./:_-]+@sha256:[a-f0-9]{64}$")


def compose(*args, check=True):
    return subprocess.run(["docker", "compose", "--project-directory", str(ROOT), "-f", str(ROOT / "compose.yaml"), *args], check=check, capture_output=True, text=True)


def configuration():
    config = json.loads(compose("config", "--format", "json").stdout)
    for service in ("web", "api", "ollama"):
        if not IMAGE.fullmatch(config["services"][service]["image"]):
            raise ValueError("Her üretim imajı doğrulanmış SHA-256 digest ile sabitlenmeli.")
    env = config["services"]["api"]["environment"]
    host = config["services"]["web"]["environment"]["PUBLIC_HOST"]
    if "REPLACE" in host or "/" in host or env["PUBLIC_BASE_URL"] != f"https://{host}":
        raise ValueError("HTTPS adresi ve PUBLIC_HOST eşleşmiyor.")
    if len(env.get("SESSION_SECRET", "")) < 32 or "REPLACE" in env["SESSION_SECRET"]:
        raise ValueError("Güçlü, özel bir oturum anahtarı gerekli.")
    if env.get("GOOGLE_MAPS_CALLS_ENABLED", "false").lower() not in {"false", "0"}:
        raise ValueError("Kurulum, sağlık kontrolü ve geri dönüşte Google çağrıları kapalı olmalı.")
    return config


def save_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as handle:
        os.chmod(handle.name, 0o600)
        json.dump(payload, handle, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(handle.name, path)


def apply():
    config = configuration()
    release_file = ROOT / "private/release.json"
    images = {service: config["services"][service]["image"] for service in ("api", "web", "ollama")}
    if release_file.exists():
        previous = json.loads(release_file.read_text())
        if previous["images"] == images:
            compose("up", "-d", "--wait", "--wait-timeout", "180")
            return
        save_json(ROOT / "private/previous-release.json", previous)
    compose("pull")
    compose("up", "-d", "--wait", "--wait-timeout", "180")
    save_json(release_file, {"recorded_at": datetime.now(timezone.utc).isoformat(),
                            "images": images})


def rollback():
    configuration()
    previous = json.loads((ROOT / "private/previous-release.json").read_text())
    # Only images change; the quota, guard, model and certificate volumes are untouched.
    override = ROOT / "private/rollback.json"
    save_json(override, {"services": {key: {"image": value} for key, value in previous["images"].items()}})
    args = ["-f", str(override)]
    compose(*args, "up", "-d", "--wait", "--wait-timeout", "180")
    save_json(ROOT / "private/release.json", previous)


def import_ledger(source: Path):
    if os.geteuid() != 0:
        raise ValueError("Kullanım kaydı aktarımı sudo ile çalıştırılmalı.")
    configuration()
    private = ROOT / "private"
    private.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Bind only a disposable copy; never expose the root-owned private directory.
    with tempfile.TemporaryDirectory(prefix="ledger-transfer-", dir=private) as directory:
        staged = Path(directory) / "ledger.json"
        shutil.copyfile(source, staged)
        os.chmod(staged, 0o600)
        os.chown(staged, 10001, 10001)
        os.chmod(directory, 0o700)
        os.chown(directory, 10001, 10001)
        compose("run", "--rm", "--no-deps", "-v", f"{directory}:/transfer:ro",
                "api", "python", "scripts/backup_database.py", "import-ledger", "/transfer/ledger.json")


def health():
    config = json.loads(compose("config", "--format", "json").stdout)
    origin = config["services"]["api"]["environment"]["PUBLIC_BASE_URL"]
    checks = {}
    for path in ("readyz", "health"):
        try:
            with urllib.request.urlopen(origin + "/api/" + path, timeout=10) as response:
                payload = json.load(response)
            checks[path] = payload.get("status") == "ok"
            if path == "health":
                checks["llama_ready"] = payload.get("ai_ready") is True and payload.get("ai_model") == "llama3:8b"
        except Exception:
            checks[path] = False
    checks["free_disk"] = shutil.disk_usage(ROOT).free >= 2 * 1024 ** 3
    ids = compose("ps", "-aq").stdout.split()
    if ids:
        containers = json.loads(subprocess.run(["docker", "inspect", *ids], capture_output=True, text=True, check=True).stdout)
        checks["no_oom"] = all(not item["State"].get("OOMKilled") for item in containers)
        checks["running"] = len(containers) == 3 and all(item["State"]["Running"] for item in containers)
    else:
        checks["running"] = False
    result = {"timestamp": datetime.now(timezone.utc).isoformat(), "passed": all(checks.values()), "checks": checks}
    history = ROOT / "private/health.jsonl"
    history.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with history.open("a") as handle:
        os.chmod(history, 0o600)
        handle.write(json.dumps(result) + "\n")
    observation_file = ROOT / "private/observation.json"
    observation = json.loads(observation_file.read_text()) if observation_file.exists() else {}
    now = time.time()
    if not result["passed"] or now - observation.get("last_check", now) > 600:
        observation = {}
    if result["passed"]:
        observation.setdefault("healthy_since", now)
    observation.update(last_check=now, accepted_24h=bool(result["passed"] and now - observation.get("healthy_since", now) >= 86400))
    save_json(observation_file, observation)
    print(json.dumps(result))
    return result["passed"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("verify", "apply", "rollback", "health", "backup", "import-ledger"))
    parser.add_argument("--ledger", type=Path, help="Private ledger-only export to merge before enabling Google")
    args = parser.parse_args()
    try:
        if args.command == "verify":
            configuration()
            print("Production configuration verified; Google calls remain disabled.")
        elif args.command == "apply":
            apply()
        elif args.command == "rollback":
            rollback()
        elif args.command == "backup":
            compose("exec", "-T", "api", "python", "scripts/backup_database.py", "backup")
        elif args.command == "import-ledger":
            if args.ledger is None:
                raise ValueError("Özel kullanım kaydı dosyası gerekli.")
            import_ledger(args.ledger)
            print("Ledger merged; temporary transfer removed and original export preserved.")
        else:
            raise SystemExit(0 if health() else 1)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError):
        # Subprocess output may contain rendered configuration; never echo it.
        parser.exit(1, "Operation failed. Inspect the private server state; secrets were not printed.\n")
