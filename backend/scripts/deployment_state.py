"""Private, locked launch checkpoints; never stores credentials or locations."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


STAGES = ("oracle_account", "free_capacity", "source", "images", "infrastructure", "llama_validation", "google_pilot", "external_access", "observation", "delivery")
DEPENDENCIES = {
    "free_capacity": ("oracle_account",), "images": ("source",),
    "infrastructure": ("free_capacity", "images"),
    "llama_validation": ("infrastructure",), "google_pilot": ("infrastructure",),
    "external_access": ("llama_validation", "google_pilot"),
    "observation": ("external_access",), "delivery": ("observation",),
}


def utcnow():
    return datetime.now(timezone.utc)


class DeploymentState:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def edit(self):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.path.with_suffix(".lock").open("a") as lock:
            os.chmod(lock.name, 0o600)
            fcntl.flock(lock, fcntl.LOCK_EX)
            state = json.loads(self.path.read_text()) if self.path.exists() else {
                "version": 1, "automation_id": "ortak-yay-n-takibi", "release": "v0.2.0-beta.1",
                "stages": {name: {"status": "pending", "attempts": 0} for name in STAGES},
            }
            yield state
            state["updated_at"] = utcnow().isoformat()
            with tempfile.NamedTemporaryFile(mode="w", dir=self.path.parent, delete=False) as temporary:
                os.chmod(temporary.name, 0o600)
                json.dump(state, temporary, ensure_ascii=False, indent=2)
                temporary.write("\n")
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary.name, self.path)

    def claim(self, name):
        with self.edit() as state:
            stage = state["stages"][name]
            if stage["status"] in {"running", "passed"}:
                raise ValueError("İş zaten başlatılmış veya tamamlanmış; sonucu uzlaştırmadan yeniden başlatmayın.")
            if any(state["stages"][dependency]["status"] != "passed" for dependency in DEPENDENCIES.get(name, ())):
                raise ValueError("Ön koşullar henüz tamamlanmadı.")
            if name == "free_capacity" and stage.get("last_attempt"):
                if (utcnow() - datetime.fromisoformat(stage["last_attempt"])).total_seconds() < 3600:
                    raise ValueError("Ücretsiz kapasite denemeleri arasında en az bir saat olmalı.")
            if name != "free_capacity" and stage["attempts"] >= 3:
                raise ValueError("Üç deneme sınırına ulaşıldı; somut engeli bildirip bağımsız işleri sürdürün.")
            stage.update(status="running", attempts=stage["attempts"] + 1, last_attempt=utcnow().isoformat())

    def finish(self, name, status, note):
        with self.edit() as state:
            stage = state["stages"][name]
            if stage["status"] == "passed":
                raise ValueError("Tamamlanmış aşama otomatik geriye alınamaz.")
            if status == "passed" and stage["status"] != "running":
                raise ValueError("Başarı kaydından önce işi sahiplenin ve kanıtları doğrulayın.")
            if name == "observation" and status == "passed":
                if (utcnow() - datetime.fromisoformat(stage["last_attempt"])).total_seconds() < 86400:
                    raise ValueError("24 saatlik gözlem henüz tamamlanmadı.")
            stage.update(status=status, note=note, finished_at=utcnow().isoformat())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=Path(__file__).resolve().parents[2] / "output/deployment/state.json")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("show")
    claim = sub.add_parser("claim")
    claim.add_argument("stage", choices=STAGES)
    finish = sub.add_parser("finish")
    finish.add_argument("stage", choices=STAGES)
    finish.add_argument("status", choices=("passed", "blocked"))
    finish.add_argument("--note", required=True, help="Only sanitized status; no credentials or personal data")
    args = parser.parse_args()
    store = DeploymentState(args.state)
    try:
        if args.command == "claim":
            store.claim(args.stage)
        elif args.command == "finish":
            store.finish(args.stage, args.status, args.note)
        with store.edit() as current:
            print(json.dumps(current, ensure_ascii=False, indent=2))
    except ValueError as exc:
        parser.exit(2, str(exc) + "\n")
