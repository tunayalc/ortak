from __future__ import annotations

import hashlib
import json
import math
import random
import uuid
from typing import Any

import httpx

from ..config import get_settings
from ..db import dump_json, get_conn, load_json
from ..schemas import PlaceCandidate, RouteMetric
from .geo import centroid, haversine_m, synthetic_duration_seconds
from .scenario import get_scenario
from .google_transport import google_request
from .google_usage import GoogleUsageBlocked, ensure_operation_capacity
from . import session_store


GOOGLE_PLACES_URL = "https://places.googleapis.com/v1/places:searchNearby"
GOOGLE_ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
PLACES_FIELD_MASK = "places.id,places.displayName,places.formattedAddress,places.location,places.rating,places.userRatingCount,places.priceLevel,places.attributions"
PRICE_LEVELS = {
    "PRICE_LEVEL_FREE": 0,
    "PRICE_LEVEL_INEXPENSIVE": 1,
    "PRICE_LEVEL_MODERATE": 2,
    "PRICE_LEVEL_EXPENSIVE": 3,
    "PRICE_LEVEL_VERY_EXPENSIVE": 4,
}


def _cache_get(provider: str, method: str, cache_key: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT response_json FROM api_cache WHERE provider = ? AND method = ? AND cache_key = ?",
            (provider, method, cache_key),
        ).fetchone()
    if row is None:
        return None
    return load_json(row["response_json"], {})


def _cache_set(provider: str, method: str, cache_key: str, payload: dict[str, Any]) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO api_cache (provider, method, cache_key, response_json)
            VALUES (?, ?, ?, ?)
            """,
            (provider, method, cache_key, dump_json(payload)),
        )


async def _google_get(url: str, params: dict[str, Any], method: str, use_cache: bool = True) -> dict[str, Any]:
    return await google_request(url, params, method)


async def _google_post(url: str, body: dict[str, Any], method: str, field_mask: str) -> dict[str, Any]:
    return await google_request(url, body, method, http_method="POST", field_mask=field_mask)


def _synthetic_candidates(scenario_id: str, max_results: int) -> list[PlaceCandidate]:
    scenario = get_scenario(scenario_id)
    center_lat, center_lng = centroid(scenario.users)
    rng = random.Random(f"{scenario.seed}:{scenario.city}:{scenario.category}:{max_results}")
    labels = [
        "Merkez Nokta",
        "Denge Durağı",
        "Ortak Alan",
        "Kesişim Kafe",
        "Rota Salon",
        "Paylaşım Noktası",
        "Meydan Teras",
        "Ulaşım Merkezi",
        "Ara Durak",
        "Yakın Çevre",
        "Kent Kafe",
        "Toplantı Noktası",
    ]
    candidates: list[PlaceCandidate] = []
    for index in range(max_results):
        spread_m = rng.uniform(250, scenario.radius_m * 0.7)
        lat = center_lat + rng.uniform(-spread_m, spread_m) / 111_320
        lng = center_lng + rng.uniform(-spread_m, spread_m) / (111_320 * 0.77)
        rating = round(rng.uniform(3.5, 4.9), 1)
        review_count = rng.randint(40, 1800)
        price_level = rng.randint(1, 4)
        place_id = f"synthetic-{scenario_id}-{index + 1}"
        candidates.append(
            PlaceCandidate(
                id=str(uuid.uuid4()),
                scenario_id=scenario_id,
                place_id=place_id,
                name=f"{labels[index % len(labels)]} {index + 1}",
                address=f"{scenario.city} sentetik bölge {index + 1}",
                category=scenario.category,
                rating=rating,
                review_count=review_count,
                lat=round(lat, 6),
                lng=round(lng, 6),
                provider="synthetic",
                price_level=price_level,
            )
        )
    return candidates


def _save_candidates(candidates: list[PlaceCandidate], raw_payload: dict[str, Any] | None = None) -> None:
    if candidates and session_store.save_candidates(candidates[0].scenario_id, candidates):
        return
    if not candidates:
        return
    scenario = get_scenario(candidates[0].scenario_id)
    if scenario.session_only or any(item.provider == "google" for item in candidates):
        raise KeyError("Oturum sona erdi; mekân verileri kalıcı kayda alınmadı.")
    with get_conn() as conn:
        for candidate in candidates:
            conn.execute(
                """
                INSERT OR REPLACE INTO place_candidates
                (id, scenario_id, place_id, name, address, category, rating, review_count, lat, lng, provider, price_level, manual_cost, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate.id,
                    candidate.scenario_id,
                    candidate.place_id,
                    candidate.name,
                    candidate.address,
                    candidate.category,
                    candidate.rating,
                    candidate.review_count,
                    candidate.lat,
                    candidate.lng,
                    candidate.provider,
                    candidate.price_level,
                    candidate.manual_cost,
                    dump_json(raw_payload or {}),
                ),
            )


