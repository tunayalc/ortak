from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional

from .config import get_settings


def _database_path() -> Path:
    raw = get_settings().database_url
    if raw.startswith("sqlite:///"):
        return Path(raw.removeprefix("sqlite:///")).resolve()
    if raw.startswith("sqlite://"):
        return Path(raw.removeprefix("sqlite://")).resolve()
    return Path(raw).resolve()


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    path = _database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS scenarios (
                id TEXT PRIMARY KEY,
                city TEXT NOT NULL,
                category TEXT NOT NULL,
                group_size INTEGER NOT NULL,
                travel_mode TEXT NOT NULL,
                radius_m INTEGER NOT NULL,
                seed INTEGER NOT NULL,
                users_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS place_candidates (
                id TEXT PRIMARY KEY,
                scenario_id TEXT NOT NULL,
                place_id TEXT NOT NULL,
                name TEXT NOT NULL,
                address TEXT NOT NULL,
                category TEXT NOT NULL,
                rating REAL NOT NULL,
                review_count INTEGER NOT NULL,
                lat REAL NOT NULL,
                lng REAL NOT NULL,
                provider TEXT NOT NULL,
                price_level INTEGER,
                manual_cost REAL,
                raw_json TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (scenario_id) REFERENCES scenarios(id)
            );

            CREATE TABLE IF NOT EXISTS route_metrics (
                id TEXT PRIMARY KEY,
                scenario_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                candidate_id TEXT NOT NULL,
                duration_seconds REAL NOT NULL,
                distance_meters REAL NOT NULL,
                provider TEXT NOT NULL,
                raw_json TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (scenario_id, user_id, candidate_id),
                FOREIGN KEY (scenario_id) REFERENCES scenarios(id),
                FOREIGN KEY (candidate_id) REFERENCES place_candidates(id)
            );

            CREATE TABLE IF NOT EXISTS recommendation_runs (
                id TEXT PRIMARY KEY,
                scenario_id TEXT NOT NULL,
                lambda_value REAL NOT NULL,
                k INTEGER NOT NULL,
                filters_json TEXT NOT NULL,
                results_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (scenario_id) REFERENCES scenarios(id)
            );

            CREATE TABLE IF NOT EXISTS api_cache (
                provider TEXT NOT NULL,
                method TEXT NOT NULL,
                cache_key TEXT NOT NULL,
                response_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (provider, method, cache_key)
            );

            CREATE TABLE IF NOT EXISTS google_api_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usage_day TEXT NOT NULL,
                timestamp_utc TEXT NOT NULL,
                operation TEXT NOT NULL,
                attempt INTEGER NOT NULL,
                http_status INTEGER,
                outcome TEXT NOT NULL DEFAULT 'reserved',
                elapsed_ms REAL
            );
            CREATE INDEX IF NOT EXISTS google_usage_day_idx ON google_api_usage(usage_day);
            CREATE TABLE IF NOT EXISTS request_limits (
                subject TEXT NOT NULL,
                name TEXT NOT NULL,
                bucket INTEGER NOT NULL,
                count INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                PRIMARY KEY (subject, name, bucket)
            );
            """
        )
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(place_candidates)").fetchall()
        }
        if "price_level" not in columns:
            conn.execute("ALTER TABLE place_candidates ADD COLUMN price_level INTEGER")
        if "manual_cost" not in columns:
            conn.execute("ALTER TABLE place_candidates ADD COLUMN manual_cost REAL")
        usage_columns = {row["name"] for row in conn.execute("PRAGMA table_info(google_api_usage)").fetchall()}
        if "estimated_cost_tl" not in usage_columns:
            conn.execute("ALTER TABLE google_api_usage ADD COLUMN estimated_cost_tl REAL")


def row_to_dict(row: Optional[sqlite3.Row]) -> Optional[dict[str, Any]]:
    return dict(row) if row is not None else None


def load_json(value: Optional[str], fallback: Any) -> Any:
    if not value:
        return fallback
    return json.loads(value)


def dump_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)
