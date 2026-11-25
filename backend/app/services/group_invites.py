"""Group invitations and rooms ("oda"). Guest capabilities travel in POST bodies, never paths.

Two kinds exist:

* A fixed-size invite (kept for older app versions) has one private link per seat.
* A room has one shareable join link. Whoever opens it takes a seat, writes a name and adds
  a starting point; a private seat token on their device lets them change it later.

A room can be saved for a group of friends who meet often. A saved room keeps only its name,
the join link and each member's name and preferred travel mode; starting points, votes and
results stay in memory and disappear within two hours, as for every other meeting. Saved rooms
unused for SAVED_ROOM_DAYS are deleted. Every token is stored as a SHA-256 hash.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from secrets import token_urlsafe
from time import monotonic
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from ..config import get_settings
from ..db import get_conn
from ..schemas import TRAVEL_MODES, Coordinate
from . import session_store

router = APIRouter(prefix="/groups")
MEETING_SECONDS = 7140
SAVED_ROOM_DAYS = 90
MAX_LIVE_GROUPS = 300


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass
class Seat:
    key: str  # hash of the seat token
    token: str | None = None  # plain token, fixed-size invites only (the host shares it)
    location: Coordinate | None = None
    vote: str | None = None
    name: str = ""
    travel_mode: str | None = None

    @classmethod
    def new(cls, **values):
        token = token_urlsafe(32)
        return cls(key=digest(token), **values), token


@dataclass
class Group:
    id: str
    seats: list[Seat]
    expires: float
    choices: dict = field(default_factory=dict)
    scenario: str = ""
    room: bool = False
    name: str = ""
    join_key: str | None = None  # hash of the join token
    join: str | None = None  # plain join token while known in this process
    saved: bool = False

    def counted(self):
        """Seats in a search: every seat of an invite, only seats with a point in a room."""
        return [s for s in self.seats if s.location] if self.room else self.seats


groups: dict[str, Group] = {}
hosts: dict[str, str] = {}  # host session id -> group id


def cleanup():
    now = monotonic()
    for key in [k for k, g in groups.items() if g.expires <= now]:
        del groups[key]
    for session in [s for s, g in hosts.items() if g not in groups]:
        del hosts[session]


def purge_saved_rooms() -> None:
    cutoff = int(time.time()) - SAVED_ROOM_DAYS * 86400
    with get_conn() as conn:
        old = [row["id"] for row in conn.execute("SELECT id FROM saved_rooms WHERE updated_at < ?", (cutoff,))]
        for room_id in old:
            conn.execute("DELETE FROM saved_room_members WHERE room_id = ?", (room_id,))
            conn.execute("DELETE FROM saved_rooms WHERE id = ?", (room_id,))


def owner(request):
    if "id" not in request.session:
        request.session["id"] = token_urlsafe(24)
    return request.session["id"]


def hosted(request) -> Group | None:
    cleanup()
    return groups.get(hosts.get(owner(request), ""))


def require_group(request) -> Group:
    group = hosted(request)
    if not group:
        raise HTTPException(404, "Davet sona erdi veya bu oturuma ait değil.")
    return group


def require_room(request) -> Group:
    group = require_group(request)
    if not group.room:
        raise HTTPException(409, "Bu işlem yalnızca odalar için kullanılabilir.")
    return group


def ballot(group):
    return [dict(choice, votes=sum(s.vote == key for s in group.seats)) for key, choice in group.choices.items()]


def summary(group):
    base = {"choices": ballot(group), "expires_in": max(0, int(group.expires - monotonic()))}
    if not group.room:
        return {**base, "seats": [{"token": s.token, "ready": s.location is not None} for s in group.seats]}
    return {**base, "room": True, "name": group.name, "saved": group.saved, "join": group.join,
            "capacity": get_settings().public_max_participants,
            "seats": [{"name": s.name, "ready": s.location is not None, "travel_mode": s.travel_mode} for s in group.seats]}


def clean_name(value: str | None, limit: int = 40) -> str:
    return " ".join((value or "").split())[:limit]


def check_mode(value: str | None) -> str | None:
    if value in (None, ""):
        return None
    if value not in TRAVEL_MODES:
        raise ValueError("Desteklenmeyen ulaşım biçimi.")
    return value


def touch(room_id: str) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE saved_rooms SET updated_at = ? WHERE id = ?", (int(time.time()), room_id))


def store_members(group: Group) -> None:
    if not group.saved:
        return
    with get_conn() as conn:
        conn.execute("DELETE FROM saved_room_members WHERE room_id = ?", (group.id,))
        conn.executemany(
            "INSERT INTO saved_room_members (key_hash, room_id, position, name, travel_mode) VALUES (?, ?, ?, ?, ?)",
            [(s.key, group.id, i, s.name, s.travel_mode) for i, s in enumerate(group.seats)],
        )
        conn.execute("UPDATE saved_rooms SET name = ?, updated_at = ? WHERE id = ?", (group.name, int(time.time()), group.id))


def load_saved(where: str, value: str) -> Group | None:
    """A saved room, live in memory or loaded from the database (without any starting point)."""
    with get_conn() as conn:
        if where == "member":
            row = conn.execute("SELECT r.* FROM saved_rooms r JOIN saved_room_members m ON m.room_id = r.id WHERE m.key_hash = ?", (value,)).fetchone()
        else:
            row = conn.execute(f"SELECT * FROM saved_rooms WHERE {where}_hash = ?", (value,)).fetchone()
        if row is None:
            return None
        if row["id"] in groups:
            return groups[row["id"]]
        if len(groups) >= MAX_LIVE_GROUPS:
            raise HTTPException(429, "Grup kapasitesi aşıldı.")
        members = conn.execute("SELECT * FROM saved_room_members WHERE room_id = ? ORDER BY position", (row["id"],)).fetchall()
        conn.execute("UPDATE saved_rooms SET updated_at = ? WHERE id = ?", (int(time.time()), row["id"]))
    group = Group(id=row["id"], seats=[Seat(key=m["key_hash"], name=m["name"], travel_mode=m["travel_mode"]) for m in members],
                  expires=monotonic() + MEETING_SECONDS, room=True, name=row["name"], join_key=row["join_hash"], saved=True)
    groups[group.id] = group
    return group


def find_room_by_join(join: str) -> Group | None:
    key = digest(join)
    for group in groups.values():
        if group.room and group.join_key == key:
            return group
    return load_saved("join", key)


def find_seat(token: str) -> tuple[Group, Seat] | None:
    key = digest(token)
    for group in groups.values():
        for seat in group.seats:
            if seat.key == key:
                return group, seat
    group = load_saved("member", key)
    if group:
        return next(((group, s) for s in group.seats if s.key == key), None)
    return None


class NewGroup(BaseModel):
    size: int | None = Field(default=None, ge=2, le=12)
    room: bool = False
    name: str | None = Field(default=None, max_length=40)


@router.post("")
async def create(request: Request, body: NewGroup):
    cleanup()
    session = owner(request)
    if session in hosts:
        raise HTTPException(409, "Önce mevcut daveti kapatın.")
    if not body.room and body.size is None:
        raise HTTPException(422, "Kişi sayısı veya oda seçimi gerekli.")
    if (body.size or 0) > get_settings().public_max_participants or len(groups) >= 100:
        raise HTTPException(429, "Grup kapasitesi aşıldı.")
    group_id = token_urlsafe(12)
    if body.room:
        join = token_urlsafe(32)
        group = Group(id=group_id, seats=[], expires=monotonic() + MEETING_SECONDS, room=True,
                      name=clean_name(body.name) or "Oda", join_key=digest(join), join=join)
    else:
        seats = []
        for _ in range(body.size):
            seat, token = Seat.new()
            seat.token = token
            seats.append(seat)
        group = Group(id=group_id, seats=seats, expires=monotonic() + MEETING_SECONDS)
    groups[group_id] = group
    hosts[session] = group_id
    return summary(group)


@router.get("/mine")
async def mine(request: Request):
    group = hosted(request)
    return summary(group) if group else None


@router.delete("/mine", status_code=204)
async def close(request: Request):
    """End the current meeting. A saved room stays saved; its points and votes are cleared."""
    group = groups.get(hosts.pop(owner(request), ""))
    if group:
        del groups[group.id]
        if group.saved:
            touch(group.id)


class RoomName(BaseModel):
    name: str = Field(min_length=1, max_length=40)


@router.post("/save")
async def save(request: Request, body: RoomName):
    """Keep the room for later meetings. Returns the owner key once; the device stores it."""
    group = require_room(request)
    name = clean_name(body.name)
    if not name:
        raise HTTPException(422, "Oda adını yazın.")
    if group.saved:
        raise HTTPException(409, "Oda zaten kayıtlı.")
    key = token_urlsafe(32)
    group.name, group.saved = name, True
    with get_conn() as conn:
        conn.execute("INSERT INTO saved_rooms (id, owner_hash, join_hash, name, updated_at) VALUES (?, ?, ?, ?, ?)",
                     (group.id, digest(key), group.join_key, name, int(time.time())))
    store_members(group)
    return {**summary(group), "owner_key": key}


@router.post("/rename")
async def rename(request: Request, body: RoomName):
    group = require_room(request)
    name = clean_name(body.name)
    if not name:
        raise HTTPException(422, "Oda adını yazın.")
    group.name = name
    store_members(group)
    return summary(group)


class OwnerKey(BaseModel):
    key: str = Field(min_length=43, max_length=43, pattern=r"^[A-Za-z0-9_-]+$")


@router.post("/open")
async def open_saved(request: Request, body: OwnerKey):
    cleanup()
    group = load_saved("owner", digest(body.key))
    if not group:
        raise HTTPException(404, "Kayıtlı oda bulunamadı; 90 gün kullanılmayan odalar silinir.")
    session = owner(request)
    previous = groups.get(hosts.get(session, ""))
    if previous and previous.id != group.id and not previous.saved:
        del groups[previous.id]
    hosts[session] = group.id
    return summary(group)


@router.post("/forget", status_code=204)
async def forget(request: Request, body: OwnerKey):
    """Delete a saved room and its member names for good."""
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM saved_rooms WHERE owner_hash = ?", (digest(body.key),)).fetchone()
        if row is None:
            raise HTTPException(404, "Kayıtlı oda bulunamadı.")
        conn.execute("DELETE FROM saved_room_members WHERE room_id = ?", (row["id"],))
        conn.execute("DELETE FROM saved_rooms WHERE id = ?", (row["id"],))
    groups.pop(row["id"], None)
    cleanup()


class SeatIndex(BaseModel):
    seat: int = Field(ge=1, le=12)


@router.post("/remove")
async def remove(request: Request, body: SeatIndex):
    """The host removes a member, for example someone who received a forwarded link."""
    group = require_room(request)
    if body.seat > len(group.seats):
        raise HTTPException(404, "Bu kişi odada yok.")
    if group.choices:
        raise HTTPException(409, "Oylama sırasında kişi çıkarılamaz.")
    del group.seats[body.seat - 1]
    store_members(group)
    return summary(group)


@router.post("/locations")
async def locations(request: Request):
    group = require_group(request)
    if not group.room:
        if not all(s.location for s in group.seats):
            raise HTTPException(409, "Tüm katılımcılar başlangıç noktalarını eklemeli.")
        return [s.location for s in group.seats]
    seats = group.counted()
    if len(seats) < 2:
        raise HTTPException(409, "Odada konumunu ekleyen en az iki kişi olmalı.")
    return [{"lat": s.location.lat, "lng": s.location.lng, "label": s.name or f"Kişi {i + 1}", "travel_mode": s.travel_mode}
            for i, s in enumerate(seats)]


class OpenBallot(BaseModel):
    scenario_id: str = Field(min_length=1, max_length=100)
    candidates: list[str] = Field(min_length=2, max_length=3)


@router.post("/ballot")
async def open_ballot(request: Request, body: OpenBallot):
    group = require_group(request)
    scenario = session_store.get_scenario(body.scenario_id)
    seats = group.counted()
    if not scenario or len(scenario.users) != len(seats) or not all(
        s.location and abs(s.location.lat - u.lat) < 0.000001 and abs(s.location.lng - u.lng) < 0.000001
        for s, u in zip(seats, scenario.users)
    ):
        raise HTTPException(409, "Bu sonuçlar davetteki güncel başlangıç noktalarına ait değil.")
    known = {p.id: p for p in session_store.list_candidates(scenario.id) or []}
    routes = {(r.candidate_id, r.user_id) for r in session_store.list_routes(scenario.id) or []}
    if len(set(body.candidates)) != len(body.candidates) or any(
        i not in known or any((i, u.id) not in routes for u in scenario.users) for i in body.candidates
    ):
        raise HTTPException(422, "Tam rotası olan iki veya üç farklı sonuç seçin.")
    if group.choices and (group.scenario != scenario.id or list(group.choices) != body.candidates):
        raise HTTPException(409, "Başlamış oylamanın seçenekleri değiştirilemez.")
    group.scenario = scenario.id
    group.choices = {i: {"id": i, "name": known[i].name, "provider": known[i].provider,
                          "attributions": known[i].attributions} for i in body.candidates}
    return summary(group)


def forget_scenario(scenario_id):
    """The host deleted the scenario: drop its meeting data. Saved rooms keep names only."""
    for key in [k for k, g in groups.items() if g.scenario == scenario_id]:
        group = groups[key]
        if group.saved:
            group.choices.clear()
            group.scenario = ""
            for seat in group.seats:
                seat.location = seat.vote = None
        else:
            del groups[key]


TOKEN = Field(min_length=43, max_length=43, pattern=r"^[A-Za-z0-9_-]+$")


def view(group, seat):
    index = group.seats.index(seat)
    return {"seat": index + 1, "ready": seat.location is not None, "choices": ballot(group), "vote": seat.vote,
            **({"room": True, "room_name": group.name, "name": seat.name, "travel_mode": seat.travel_mode} if group.room else {})}


class JoinRoom(BaseModel):
    join: str = TOKEN
    name: str = Field(min_length=1, max_length=40)


@router.post("/join")
async def join(body: JoinRoom):
    """Take a new seat in a room. The returned seat token is the guest's only key to it."""
    cleanup()
    name = clean_name(body.name)
    if not name:
        raise HTTPException(422, "Adınızı yazın.")
    group = find_room_by_join(body.join)
    if not group:
        raise HTTPException(404, "Oda bağlantısı geçersiz veya oda silinmiş.")
    if group.choices:
        raise HTTPException(409, "Oylama başladı; odaya yeni kişi katılamaz.")
    if len(group.seats) >= get_settings().public_max_participants:
        raise HTTPException(409, "Oda dolu.")
    seat, token = Seat.new(name=name)
    group.seats.append(seat)
    store_members(group)
    return {"token": token, **view(group, seat)}