def list_candidates(scenario_id: str) -> list[PlaceCandidate]:
    get_scenario(scenario_id)
    session_candidates = session_store.list_candidates(scenario_id)
    if session_candidates is not None:
        return sorted(session_candidates, key=lambda candidate: (candidate.rating, candidate.review_count), reverse=True)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM place_candidates WHERE scenario_id = ? ORDER BY rating DESC, review_count DESC",
            (scenario_id,),
        ).fetchall()
    return [
        PlaceCandidate(
            id=row["id"],
            scenario_id=row["scenario_id"],
            place_id=row["place_id"],
            name=row["name"],
            address=row["address"],
            category=row["category"],
            rating=row["rating"],
            review_count=row["review_count"],
            lat=row["lat"],
            lng=row["lng"],
            provider=row["provider"],
            price_level=row["price_level"],
            manual_cost=row["manual_cost"],
        )
        for row in rows
    ]


async def search_candidates(scenario_id: str, max_results: int, radius_m: int | None) -> list[PlaceCandidate]:
    scenario = get_scenario(scenario_id)
    settings = get_settings()
    if settings.has_google_key and not scenario.session_only:
        scenario = scenario.model_copy(update={"session_only": True})
        session_store.put_scenario(scenario)
    existing = list_candidates(scenario_id)
    expected_provider = "google" if settings.has_google_key else "synthetic"
    if len(existing) >= min(max_results, 20) and all(item.provider == expected_provider for item in existing):
        return existing[:max_results]

    if not settings.has_google_key:
        candidates = _synthetic_candidates(scenario_id, max_results)
        _save_candidates(candidates)
        return candidates

    center_lat, center_lng = centroid(scenario.users)
    ensure_operation_capacity({"places_nearby_new": 1})
    payload = await _google_post(
        GOOGLE_PLACES_URL,
        {
            "includedTypes": [scenario.category],
            "maxResultCount": min(max_results, 20),
            "languageCode": "tr",
            "locationRestriction": {"circle": {
                "center": {"latitude": center_lat, "longitude": center_lng},
                "radius": float(radius_m or scenario.radius_m),
            }},
        },
        "places_nearby_new",
        PLACES_FIELD_MASK,
    )
    candidates: list[PlaceCandidate] = []
    for item in payload.get("places", [])[:max_results]:
        location = item["location"]
        candidates.append(
            PlaceCandidate(
                id=str(uuid.uuid4()),
                scenario_id=scenario_id,
                place_id=item["id"],
                name=item.get("displayName", {}).get("text") or "Adsız mekân",
                address=item.get("formattedAddress") or "",
                category=scenario.category,
                rating=float(item.get("rating") or 0),
                review_count=int(item.get("userRatingCount") or 0),
                lat=float(location["latitude"]),
                lng=float(location["longitude"]),
                provider="google",
                price_level=PRICE_LEVELS.get(item.get("priceLevel")),
                attributions=item.get("attributions", []),
            )
        )
    _save_candidates(candidates, payload)
    return candidates


