import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
from unittest.mock import AsyncMock

import httpx
import pytest

from app.config import get_settings
from app.db import get_conn
from app.services import google_prices as prices, google_usage
from test_public_release import production


HTML = ("<p>Costs - per 1000 events | Prices - USD</p><table>" + "".join(
    f"<tr><td>{sku}</td><td>1000</td><td>${value}</td><td>$1.00</td></tr>"
    for sku, value in zip(prices.SKU_IDS.values(), ("5.00", "35.00", "10.00"))
) + "</table>").encode()


def fx_body(stamp=None, rate="49.6540"):
    stamp = stamp or datetime.now(timezone.utc)
    return (f'<Tarih_Date Tarih="{stamp:%d.%m.%Y}"><Currency Kod="USD">'
            f'<Unit>1</Unit><ForexSelling>{rate}</ForexSelling></Currency></Tarih_Date>').encode()


def snapshot(now=None):
    now = now or datetime.now(timezone.utc)
    return prices.PriceSnapshot(verified_at=now, fx_date=now.date(), fx_usd_try=49.654,
        reserved_fx_usd_try=60, unit_prices_tl={"geocoding": .45, "geocoding_location": .45,
        "places_nearby_new": 3.15, "routes_compute_routes": .9},
        source_sha256={prices.PRICING_URL: "a" * 64, prices.FX_URL: "b" * 64, prices.VAT_URL: prices.VAT_SHA256})


def test_first_paid_tier_is_used_instead_of_free_allowance_or_discount():
    result = prices.parse_google_prices(HTML)
    assert result == {"geocoding": Decimal(".005"), "geocoding_location": Decimal(".005"),
                      "places_nearby_new": Decimal(".035"), "routes_compute_routes": Decimal(".01")}


@pytest.mark.parametrize("body", [
    HTML.replace(b"Prices - USD", b"Prices - EUR"),
    HTML.replace(b"1000 events", b"100 events"),
    HTML.replace(b"$35.00", b"Contact sales"),
    HTML.replace(b"772E-9975-BE34", b"UNKNOWN-SKU"),
    HTML + b"<table><tr><td>772E-9975-BE34</td><td>0</td><td>$35.00</td></tr></table>",
])
def test_changed_or_ambiguous_pricing_is_not_accepted(body):
    with pytest.raises(ValueError):
        prices.parse_google_prices(body)


@pytest.mark.parametrize("rate", ["", "junk", "NaN", "Infinity", "-1", "0"])
def test_invalid_fx_is_safely_rejected(rate):
    with pytest.raises(ValueError):
        prices.parse_fx(fx_body(rate=rate), datetime.now(timezone.utc))


def test_weekend_fx_is_valid_but_future_and_stale_rates_are_rejected():
    now = datetime.now(timezone.utc)
    assert prices.parse_fx(fx_body(now - timedelta(days=2)), now)[1] == Decimal("49.6540")
    for age in (-1, 8):
        with pytest.raises(ValueError):
            prices.parse_fx(fx_body(now - timedelta(days=age)), now)


def test_refresh_contacts_only_public_references_without_credentials(monkeypatch):
    vat = b"test-only tax reference"
    monkeypatch.setattr(prices, "VAT_SHA256", hashlib.sha256(vat).hexdigest())
    bodies = {prices.PRICING_URL: HTML, prices.FX_URL: fx_body(), prices.VAT_URL: vat}
    seen = []

    def handler(request):
        seen.append(request)
        assert request.method == "GET"
        assert not request.headers.get("authorization") and not request.headers.get("x-goog-api-key")
        assert not request.content
        return httpx.Response(200, content=bodies[str(request.url)])

    async def collect():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await prices.collect_snapshot(client)
    result = asyncio.run(collect())
    assert result.unit_prices_tl == snapshot().unit_prices_tl
    assert len(seen) == 3 and set(str(request.url) for request in seen) == set(bodies)


def test_changed_tax_reference_never_advances_snapshot(monkeypatch):
    async def collect():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, content=b"changed"))) as client:
            return await prices.collect_snapshot(client)
    with pytest.raises(ValueError, match="Tax reference"):
        asyncio.run(collect())


def test_public_reference_redirect_is_not_followed():
    seen = []
    def handler(request):
        seen.append(request)
        return httpx.Response(302, headers={"Location": "https://other.example/private"})
    async def collect():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False) as client:
            await prices.collect_snapshot(client)
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(collect())
    assert len(seen) == 1


def test_fresh_snapshot_recovers_expired_env_without_restart_or_usage_reset(production, monkeypatch):
    google_usage.reserve_call("geocoding", 1)
    monkeypatch.setenv("GOOGLE_BUDGET_LIMIT_TL", "100")
    monkeypatch.setenv("GOOGLE_PRICE_AUTO_REFRESH_ENABLED", "true")
    monkeypatch.setenv("GOOGLE_PRICE_VERIFIED_AT", (datetime.now(timezone.utc) - timedelta(days=8)).isoformat())
    get_settings.cache_clear()
    assert not google_usage.usage_status()["available"]
    with get_conn() as conn:
        before = [dict(row) for row in conn.execute("SELECT * FROM google_api_usage ORDER BY id")]
    settings = get_settings()
    prices.save_snapshot(snapshot())
    assert get_settings() is settings
    assert google_usage.usage_status()["available"]
    assert google_usage.verified_prices() == snapshot().unit_prices_tl
    assert prices.snapshot_path().stat().st_mode & 0o777 == 0o600
    with get_conn() as conn:
        assert [dict(row) for row in conn.execute("SELECT * FROM google_api_usage ORDER BY id")] == before
    assert settings.google_budget_limit_tl == 100
    assert google_usage.usage_status()["used_today"] == 1
    assert google_usage.usage_status()["estimated_cost_tl"] == 1


