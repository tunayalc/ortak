from __future__ import annotations

import asyncio
import json
import logging
import time
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Iterator

import httpx

from ..config import get_settings
from .google_usage import finish_call, reserve_call


_events: ContextVar[list[dict[str, Any]] | None] = ContextVar("google_api_events", default=None)
logger = logging.getLogger("ortak.google")


@contextmanager
def capture_google_calls() -> Iterator[list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    token = _events.set(events)
    try:
        yield events
    finally:
        _events.reset(token)


async def google_request(
    url: str,
    parameters: dict[str, Any],
    operation: str,
    *,
    field_mask: str | None = None,
    http_method: str = "GET",
) -> dict[str, Any]:
    settings = get_settings()
    key = settings.google_maps_api_key
    max_attempts = settings.google_maps_max_attempts
    if not key:
        raise RuntimeError("Google Maps API anahtarı tanımlı değil.")
    headers = {"X-Goog-Api-Key": key}
    if field_mask:
        headers["X-Goog-FieldMask"] = field_mask
    # Google content is held in the active scenario, never in permanent api_cache.
    async with httpx.AsyncClient(timeout=httpx.Timeout(20, connect=5), trust_env=False) as client:
        for attempt in range(max_attempts):
            call_id = reserve_call(operation, attempt + 1)
            started = time.perf_counter()
            event: dict[str, Any] = {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "operation": operation,
                "attempt": attempt + 1,
                "http_status": None,
                "outcome": "network_error",
            }
            retry = False
            error = "Google Maps bağlantısı kurulamadı."
            result = None
            try:
                options = {"json": parameters} if http_method == "POST" else {"params": {**parameters, "key": key}}
                response = await client.request(http_method, url, headers=headers, **options)
                event["http_status"] = response.status_code
                retry = response.status_code == 429 or response.status_code >= 500
                if response.is_error:
                    event["outcome"] = f"http_{response.status_code}"
                    error = (
                        f"Google Maps HTTP {response.status_code}: API yetkilerini, faturalandırmayı "
                        "ve kota durumunu kontrol edin."
                    )
                else:
                    payload = response.json()
                    if not isinstance(payload, dict):
                        raise ValueError("Expected a JSON object")
                    status = payload.get("status", "OK")
                    if status in {"OK", "ZERO_RESULTS"}:
                        event["outcome"] = "ok" if status == "OK" else "zero_results"
                        result = payload
                    else:
                        retry = status in {"OVER_QUERY_LIMIT", "UNKNOWN_ERROR"}
                        event["outcome"] = status if status in {"OVER_QUERY_LIMIT", "UNKNOWN_ERROR", "REQUEST_DENIED", "INVALID_REQUEST", "OVER_DAILY_LIMIT"} else "api_error"
                        error = f"Google Maps isteği başarısız ({event['outcome']}). API, faturalandırma ve kota ayarlarını kontrol edin."
            except httpx.TimeoutException:
                event["outcome"] = "timeout"
                retry = True
                error = "Google Maps yanıtı zaman aşımına uğradı."
            except httpx.TransportError:
                retry = True
            except (ValueError, TypeError):
                event["outcome"] = "invalid_response"
                error = "Google Maps geçerli bir JSON yanıtı döndürmedi."
            finally:
                event["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 2)
                events = _events.get()
                if events is not None:
                    events.append(event)
                # Never log request URLs, API keys, addresses or response content.
                logger.info(json.dumps(event, ensure_ascii=False))
                finish_call(call_id, event)
            if result is not None:
                return result
            if not retry or attempt + 1 == max_attempts:
                raise RuntimeError(error) from None
            await asyncio.sleep(0.5 * (2**attempt))
    raise RuntimeError("Google Maps isteği tamamlanamadı.")
