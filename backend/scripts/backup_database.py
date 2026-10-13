"""Consistent private SQLite backups and ledger-only transfer; no HTTP calls."""
from __future__ import annotations

import argparse
import json
import math
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db import get_conn, init_db, _database_path
from app.services import usage_guard


def backup(source: Path, destination: Path):
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if destination.exists():
        raise ValueError("Yedek hedefi zaten var; mevcut dosya üzerine yazılmaz.")
    temporary = destination.with_suffix(".partial")
    with sqlite3.connect(f"{source.resolve().as_uri()}?mode=ro", uri=True) as original, sqlite3.connect(temporary) as copy:
        original.backup(copy)
        if copy.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("Yedek bütünlük kontrolü başarısız.")
    os.chmod(temporary, 0o600)
    os.replace(temporary, destination)


def export_ledger(destination: Path):
    with get_conn() as conn:
        rows = [dict(row) for row in conn.execute("SELECT * FROM google_api_usage ORDER BY id")]
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with destination.open("x") as handle:
        os.chmod(destination, 0o600)
        json.dump({"version": 1, "usage": rows}, handle, indent=2)
        handle.flush()
        os.fsync(handle.fileno())


def import_ledger(source: Path):
    payload = json.loads(source.read_text())
    if payload["version"] != 1:
        raise ValueError("Bilinmeyen kayıt sürümü.")
    init_db()
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        for row in payload["usage"]:
            columns = ("id", "usage_day", "timestamp_utc", "operation", "attempt", "http_status", "outcome", "elapsed_ms", "estimated_cost_tl")
            if set(row) != set(columns):
                raise ValueError("Kullanım kaydı alanları eksik veya beklenenden farklı.")
            cost = row["estimated_cost_tl"]
            if cost is not None and (type(cost) not in (int, float) or not math.isfinite(cost) or cost < 0):
                raise ValueError("Geçersiz kullanım maliyeti; aktarım durduruldu.")
            existing = conn.execute("SELECT * FROM google_api_usage WHERE id = ?", (row["id"],)).fetchone()
            if existing:
                saved = dict(existing)
                if all(saved[key] == row[key] for key in columns if key != "estimated_cost_tl") and saved["estimated_cost_tl"] is None and cost is not None and cost > 0:
                    conn.execute("UPDATE google_api_usage SET estimated_cost_tl = ? WHERE id = ? AND estimated_cost_tl IS NULL", (cost, row["id"]))
                    continue
                if saved != row:
                    raise ValueError("Çakışan kullanım kaydı; otomatik sayaç değişikliği yapılmadı.")
                continue
            conn.execute(f"INSERT INTO google_api_usage ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})", [row[key] for key in columns])
        if usage_guard.guard_path().exists():
            usage_guard.verify(conn)
        usage_guard.write(conn)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    daily = sub.add_parser("backup")
    daily.add_argument("--directory", type=Path, default=Path("/backups"))
    export = sub.add_parser("export-ledger")
    export.add_argument("path", type=Path)
    transfer = sub.add_parser("import-ledger")
    transfer.add_argument("path", type=Path)
    initialize = sub.add_parser("initialize-empty-ledger")
    args = parser.parse_args()
    if args.command == "backup":
        target = args.directory / (datetime.now(timezone.utc).strftime("ortak-%Y%m%dT%H%M%S") + ".sqlite3")
        backup(_database_path(), target)
        for old in sorted(args.directory.glob("ortak-*.sqlite3"))[:-7]:
            old.unlink()
        print("Private backup verified; retained latest seven copies.")
    elif args.command == "export-ledger":
        export_ledger(args.path)
        print("Ledger exported; contains no scenarios, locations or Google content.")
    elif args.command == "import-ledger":
        import_ledger(args.path)
        print("Ledger merged without resetting existing usage.")
    else:
        init_db()
        with get_conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if usage_guard.guard_path().exists() or conn.execute("SELECT COUNT(*) FROM google_api_usage").fetchone()[0]:
                parser.exit(2, "Existing ledger must be reconciled, not initialized again.\n")
            usage_guard.write(conn)
        print("Empty ledger initialized explicitly; import previous usage before enabling Google.")
