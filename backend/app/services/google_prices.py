"""Refresh public price references without credentials or billable API calls."""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_UP
import hashlib
from html.parser import HTMLParser
import logging
import os
from pathlib import Path
import re
import tempfile
from typing import Literal
from xml.etree import ElementTree

import httpx
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from ..config import get_settings
from ..db import _database_path


PRICING_URL = "https://developers.google.com/maps/billing-and-pricing/pricing"
FX_URL = "https://www.tcmb.gov.tr/kurlar/today.xml"
VAT_URL = "https://cdn.gib.gov.tr/api/gibportal-file/file/getFileResources?objectKey=arsiv%2Fyardim-kaynaklar%2Fyararli-bilgiler%2Fkdv-oranlari.pdf"
# Reviewed first-page standard rate: 20%. A changed publication requires review.
VAT_SHA256 = "8589f10107826271cced2af2ce6ce8c6d938089554fa2edb84cf8e6d56118bcc"
SKU_IDS = {"geocoding": "BAC8-4E68-E261", "places_nearby_new": "772E-9975-BE34", "routes_compute_routes": "02F7-1B55-DC90"}
OPERATIONS = {*SKU_IDS, "geocoding_location"}
MAX_AGE_SECONDS = 7 * 86400
REFRESH_SECONDS = 6 * 3600
RETRY_SECONDS = 15 * 60
MAX_SOURCE_BYTES = 6 * 1024 * 1024
logger = logging.getLogger(__name__)


class PriceSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1] = 1
    verified_at: AwareDatetime
    fx_date: date
    fx_usd_try: float = Field(gt=0, allow_inf_nan=False)
    reserved_fx_usd_try: float = Field(ge=60, allow_inf_nan=False)
    vat_reserve_rate: Literal[0.2] = 0.2
    safety_factor: Literal[1.25] = 1.25
    unit_prices_tl: dict[str, float]
    source_sha256: dict[str, str]

    @field_validator("unit_prices_tl")
    @classmethod
    def valid_prices(cls, prices):
        if set(prices) != OPERATIONS or any(not Decimal(str(value)).is_finite() or value <= 0 for value in prices.values()):
            raise ValueError("Invalid unit prices")
        return prices

    @field_validator("source_sha256")
    @classmethod
    def valid_sources(cls, sources):
        if set(sources) != {PRICING_URL, FX_URL, VAT_URL} or any(not re.fullmatch(r"[a-f0-9]{64}", value) for value in sources.values()):
            raise ValueError("Invalid public price sources")
        if sources[VAT_URL] != VAT_SHA256:
            raise ValueError("Tax reference needs review")
        return sources

    def require_current(self, now: datetime | None = None):
        now = now or datetime.now(timezone.utc)
        age = (now - self.verified_at).total_seconds()
        fx_age = (now.date() - self.fx_date).days
        if not 0 <= age <= MAX_AGE_SECONDS or not 0 <= fx_age <= 7:
            raise ValueError("Price reference is stale or in the future")
        return self


class PriceTableParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.text = []
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        elif tag in {"th", "td"} and self.row is not None:
            self.cell = []

    def handle_data(self, value):
        self.text.append(value)
        if self.cell is not None:
            self.cell.append(value)

    def handle_endtag(self, tag):
        if tag in {"th", "td"} and self.row is not None and self.cell is not None:
            self.row.append(" ".join(" ".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None


def parse_google_prices(body: bytes) -> dict[str, Decimal]:
    parser = PriceTableParser()
    parser.feed(body.decode("utf-8"))
    text = " ".join(" ".join(parser.text).lower().split())
    if "costs - per 1000 events" not in text or "prices - usd" not in text:
        raise ValueError("Unrecognized pricing units")
    result = {}
    for operation, sku in SKU_IDS.items():
        rows = [row for row in parser.rows if row and re.search(r"\b" + re.escape(sku) + r"\b", row[0])]
        if len(rows) != 1 or len(rows[0]) < 3:
            raise ValueError("Missing or ambiguous SKU")
        # First paid tier, not the free monthly allowance or a volume discount.
        match = re.fullmatch(r"\$\s*(\d+(?:\.\d+)?)", rows[0][2])
        if not match or not 0 < Decimal(match[1]) <= 100000:
            raise ValueError("Invalid first-tier price")
        result[operation] = Decimal(match[1]) / 1000
    result["geocoding_location"] = result["geocoding"]
    return result


def parse_fx(body: bytes, now: datetime) -> tuple[date, Decimal]:
    if b"<!DOCTYPE" in body.upper() or b"<!ENTITY" in body.upper():
        raise ValueError("Unexpected XML declarations")
    root = ElementTree.fromstring(body)
    stamp = datetime.strptime(root.attrib["Tarih"], "%d.%m.%Y").date()
    usd = root.findall("Currency[@Kod='USD']")
    if len(usd) != 1 or usd[0].findtext("Unit") != "1":
        raise ValueError("Invalid USD quotation")
    try:
        rate = Decimal(usd[0].findtext("ForexSelling", ""))
    except InvalidOperation:
        raise ValueError("Invalid FX rate") from None
    if not rate.is_finite() or rate <= 0 or not 0 <= (now.date() - stamp).days <= 7:
        raise ValueError("Invalid or outdated FX rate")
    return stamp, rate


async def fetch_source(client: httpx.AsyncClient, url: str) -> bytes:
    async with client.stream("GET", url) as response:
        response.raise_for_status()
        result = bytearray()
        async for chunk in response.aiter_bytes():
            if len(result) + len(chunk) > MAX_SOURCE_BYTES:
                raise ValueError("Public source exceeds size limit")
            result.extend(chunk)
        return bytes(result)


async def collect_snapshot(client: httpx.AsyncClient, now: datetime | None = None) -> PriceSnapshot:
    bodies = {}
    for url in (PRICING_URL, FX_URL, VAT_URL):
        bodies[url] = await fetch_source(client, url)
    hashes = {url: hashlib.sha256(body).hexdigest() for url, body in bodies.items()}
    if hashes[VAT_URL] != VAT_SHA256:
        raise ValueError("Tax reference changed; operator review required")
    now = now or datetime.now(timezone.utc)
    usd_prices = parse_google_prices(bodies[PRICING_URL])
    fx_date, fx = parse_fx(bodies[FX_URL], now)
    reserved_fx = max(Decimal("60"), fx * Decimal("1.20"))
    prices = {key: float((value * reserved_fx * Decimal("1.20") * Decimal("1.25")).quantize(Decimal("0.0001"), rounding=ROUND_UP))
              for key, value in usd_prices.items()}
    return PriceSnapshot(verified_at=now, fx_date=fx_date, fx_usd_try=float(fx),
                         reserved_fx_usd_try=float(reserved_fx), unit_prices_tl=prices,
                         source_sha256=hashes).require_current(now)


def snapshot_path() -> Path:
    return _database_path().with_name("google-prices.json")


def load_snapshot() -> PriceSnapshot | None:
    path = snapshot_path()
    if not path.exists():
        return None
    with path.open("rb") as handle:
        body = handle.read(32769)
    if len(body) > 32768:
        raise ValueError("Price snapshot exceeds size limit")
    return PriceSnapshot.model_validate_json(body).require_current()


def save_snapshot(snapshot: PriceSnapshot) -> None:
    snapshot.require_current()
    path = snapshot_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            os.chmod(temporary, 0o600)
            handle.write(snapshot.model_dump_json(indent=2))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


async def refresh_once() -> PriceSnapshot:
    async with httpx.AsyncClient(timeout=20, follow_redirects=False, trust_env=False) as client:
        snapshot = await collect_snapshot(client)
    save_snapshot(snapshot)
    return snapshot


async def refresh_loop() -> None:
    settings = get_settings()
    # Public references must be ready before billable calls can be enabled.
    if not (settings.production and settings.google_price_auto_refresh_enabled
            and settings.has_google_key):
        return
    while True:
        try:
            await refresh_once()
            delay = REFRESH_SECONDS
        except (httpx.HTTPError, OSError, ValueError, KeyError, ElementTree.ParseError):
            # A failed refresh must neither advance the timestamp nor reset usage.
            logger.warning("Public price refresh failed; retaining last verified snapshot.")
            delay = RETRY_SECONDS
        await asyncio.sleep(delay)
