from __future__ import annotations

from datetime import datetime, timezone
import math
from zoneinfo import ZoneInfo

from ..config import get_settings
from ..db import get_conn
from . import usage_guard


class GoogleUsageBlocked(RuntimeError):
    pass


OPERATIONS = {"geocoding", "geocoding_location", "places_nearby_new", "routes_compute_routes"}
SERVICE_LIMITS = {"geocoding": 3, "places": 3, "routes": 27}
SERVICE_OPERATIONS = {"geocoding": ("geocoding", "geocoding_location"), "places": ("places_nearby_new",), "routes": ("routes_compute_routes",)}


def verify_ledger(conn):
    try:
        usage_guard.verify(conn)
    except ValueError as exc:
        raise GoogleUsageBlocked(str(exc)) from exc


def service_remaining(conn, day):
    used = {row["operation"]: row["count"] for row in conn.execute("SELECT operation, COUNT(*) AS count FROM google_api_usage WHERE usage_day = ? GROUP BY operation", (day,))}
    return {service: max(0, limit - sum(used.get(operation, 0) for operation in SERVICE_OPERATIONS[service])) for service, limit in SERVICE_LIMITS.items()}


def verified_prices() -> dict[str, float]:
    settings = get_settings()
    stamp = settings.google_price_verified_at
    prices = settings.google_unit_prices_tl
    if not stamp or stamp.tzinfo is None or not settings.google_price_source:
        raise GoogleUsageBlocked("Güncel ve kaynaklı TL maliyet bilgisi eksik; Google çağrıları durduruldu.")
    age = (datetime.now(timezone.utc) - stamp).total_seconds()
    if age < 0 or age > 7 * 86400:
        raise GoogleUsageBlocked("Maliyet bilgisinin yedi günlük geçerlilik süresi doldu; Google çağrıları durduruldu.")
    if not OPERATIONS.issubset(prices) or any(not math.isfinite(prices[key]) or prices[key] <= 0 for key in OPERATIONS):
        raise GoogleUsageBlocked("Vergi ve güvenlik payı içeren geçerli birim fiyatlar eksik; Google çağrıları durduruldu.")
    return {key: prices[key] for key in OPERATIONS}


def estimated_spend(conn, worst_price: float) -> float:
    # Old records and interrupted requests must never disappear from the allowance.
    return conn.execute("SELECT COALESCE(SUM(COALESCE(estimated_cost_tl, ?)), 0) FROM google_api_usage", (worst_price,)).fetchone()[0]


def usage_day() -> str:
    return datetime.now(ZoneInfo("Europe/Istanbul")).date().isoformat()


def usage_status() -> dict[str, object]:
    settings = get_settings()
    day = usage_day()
    with get_conn() as conn:
        used = conn.execute("SELECT COUNT(*) FROM google_api_usage WHERE usage_day = ?", (day,)).fetchone()[0]
    status = {
        "calls_enabled": settings.google_maps_calls_enabled,
        "daily_limit": settings.google_maps_daily_call_limit,
        "max_attempts_per_request": settings.google_maps_max_attempts,
        "used_today": used,
        "remaining_today": max(0, settings.google_maps_daily_call_limit - used),
        "usage_day": day,
        "timezone": "Europe/Istanbul",
        "scope": "this_backend_database",
        "budget_enforced": settings.google_budget_protected,
        "budget_limit_tl": settings.google_budget_limit_tl,
    }
    status["available"] = settings.google_maps_calls_enabled and used < settings.google_maps_daily_call_limit
    status["unavailable_reason"] = "" if status["available"] else "Google işlemleri şu anda kapalı veya günlük kota dolu."
    if settings.google_budget_protected:
        try:
            prices = verified_prices()
            with get_conn() as conn:
                verify_ledger(conn)
                spent = estimated_spend(conn, max(prices.values()))
                status["service_remaining"] = service_remaining(conn, day)
            status.update(estimated_cost_tl=round(spent, 4), budget_limit_tl=settings.google_budget_limit_tl)
            if spent + max(prices.values()) > settings.google_budget_limit_tl:
                raise GoogleUsageBlocked("Güvenlik payı ayrılmış kullanım bütçesi doldu; yeni Google çağrısı yapılmayacak.")
        except GoogleUsageBlocked as exc:
            status.update(available=False, unavailable_reason=str(exc))
    return status