def _save_route(metric: RouteMetric, raw_payload: dict[str, Any] | None = None) -> None:
    if session_store.save_route(metric):
        return
    if get_scenario(metric.scenario_id).session_only or metric.provider == "google":
        raise KeyError("Oturum sona erdi; rota verileri kalıcı kayda alınmadı.")
    with get_conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO route_metrics
            (id, scenario_id, user_id, candidate_id, duration_seconds, distance_meters, provider, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                metric.id,
                metric.scenario_id,
                metric.user_id,
                metric.candidate_id,
                metric.duration_seconds,
                metric.distance_meters,
                metric.provider,
                dump_json(raw_payload or {}),
            ),
        )


def list_route_metrics(scenario_id: str) -> list[RouteMetric]:
    get_scenario(scenario_id)
    session_routes = session_store.list_routes(scenario_id)
    if session_routes is not None:
        return session_routes
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM route_metrics WHERE scenario_id = ?", (scenario_id,)).fetchall()
    return [
        RouteMetric(
            id=row["id"],
            scenario_id=row["scenario_id"],
            user_id=row["user_id"],
            candidate_id=row["candidate_id"],
            duration_seconds=row["duration_seconds"],
            distance_meters=row["distance_meters"],
            provider=row["provider"],
        )
        for row in rows
    ]


async def _google_route(
    scenario_id: str,
    user_id: str,
    origin_lat: float,
    origin_lng: float,
    candidate: PlaceCandidate,
    mode: str,
    use_cache: bool = True,
) -> RouteMetric:
    modes = {"driving": "DRIVE", "walking": "WALK", "transit": "TRANSIT", "bicycling": "BICYCLE"}
    params: dict[str, Any] = {
        "origin": {"location": {"latLng": {"latitude": origin_lat, "longitude": origin_lng}}},
        "destination": {"placeId": candidate.place_id} if candidate.provider == "google" else {"location": {"latLng": {"latitude": candidate.lat, "longitude": candidate.lng}}},
        "travelMode": modes[mode],
        "languageCode": "tr",
        "units": "METRIC",
    }
    if mode == "driving":
        params["routingPreference"] = "TRAFFIC_AWARE"
    payload = await _google_post(
        GOOGLE_ROUTES_URL,
        params,
        "routes_compute_routes",
        "routes.duration,routes.distanceMeters",
    )
    routes = payload.get("routes") or []
    if not routes:
        raise RuntimeError("Google Routes bu kişi ve mekân arasında uygun rota bulamadı.")
    route = routes[0]
    distance = float(route.get("distanceMeters", 0))
    duration_text = route["duration"]
    if not isinstance(duration_text, str) or not duration_text.endswith("s"):
        raise RuntimeError("Google Routes geçerli bir yolculuk süresi döndürmedi.")
    duration = float(duration_text[:-1])
    if not all(math.isfinite(value) and value >= 0 for value in (distance, duration)):
        raise RuntimeError("Google Routes geçerli süre ve mesafe değerleri döndürmedi.")
    return RouteMetric(
        id=str(uuid.uuid4()),
        scenario_id=scenario_id,
        user_id=user_id,
        candidate_id=candidate.id,
        duration_seconds=duration,
        distance_meters=distance,
        provider="google",
    )


