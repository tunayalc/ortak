"""Venue and event types users can pick. Each maps to Google Places (New) Table A types.

Escape rooms, billiards, board-game cafes and climbing/trampoline parks have no Google
type of their own. They are searched through broader types and kept only when the place
name matches (``name_only``), so a plain cafe is never presented as a board-game cafe.
"""
from __future__ import annotations

def _c(group, label, types, keywords=(), name_only=False):
    return {"group": group, "label": label, "types": list(types), "keywords": list(keywords), "name_only": name_only}


CATALOG: dict[str, dict] = {
    # Yeme içme
    "cafe": _c("Yeme içme", "Kafe", ["cafe"]),
    "restaurant": _c("Yeme içme", "Restoran", ["restaurant"]),
    "breakfast": _c("Yeme içme", "Kahvaltı", ["breakfast_restaurant", "brunch_restaurant"], ["kahvaltı"]),
    "dessert": _c("Yeme içme", "Tatlı ve pastane", ["dessert_shop", "bakery", "ice_cream_shop"]),
    "tea_house": _c("Yeme içme", "Çay evi ve çay bahçesi", ["tea_house"], ["çay bahçesi"]),
    "fast_food": _c("Yeme içme", "Fast food", ["fast_food_restaurant", "pizza_restaurant", "hamburger_restaurant"]),
    "bar": _c("Yeme içme", "Bar ve pub", ["bar", "pub"]),
    # Aktif ve macera
    "paintball": _c("Aktif ve macera", "Paintball ve macera sporları", ["paintball_center", "adventure_sports_center"],
                    ["paintball", "airsoft", "lazer tag", "laser tag"]),
    "go_kart": _c("Aktif ve macera", "Go-kart", ["go_karting_venue"], ["karting", "go-kart", "go kart"]),
    "escape_room": _c("Aktif ve macera", "Kaçış odası", ["amusement_center"], ["escape", "kaçış", "gizem odası"], name_only=True),
    "climbing": _c("Aktif ve macera", "Tırmanış ve trambolin", ["sports_activity_location", "sports_club"],
                   ["tırmanış", "climbing", "trambolin", "trampoline", "boulder"], name_only=True),
    "sports": _c("Aktif ve macera", "Spor tesisi", ["sports_complex", "stadium", "athletic_field"]),
    "fitness": _c("Aktif ve macera", "Spor salonu", ["gym", "fitness_center"]),
    "swimming": _c("Aktif ve macera", "Yüzme ve havuz", ["swimming_pool", "water_park"]),
    "ice_skating": _c("Aktif ve macera", "Buz pateni", ["ice_skating_rink"]),
    "golf": _c("Aktif ve macera", "Minigolf ve golf", ["miniature_golf_course", "golf_course"], ["minigolf", "mini golf"]),
    "cycling": _c("Aktif ve macera", "Bisiklet ve skatepark", ["cycling_park", "skateboard_park"]),
    "boat": _c("Aktif ve macera", "Tekne ve marina", ["marina"], ["tekne", "boat"]),
    "hiking": _c("Aktif ve macera", "Doğa yürüyüşü ve piknik", ["hiking_area", "picnic_ground", "national_park", "state_park"]),
    # Eğlence
    "bowling": _c("Eğlence", "Bowling", ["bowling_alley"]),
    "billiards": _c("Eğlence", "Bilardo", ["amusement_center"], ["bilardo", "billiard", "snooker"], name_only=True),
    "arcade": _c("Eğlence", "Oyun salonu ve internet kafe", ["video_arcade", "internet_cafe", "amusement_center"], ["arcade", "playstation"]),
    "board_game": _c("Eğlence", "Kutu oyunu kafesi", ["cafe"], ["oyun kafe", "board game", "kutu oyunu", "mangala"], name_only=True),
    "cinema": _c("Eğlence", "Sinema", ["movie_theater"]),
    "theater": _c("Eğlence", "Tiyatro ve konser", ["performing_arts_theater", "concert_hall", "opera_house", "philharmonic_hall"]),
    "karaoke": _c("Eğlence", "Karaoke", ["karaoke"]),
    "night_club": _c("Eğlence", "Gece kulübü ve dans", ["night_club", "dance_hall"]),
    "amusement_park": _c("Eğlence", "Eğlence parkı", ["amusement_park", "ferris_wheel", "roller_coaster"]),
    "event_venue": _c("Eğlence", "Etkinlik salonu", ["event_venue", "banquet_hall", "community_center", "convention_center"]),
    # Kültür ve gezi
    "museum": _c("Kültür ve gezi", "Müze", ["museum"]),
    "art_gallery": _c("Kültür ve gezi", "Sanat galerisi", ["art_gallery", "cultural_center"]),
    "library": _c("Kültür ve gezi", "Kütüphane", ["library"]),
    "bookstore": _c("Kültür ve gezi", "Kitapçı", ["book_store"]),
    "historic": _c("Kültür ve gezi", "Tarihi yer", ["historical_landmark", "monument", "cultural_landmark"]),
    "planetarium": _c("Kültür ve gezi", "Planetaryum ve gözlem noktası", ["planetarium", "observation_deck"]),
    "tourist_attraction": _c("Kültür ve gezi", "Gezilecek yer", ["tourist_attraction", "visitor_center"]),
    # Doğa ve hayvanlar
    "park": _c("Doğa ve hayvanlar", "Park", ["park", "garden"]),
    "botanical": _c("Doğa ve hayvanlar", "Botanik bahçesi", ["botanical_garden"]),
    "aquarium_zoo": _c("Doğa ve hayvanlar", "Akvaryum ve hayvanat bahçesi", ["aquarium", "zoo", "wildlife_park"]),
    "dog_park": _c("Doğa ve hayvanlar", "Köpek parkı", ["dog_park"]),
    "playground": _c("Doğa ve hayvanlar", "Çocuk oyun alanı", ["playground"]),
    # Dinlenme ve alışveriş
    "spa": _c("Dinlenme ve alışveriş", "Spa ve hamam", ["spa"], ["hamam"]),
    "shopping_mall": _c("Dinlenme ve alışveriş", "Alışveriş merkezi", ["shopping_mall"]),
    "market": _c("Dinlenme ve alışveriş", "Pazar ve çarşı", ["market"], ["pazar", "çarşı", "bazaar"]),
}
CATEGORY_IDS = tuple(CATALOG)
MAX_SELECTED = 5