def ensure_capacity(required: int = 1) -> None:
    status = usage_status()
    if not status["calls_enabled"]:
        raise GoogleUsageBlocked("Google Maps çağrıları kapalı. Faturalandırma ve harcama onayından sonra GOOGLE_MAPS_CALLS_ENABLED=true ayarlanmalıdır.")
    if required > status["remaining_today"]:
        raise GoogleUsageBlocked("Google Maps günlük yerel çağrı sınırı yetersiz. Yeni istek gönderilmedi; kota ve kullanım kaydını kontrol edin.")
    settings = get_settings()
    if settings.google_budget_protected:
        worst = max(verified_prices().values())
        with get_conn() as conn:
            if estimated_spend(conn, worst) + required * worst > settings.google_budget_limit_tl:
                raise GoogleUsageBlocked("İşlem için bütçe kapasitesi yetersiz; yeni Google çağrısı yapılmadı.")


def reserve_call(operation: str, attempt: int) -> int:
    settings = get_settings()
    if not settings.google_maps_calls_enabled:
        raise GoogleUsageBlocked("Google Maps çağrıları kapalı; harcama onayı olmadan istek gönderilmedi.")
    price = None
    worst = 0
    if settings.google_budget_protected:
        prices = verified_prices()
        if operation not in prices:
            raise GoogleUsageBlocked("Bu Google işlemi için doğrulanmış fiyat yok; istek gönderilmedi.")
        price, worst = prices[operation], max(prices.values())
    # Reserving before transmission keeps parallel requests and restarts within the same limit.
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        day = usage_day()
        used = conn.execute("SELECT COUNT(*) FROM google_api_usage WHERE usage_day = ?", (day,)).fetchone()[0]
        if used >= settings.google_maps_daily_call_limit:
            raise GoogleUsageBlocked("Google Maps günlük yerel çağrı sınırına ulaşıldı; yeni istek gönderilmedi.")
        if settings.google_budget_protected:
            verify_ledger(conn)
            if operation not in OPERATIONS:
                raise GoogleUsageBlocked("Desteklenmeyen Google işlemi; istek gönderilmedi.")
            service = next(key for key, operations in SERVICE_OPERATIONS.items() if operation in operations)
            if service_remaining(conn, day)[service] <= 0:
                raise GoogleUsageBlocked("Bu Google servisinin günlük kotası doldu; yeni istek gönderilmedi.")
            if estimated_spend(conn, worst) + price > settings.google_budget_limit_tl:
                raise GoogleUsageBlocked("Güvenlik payı ayrılmış kullanım bütçesi doldu; istek gönderilmedi.")
            conn.execute("UPDATE google_api_usage SET estimated_cost_tl = ? WHERE estimated_cost_tl IS NULL", (worst,))
        cursor = conn.execute(
            "INSERT INTO google_api_usage (usage_day, timestamp_utc, operation, attempt, estimated_cost_tl) VALUES (?, ?, ?, ?, ?)",
            (day, datetime.now(timezone.utc).isoformat(), operation, attempt, price),
        )
        if settings.google_budget_protected:
            # Persist before dispatch. A DB failure afterwards fails closed, never refunds a call.
            try:
                usage_guard.write(conn)
            except OSError as exc:
                raise GoogleUsageBlocked("Kullanım kaydı diske yazılamadı; Google isteği gönderilmedi.") from exc
        return cursor.lastrowid


def finish_call(call_id: int, event: dict) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE google_api_usage SET http_status = ?, outcome = ?, elapsed_ms = ? WHERE id = ?",
            (event["http_status"], event["outcome"], event["elapsed_ms"], call_id),
        )
