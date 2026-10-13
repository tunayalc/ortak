from __future__ import annotations

from math import asin, cos, radians, sin, sqrt

from ..schemas import SyntheticUser


CITY_CENTERS: dict[str, tuple[float, float]] = {
    "ankara": (39.9208, 32.8541),
    "istanbul": (41.0082, 28.9784),
    "izmir": (38.4237, 27.1428),
    "eskisehir": (39.7667, 30.5256),
    "bursa": (40.1828, 29.0663),
    "antalya": (36.8969, 30.7133),
}


def city_center(city: str) -> tuple[float, float]:
    return CITY_CENTERS.get(city.lower().strip(), CITY_CENTERS["ankara"])


def centroid(points: list[SyntheticUser]) -> tuple[float, float]:
    return (
        sum(point.lat for point in points) / len(points),
        sum(point.lng for point in points) / len(points),
    )


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius_m = 6_371_000
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return 2 * radius_m * asin(sqrt(a))


def synthetic_duration_seconds(distance_m: float, mode: str) -> float:
    speeds_kmh = {
        "walking": 4.8,
        "bicycling": 14.0,
        "driving": 28.0,
        "transit": 21.0,
    }
    speed_mps = speeds_kmh.get(mode, 28.0) * 1000 / 3600
    network_factor = 1.28 if mode != "walking" else 1.18
    overhead = 180 if mode in {"driving", "transit"} else 60
    return distance_m * network_factor / speed_mps + overhead

