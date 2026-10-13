"""A separate durable high-water mark detects missing or rolled-back quota DBs."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from ..config import get_settings
from ..db import _database_path


def guard_path() -> Path:
    configured = get_settings().google_ledger_watermark_path
    return Path(configured) if configured else _database_path().with_suffix(".usage-guard.json")


def snapshot(conn) -> dict:
    row = conn.execute("SELECT COUNT(*) AS count, COALESCE(MAX(id), 0) AS max_id FROM google_api_usage").fetchone()
    return {"version": 1, "count": row["count"], "max_id": row["max_id"]}


def verify(conn) -> None:
    # Initialization is an explicit operator action, never an automatic reset.
    try:
        mark = json.loads(guard_path().read_text())
        current = snapshot(conn)
        if mark["version"] != 1 or any(type(mark[key]) is not int or mark[key] < 0 or mark[key] > current[key] for key in ("count", "max_id")):
            raise ValueError("rollback")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ValueError("Kullanım sayacı doğrulanamadı; Google kapalı kalır. Yedek ve faturalandırma kayıtlarını uzlaştırın.") from exc


def write(conn) -> None:
    path = guard_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as handle:
            temporary = handle.name
            os.chmod(temporary, 0o600)
            json.dump(snapshot(conn), handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