def public_catalog() -> list[dict]:
    """Id, label and group only; Google type details stay on the server."""
    return [{"id": key, "label": value["label"], "group": value["group"]} for key, value in CATALOG.items()]


def labels() -> dict[str, str]:
    return {key: value["label"] for key, value in CATALOG.items()}


def normalize_categories(values: list[str] | None, fallback: str = "cafe") -> list[str]:
    """Unique, known category ids in the given order. Unknown ids are rejected."""
    items = list(dict.fromkeys(item.strip().lower() for item in (values or []) if item and item.strip())) or [fallback]
    unknown = [item for item in items if item not in CATALOG]
    if unknown:
        raise ValueError("Desteklenmeyen mekân türü: " + ", ".join(unknown))
    if len(items) > MAX_SELECTED:
        raise ValueError(f"En fazla {MAX_SELECTED} mekân türü seçilebilir.")
    return items


def google_types(categories: list[str]) -> list[str]:
    return list(dict.fromkeys(kind for key in categories for kind in CATALOG[key]["types"]))


def fold(text: str) -> str:
    """Case-insensitive Turkish match: "KAÇIŞ ODASI" and "kaçış" fold to the same text."""
    return text.replace("I", "ı").replace("İ", "i").lower().replace("ı", "i")


def match_category(categories: list[str], place_types: list[str], name: str) -> str | None:
    """Which selected category a returned place belongs to, or None when it fits none.

    A name match wins. Otherwise a type match counts, except for ``name_only`` categories,
    whose Google types are too broad to prove the activity.
    """
    folded = fold(name)
    for key in categories:
        if any(fold(word) in folded for word in CATALOG[key]["keywords"]):
            return key
    typed = [key for key in categories if not CATALOG[key]["name_only"]]
    if not place_types:
        # Google returned no type list; the request itself only allowed the selected types.
        return typed[0] if typed else None
    for key in typed:
        if set(CATALOG[key]["types"]) & set(place_types):
            return key
    return None


def balanced(items: list[tuple[str, object]], categories: list[str], limit: int) -> list[object]:
    """Up to ``limit`` items taking turns across the selected categories, in result order."""
    queues = {key: [item for category, item in items if category == key] for key in categories}
    chosen: list[object] = []
    while len(chosen) < limit and any(queues.values()):
        for key in categories:
            if queues[key] and len(chosen) < limit:
                chosen.append(queues[key].pop(0))
    return chosen
