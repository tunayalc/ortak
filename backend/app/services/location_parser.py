from __future__ import annotations

import re
import asyncio
import ipaddress
import socket
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import httpx

from ..config import get_settings
from ..schemas import ParsedLocation, ParticipantLocationInput
from .google_transport import google_request


GOOGLE_GEOCODING_URL = "https://maps.googleapis.com/maps/api/geocode/json"
COORD_RE = re.compile(r"(?<![\w.-])(-?\d{1,2}(?:\.\d+)?),\s*(-?\d{1,3}(?:\.\d+)?)(?![\w.-])")
GOOGLE_HOSTS = {"google.com", "www.google.com", "maps.google.com", "google.com.tr", "www.google.com.tr", "maps.google.com.tr", "maps.app.goo.gl", "goo.gl"}


def validate_maps_url(value: str) -> str:
    parsed = urlparse(value)
    if (parsed.scheme != "https" or parsed.hostname not in GOOGLE_HOSTS or parsed.username
            or parsed.password or parsed.port not in (None, 443)):
        raise ValueError("Yalnızca HTTPS Google Maps bağlantıları kabul edilir.")
    return value


async def require_public_host(host: str) -> list[str]:
    records = await asyncio.get_running_loop().getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    if not records or any(not ipaddress.ip_address(record[4][0]).is_global for record in records):
        raise ValueError("Özel ağa yönlenen bağlantılar kabul edilmez.")
    return list(dict.fromkeys(record[4][0] for record in records))


def _valid_coordinate(lat: float, lng: float) -> bool:
    return -90 <= lat <= 90 and -180 <= lng <= 180


def _coordinate_from_text(value: str) -> tuple[float, float] | None:
    decoded = unquote(value)
    for match in COORD_RE.finditer(decoded):
        lat = float(match.group(1))
        lng = float(match.group(2))
        if _valid_coordinate(lat, lng):
            return lat, lng
        raise ValueError("Koordinatlar izin verilen enlem ve boylam aralığında olmalı.")
    return None


def _coordinate_from_url(value: str) -> tuple[float, float] | None:
    decoded = unquote(value)
    parsed = urlparse(decoded)
    query = parse_qs(parsed.query)
    for key in ("q", "query", "destination", "ll"):
        for item in query.get(key, []):
            coordinate = _coordinate_from_text(item)
            if coordinate is not None:
                return coordinate
    return _coordinate_from_text(decoded)


async def _expand_short_url(value: str) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(8, connect=3), follow_redirects=False, trust_env=False) as client:
            target = value
            for _ in range(5):
                validate_maps_url(target)
                host = urlparse(target).hostname
                addresses = await require_public_host(host)
                pinned = httpx.URL(target).copy_with(host=addresses[0])
                # Only headers are needed; never download an unbounded redirect body.
                # Pin the checked IP; retain the real hostname for TLS validation and Host.
                async with client.stream("GET", pinned, headers={"Host": host}, extensions={"sni_hostname": host}) as response:
                    if response.is_redirect:
                        target = urljoin(target, response.headers.get("location", ""))
                        validate_maps_url(target)
                        if _coordinate_from_url(target) is not None:
                            return target
                    elif response.is_success:
                        return target
                    else:
                        return None
    except (httpx.HTTPError, ValueError, OSError):
        return None
    return None


async def _geocode_text(value: str) -> tuple[float, float] | None:
    settings = get_settings()
    if not settings.has_google_key:
        return None
    try:
        payload = await google_request(
            GOOGLE_GEOCODING_URL,
            {"address": value, "language": "tr", "region": "tr"},
            "geocoding_location",
        )
    except Exception:  # noqa: BLE001
        return None
    if payload.get("status") != "OK":
        return None
    location = payload["results"][0]["geometry"]["location"]
    lat = float(location["lat"])
    lng = float(location["lng"])
    return (lat, lng) if _valid_coordinate(lat, lng) else None


async def parse_location_input(item: ParticipantLocationInput) -> ParsedLocation:
    raw_value = item.value.strip()
    label = item.label.strip() or "Katılımcı"
    if not raw_value:
        return ParsedLocation(
            label=label,
            source="missing",
            location_input_type="empty",
            delta_weight=item.delta_weight,
            error="Konum linki veya koordinat boş olamaz.",
        )

    is_url = "://" in raw_value
    source = "google_maps_url" if is_url else "coordinate"
    input_type = "link" if is_url else "coordinate"
    if is_url:
        try:
            validate_maps_url(raw_value)
        except ValueError:
            return ParsedLocation(label=label, source="invalid", location_input_type="link", delta_weight=item.delta_weight,
                                  error="Yalnızca geçerli HTTPS Google Maps bağlantıları kabul edilir.")
    try:
        coordinate = _coordinate_from_url(raw_value) if is_url else _coordinate_from_text(raw_value) if COORD_RE.fullmatch(raw_value) else None
    except ValueError:
        return ParsedLocation(label=label, source="invalid", location_input_type=input_type, delta_weight=item.delta_weight,
                              error="Koordinatlar izin verilen enlem ve boylam aralığında olmalı.")
    if coordinate is None and "://" in raw_value:
        expanded = await _expand_short_url(raw_value)
        if expanded:
            coordinate = _coordinate_from_url(expanded)
            source = "google_maps_redirect"

    if coordinate is None and is_url:
        parsed = urlparse(raw_value)
        query = parse_qs(parsed.query)
        address = (query.get("q") or query.get("query") or query.get("destination") or [""])[0]
        if not address and "/maps/place/" in parsed.path:
            address = unquote(parsed.path.split("/maps/place/", 1)[1].split("/")[0]).replace("+", " ")
        if address and not re.fullmatch(r"[-\d.,\s]+", address):
            coordinate = await _geocode_text(address[:200])
        source = "google_geocoding" if coordinate is not None else source
        input_type = "geocoded_text" if coordinate is not None else input_type

    if coordinate is None:
        return ParsedLocation(
            label=label,
            source=source,
            location_input_type=input_type,
            delta_weight=item.delta_weight,
            error="Konum çözülemedi. Google Maps linki veya lat,lng formatı kullanın.",
        )

    lat, lng = coordinate
    return ParsedLocation(
        label=label,
        lat=round(lat, 6),
        lng=round(lng, 6),
        source=source,
        location_input_type=input_type,
        delta_weight=item.delta_weight,
    )


async def parse_location_inputs(items: list[ParticipantLocationInput]) -> list[ParsedLocation]:
    return [await parse_location_input(item) for item in items]