def test_invalid_file_does_not_fall_back_to_fresh_env_prices(production, monkeypatch):
    monkeypatch.setenv("GOOGLE_PRICE_AUTO_REFRESH_ENABLED", "true")
    get_settings.cache_clear()
    prices.snapshot_path().write_text('{"unit_prices_tl":{}}')
    assert not google_usage.usage_status()["available"]
    with pytest.raises(google_usage.GoogleUsageBlocked):
        google_usage.reserve_call("geocoding", 1)


def test_auto_refreshed_prices_still_enforce_existing_budget(production, monkeypatch):
    monkeypatch.setenv("GOOGLE_PRICE_AUTO_REFRESH_ENABLED", "true")
    monkeypatch.setenv("GOOGLE_BUDGET_LIMIT_TL", "0.9")
    get_settings.cache_clear()
    prices.save_snapshot(snapshot())
    google_usage.reserve_call("geocoding", 1)
    google_usage.reserve_call("geocoding", 1)
    with pytest.raises(google_usage.GoogleUsageBlocked, match="bütçesi"):
        google_usage.reserve_call("geocoding", 1)
    status = google_usage.usage_status()
    assert status["used_today"] == 2 and status["estimated_cost_tl"] == .9


def test_atomic_write_failure_preserves_last_good_snapshot(production, monkeypatch):
    original = snapshot()
    prices.save_snapshot(original)
    before = prices.snapshot_path().read_bytes()
    existing = sorted(path.name for path in prices.snapshot_path().parent.iterdir())
    monkeypatch.setattr(prices.os, "replace", lambda *_: (_ for _ in ()).throw(OSError("test disk failure")))
    with pytest.raises(OSError):
        prices.save_snapshot(original)
    assert prices.snapshot_path().read_bytes() == before
    assert sorted(path.name for path in prices.snapshot_path().parent.iterdir()) == existing


def test_failed_refresh_is_retried_without_discarding_last_good_snapshot(production, monkeypatch):
    monkeypatch.setenv("GOOGLE_PRICE_AUTO_REFRESH_ENABLED", "true")
    get_settings.cache_clear()
    prices.save_snapshot(snapshot())
    before = prices.snapshot_path().read_bytes()
    refresh = AsyncMock(side_effect=ValueError("source changed"))
    monkeypatch.setattr(prices, "refresh_once", refresh)
    delays = []
    async def stop(delay):
        delays.append(delay)
        raise asyncio.CancelledError
    monkeypatch.setattr(prices.asyncio, "sleep", stop)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(prices.refresh_loop())
    assert delays == [prices.RETRY_SECONDS] and refresh.await_count == 1
    assert prices.snapshot_path().read_bytes() == before


def test_healthy_refresh_is_scheduled_before_seven_day_expiry(production, monkeypatch):
    monkeypatch.setenv("GOOGLE_PRICE_AUTO_REFRESH_ENABLED", "true")
    get_settings.cache_clear()
    refresh = AsyncMock()
    monkeypatch.setattr(prices, "refresh_once", refresh)
    delays = []
    async def stop(delay):
        delays.append(delay)
        raise asyncio.CancelledError
    monkeypatch.setattr(prices.asyncio, "sleep", stop)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(prices.refresh_loop())
    assert delays == [6 * 3600] and refresh.await_count == 1


def test_closed_google_calls_still_refresh_public_prices_without_resetting_usage(production, monkeypatch):
    google_usage.reserve_call("geocoding", 1)
    with get_conn() as conn:
        before = [dict(row) for row in conn.execute("SELECT * FROM google_api_usage ORDER BY id")]
    monkeypatch.setenv("GOOGLE_PRICE_AUTO_REFRESH_ENABLED", "true")
    monkeypatch.setenv("GOOGLE_MAPS_CALLS_ENABLED", "false")
    monkeypatch.setenv("GOOGLE_PRICE_VERIFIED_AT", (datetime.now(timezone.utc) - timedelta(days=8)).isoformat())
    get_settings.cache_clear()
    async def refresh():
        prices.save_snapshot(snapshot())
    reference_refresh = AsyncMock(side_effect=refresh)
    monkeypatch.setattr(prices, "refresh_once", reference_refresh)
    async def stop(_delay):
        raise asyncio.CancelledError
    monkeypatch.setattr(prices.asyncio, "sleep", stop)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(prices.refresh_loop())
    reference_refresh.assert_awaited_once()
    assert google_usage.verified_prices() == snapshot().unit_prices_tl
    assert not get_settings().google_maps_calls_enabled
    assert not google_usage.usage_status()["available"]
    with get_conn() as conn:
        assert [dict(row) for row in conn.execute("SELECT * FROM google_api_usage ORDER BY id")] == before


@pytest.mark.parametrize("setting,value", [("GOOGLE_PRICE_AUTO_REFRESH_ENABLED", "false"), ("GOOGLE_MAPS_API_KEY", "")])
def test_production_refresh_respects_disabled_refresher_or_missing_key(production, monkeypatch, setting, value):
    monkeypatch.setenv("GOOGLE_PRICE_AUTO_REFRESH_ENABLED", "true")
    monkeypatch.setenv(setting, value)
    get_settings.cache_clear()
    refresh = AsyncMock()
    monkeypatch.setattr(prices, "refresh_once", refresh)
    asyncio.run(prices.refresh_loop())
    refresh.assert_not_awaited()


def test_local_or_disabled_instance_never_starts_reference_fetch(monkeypatch):
    refresh = AsyncMock()
    monkeypatch.setattr(prices, "refresh_once", refresh)
    asyncio.run(prices.refresh_loop())
    refresh.assert_not_awaited()