async def _osrm_route(
    scenario_id: str,
    user_id: str,
    origin_lat: float,
    origin_lng: float,
    candidate: PlaceCandidate,
    use_cache: bool = True,
) -> RouteMetric:
    settings = get_settings()
    params = {
        "coordinates": f"{origin_lng},{origin_lat};{candidate.lng},{candidate.lat}",
        "overview": "false",
    }
    cache_key = hashlib.sha256(
        json.dumps(params, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    cached = _cache_get("osrm", "route_driving", cache_key) if use_cache else None
    payload: dict[str, Any]
    if cached is None:
        url = f"{settings.osrm_base_url.rstrip('/')}/route/v1/driving/{params['coordinates']}"
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.get(url, params={"overview": params["overview"]})
            response.raise_for_status()
            payload = response.json()
        if payload.get("code") != "Ok" or not payload.get("routes"):
            raise RuntimeError(f"OSRM rota isteği başarısız: {payload.get('code')}")
        if use_cache:
            _cache_set("osrm", "route_driving", cache_key, payload)
    else:
        payload = cached

    route = payload["routes"][0]
    return RouteMetric(
        id=str(uuid.uuid4()),
        scenario_id=scenario_id,
        user_id=user_id,
        candidate_id=candidate.id,
        duration_seconds=float(route["duration"]),
        distance_meters=float(route["distance"]),
        provider="osrm",
    )


def _synthetic_route(
    scenario_id: str,
    user_id: str,
    origin_lat: float,
    origin_lng: float,
    candidate: PlaceCandidate,
    mode: str,
) -> RouteMetric:
    distance = haversine_m(origin_lat, origin_lng, candidate.lat, candidate.lng)
    duration = synthetic_duration_seconds(distance, mode)
    return RouteMetric(
        id=str(uuid.uuid4()),
        scenario_id=scenario_id,
        user_id=user_id,
        candidate_id=candidate.id,
        duration_seconds=duration,
        distance_meters=distance,
        provider="synthetic",
    )


async def build_route_matrix(scenario_id: str, provider: str = "auto") -> list[RouteMetric]:
    scenario = get_scenario(scenario_id)
    settings = get_settings()
    candidates = list_candidates(scenario_id)
    if not candidates or (settings.has_google_key and provider in {"google", "auto"} and any(item.provider != "google" for item in candidates)):
        candidates = await search_candidates(scenario_id, settings.public_max_candidates if settings.production else 12, scenario.radius_m)

    existing = list_route_metrics(scenario_id)
    expected_pairs = {(user.id, candidate.id) for user in scenario.users for candidate in candidates}
    desired_provider = provider
    if provider == "auto":
        desired_provider = "google" if settings.has_google_key else "osrm"
    existing_providers = {metric.provider for metric in existing}
    walking_with_synthetic = desired_provider == "osrm" and scenario.travel_mode != "driving"
    provider_matches = (
        {(metric.user_id, metric.candidate_id) for metric in existing} == expected_pairs
        and (
            desired_provider == "auto"
            or existing_providers == {desired_provider}
            or (walking_with_synthetic and existing_providers == {"synthetic"})
        )
    )
    if provider_matches:
        return existing

    use_google = provider == "google" or (provider == "auto" and settings.has_google_key)
    use_osrm = provider == "osrm" or (provider == "auto" and not settings.has_google_key)
    reusable = {(metric.user_id, metric.candidate_id): metric for metric in existing
                if metric.provider == "google" and (metric.user_id, metric.candidate_id) in expected_pairs}
    if use_google:
        ensure_operation_capacity({"routes_compute_routes": len(expected_pairs - reusable.keys())})
    metrics: list[RouteMetric] = []
    for user in scenario.users:
        for candidate in candidates:
            if use_google:
                saved = reusable.get((user.id, candidate.id))
                if saved is not None:
                    metrics.append(saved)
                    continue
                try:
                    metric = await _google_route(
                        scenario_id,
                        user.id,
                        user.lat,
                        user.lng,
                        candidate,
                        scenario.travel_mode,
                        use_cache=not scenario.session_only,
                    )
                    _save_route(metric)
                    metrics.append(metric)
                    continue
                except GoogleUsageBlocked:
                    raise
                except Exception:
                    if provider == "google":
                        raise
            if use_osrm and scenario.travel_mode == "driving":
                try:
                    metric = await _osrm_route(
                        scenario_id,
                        user.id,
                        user.lat,
                        user.lng,
                        candidate,
                        use_cache=not scenario.session_only,
                    )
                    _save_route(metric)
                    metrics.append(metric)
                    continue
                except Exception:
                    if provider == "osrm":
                        raise

            metric = _synthetic_route(
                scenario_id,
                user.id,
                user.lat,
                user.lng,
                candidate,
                scenario.travel_mode,
            )
            _save_route(metric)
            metrics.append(metric)
    return metrics