class GuestAction(BaseModel):
    token: str = TOKEN
    action: Literal["view", "locate", "vote", "withdraw", "leave"] = "view"
    location: Coordinate | None = None
    # Accepted from older clients; the first-launch notice now records consent.
    consent: Literal[True] | None = None
    candidate_id: str | None = Field(default=None, max_length=100)
    name: str | None = Field(default=None, max_length=40)
    travel_mode: str | None = None

    @field_validator("travel_mode")
    @classmethod
    def valid_mode(cls, value: str | None) -> str | None:
        return check_mode(value)


def reset_ballot(group):
    group.choices.clear()
    for other in group.seats:
        other.vote = None


@router.post("/guest")
async def guest(body: GuestAction):
    cleanup()
    found = find_seat(body.token)
    if not found:
        raise HTTPException(404, "Davet bağlantısı geçersiz veya süresi dolmuş.")
    group, seat = found
    if body.action == "locate":
        if group.choices:
            raise HTTPException(409, "Oylama sırasında başlangıç noktası değiştirilemez.")
        if not body.location:
            raise HTTPException(422, "Başlangıç noktası gerekli.")
        seat.location = body.location
        if group.room:
            seat.name = clean_name(body.name) or seat.name
            seat.travel_mode = body.travel_mode
            store_members(group)
    elif body.action == "vote":
        if not seat.location or body.candidate_id not in group.choices:
            raise HTTPException(409, "Bu oylama seçeneği kullanılamıyor.")
        seat.vote = body.candidate_id
    elif body.action == "withdraw":
        seat.location = None
        seat.vote = None
        if group.choices:
            reset_ballot(group)
    elif body.action == "leave":
        if not group.room:
            raise HTTPException(409, "Bu davetten ayrılınamaz; paylaşımı geri çekebilirsiniz.")
        if seat.location and group.choices:
            reset_ballot(group)
        group.seats.remove(seat)
        store_members(group)
        return {"left": True}
    return view(group, seat)
