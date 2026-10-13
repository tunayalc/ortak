from __future__ import annotations

import math
import random
import uuid

from ..config import get_settings
from ..db import dump_json, get_conn, load_json
from ..schemas import Scenario, ScenarioCreate, SyntheticUser
from .geo import city_center
from .location_parser import parse_location_inputs
from .google_transport import google_request
from . import session_store


GOOGLE_GEOCODING_URL = "https://maps.googleapis.com/maps/api/geocode/json"


async def geocode_city_center(city: str) -> tuple[float, float, str]:
    settings = get_settings()
    fallback = city_center(city)
    if not settings.has_google_key:
        return fallback[0], fallback[1], "static"

    params = {"address": f"{city}, Türkiye", "language": "tr", "region": "tr"}
    payload = await google_request(GOOGLE_GEOCODING_URL, params, "geocoding")
    if not payload.get("results"):
        raise ValueError("Google Geocoding belirtilen şehir için konum bulamadı.")
    location = payload["results"][0]["geometry"]["location"]
    return float(location["lat"]), float(location["lng"]), "google-geocoding"


def _synthetic_users(
    city: str,
    group_size: int,
    radius_m: int,
    seed: int,
    center: tuple[float, float],
) -> list[SyntheticUser]:
    rng = random.Random(seed)
    center_lat, center_lng = center
    users: list[SyntheticUser] = []
    for index in range(group_size):
        angle = rng.uniform(0, 2 * math.pi)
        distance = math.sqrt(rng.random()) * radius_m * 0.95
        lat_offset = math.cos(angle) * distance / 111_320
        lng_offset = math.sin(angle) * distance / (111_320 * max(math.cos(math.radians(center_lat)), 0.1))
        users.append(
            SyntheticUser(
                id=f"user-{index + 1}",
                label=f"Katılımcı {index + 1}",
                lat=round(center_lat + lat_offset, 6),
                lng=round(center_lng + lng_offset, 6),
                source="synthetic",
                location_input_type="synthetic",
                delta_weight=1.0,
            )
        )
    return users


async def create_scenario(payload: ScenarioCreate) -> Scenario:
    settings = get_settings()
    if settings.production:
        session_store.ensure_capacity()
        payload = payload.model_copy(update={"session_only": True})
    scenario_id = str(uuid.uuid4())
    if payload.input_mode == "link":
        if not payload.session_only:
            raise ValueError("Link ile kişi konumu girişinde session_only=true zorunludur.")
        if not payload.participant_locations:
            raise ValueError("Link modunda en az iki kişi konumu girilmelidir.")
        parsed_locations = await parse_location_inputs(payload.participant_locations)
        failed = [item for item in parsed_locations if item.error]
        if failed:
            details = "; ".join(f"{item.label}: {item.error}" for item in failed)
            raise ValueError(f"Konumlar çözülemedi. {details}")
        users = [
            SyntheticUser(
                id=f"user-{index + 1}",
                label=item.label,
                lat=float(item.lat),
                lng=float(item.lng),
                source=item.source,
                location_input_type=item.location_input_type,
                delta_weight=item.delta_weight,
            )
            for index, item in enumerate(parsed_locations)
            if item.lat is not None and item.lng is not None
        ]
        if len(users) < 2:
            raise ValueError("Link modunda en az iki geçerli kişi konumu gereklidir.")
        scenario = Scenario(
            id=scenario_id,
            city=payload.city,
            category=payload.category,
            group_size=len(users),
            travel_mode=payload.travel_mode,
            radius_m=payload.radius_m,
            seed=payload.seed,
            users=users,
            session_only=True,
            input_mode="link",
        )
        session_store.put_scenario(scenario)
        return scenario

    if payload.users and not payload.synthetic_fixture:
        raise ValueError(
            "Özel koordinatlı kullanıcı listeleri yalnızca synthetic_fixture=true ile kabul edilir. "
            "Gerçek kişi konumu göndermeyin."
        )
    center_lat, center_lng = city_center(payload.city) if payload.users else (await geocode_city_center(payload.city))[:2]
    users = payload.users or _synthetic_users(
        payload.city,
        payload.group_size,
        payload.radius_m,
        payload.seed,
        (center_lat, center_lng),
    )
    scenario = Scenario(
        id=scenario_id,
        city=payload.city,
        category=payload.category,
        group_size=len(users),
        travel_mode=payload.travel_mode,
        radius_m=payload.radius_m,
        seed=payload.seed,
        users=users,
        session_only=payload.session_only or settings.has_google_key,
        input_mode=payload.input_mode,
    )
    if scenario.session_only:
        session_store.put_scenario(scenario)
        return scenario
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO scenarios (id, city, category, group_size, travel_mode, radius_m, seed, users_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                scenario.id,
                scenario.city,
                scenario.category,
                scenario.group_size,
                scenario.travel_mode,
                scenario.radius_m,
                scenario.seed,
                dump_json([user.model_dump() for user in users]),
            ),
        )
    return scenario


def get_scenario(scenario_id: str) -> Scenario:
    session_scenario = session_store.get_scenario(scenario_id)
    if session_scenario is not None:
        return session_scenario
    if get_settings().production:
        raise KeyError("Senaryo bulunamadı veya oturum süresi doldu.")
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM scenarios WHERE id = ?", (scenario_id,)).fetchone()
    if row is None:
        raise KeyError("Senaryo bulunamadı veya oturum süresi doldu.")
    users = [SyntheticUser(**item) for item in load_json(row["users_json"], [])]
    return Scenario(
        id=row["id"],
        city=row["city"],
        category=row["category"],
        group_size=row["group_size"],
        travel_mode=row["travel_mode"],
        radius_m=row["radius_m"],
        seed=row["seed"],
        users=users,
        session_only=False,
        input_mode="synthetic",
    )
