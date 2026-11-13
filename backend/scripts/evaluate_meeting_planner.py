"""Explicit local Llama acceptance; never calls Google or writes prompt/model content."""
import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--base-url", default="http://127.0.0.1:8014")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.live or urlparse(args.base_url).hostname not in {"127.0.0.1", "localhost"}:
        parser.error("Explicit --live and a loopback backend are required.")
    cases = [
        ("city_district", "Ankara Gölbaşı'nda üç arkadaş iki saat sakin ve ekonomik bir sohbet istiyoruz.", {},
         {"city": "Ankara", "area": "Gölbaşı", "group_size": 3, "duration_minutes": 120, "budget": "low", "interests": ["conversation"]}),
        ("nature", "İzmir'de dört kişi, 90 dakika açık havada yürüyüş yapalım.", {},
         {"city": "İzmir", "group_size": 4, "duration_minutes": 90, "environment": "outdoor", "interests": ["nature"]}),
        ("culture", "İstanbul'da beş kişiyiz. Bir saat müze gezelim.", {},
         {"city": "İstanbul", "group_size": 5, "duration_minutes": 60, "interests": ["culture"]}),
        ("missing_city", "İki arkadaş yemek yemek istiyoruz.", {},
         {"city": "", "group_size": 2, "interests": ["food"]}),
        ("preserve_context", "Süreyi 60 dakika yap, diğer bilgiler aynı kalsın.", {"city": "Ankara", "group_size": 3},
         {"city": "Ankara", "group_size": 3, "duration_minutes": 60}),
    ]
    records = []
    google_calls = 0
    with httpx.Client(base_url=args.base_url, timeout=130, trust_env=False) as client:
        for case_id, text, current, expected in cases:
            started = time.monotonic()
            response = client.post("/plans/interpret", json={"text": text, "current": current})
            elapsed = round(time.monotonic() - started, 2)
            google_calls += int(response.headers.get("x-ortak-google-calls", "0"))
            checks = {"http_ok": response.status_code == 200, "no_google": response.headers.get("x-ortak-google-calls") == "0", "under_120s": elapsed <= 120}
            if response.status_code == 200:
                payload = response.json()
                checks["real_provider"] = payload["source"] == "ollama" and payload["model"] == "llama3:8b"
                checks.update({key: payload["brief"][key] == value for key, value in expected.items()})
                plans = client.post("/plans/recommend", json=payload["brief"])
                google_calls += int(plans.headers.get("x-ortak-google-calls", "0"))
                checks["recommendation_http_ok"] = plans.status_code == 200
                checks["recommendation_no_google"] = plans.headers.get("x-ortak-google-calls") == "0"
                if plans.status_code == 200:
                    checks["missing_context_blocks"] = bool(plans.json()["plans"]) == bool(expected["city"])
            record = {"case": case_id, "seconds": elapsed, "http_status": response.status_code, "checks": checks, "passed": all(checks.values())}
            records.append(record)
            print(json.dumps(record), flush=True)
    report = {"recorded_at": datetime.now(timezone.utc).isoformat(), "environment": "local", "model": "llama3:8b", "google_calls": google_calls,
              "passed": sum(r["passed"] for r in records), "total": len(records), "cases": records}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
    return 0 if report["passed"] == report["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
