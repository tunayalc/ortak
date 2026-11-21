"""Single-worker, ephemeral invitations. Guest capabilities travel in POST bodies, never paths."""
from dataclasses import dataclass, field
from secrets import token_urlsafe
from time import monotonic
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ..config import get_settings
from ..schemas import Coordinate
from . import session_store

router = APIRouter(prefix="/groups")


@dataclass
class Seat:
    token: str = field(default_factory=lambda: token_urlsafe(32))
    location: Coordinate | None = None
    vote: str | None = None


@dataclass
class Group:
    seats: list[Seat]
    expires: float
    choices: dict = field(default_factory=dict)
    scenario: str = ""


groups: dict[str, Group] = {}


def cleanup():
    for key in [k for k, v in groups.items() if v.expires <= monotonic()]:
        del groups[key]


def owner(request):
    if "id" not in request.session:
        request.session["id"] = token_urlsafe(24)
    return request.session["id"]


def require_group(request):
    cleanup()
    group = groups.get(owner(request))
    if not group:
        raise HTTPException(404, "Davet sona erdi veya bu oturuma ait değil.")
    return group


def ballot(group):
    return [dict(choice, votes=sum(s.vote == key for s in group.seats)) for key, choice in group.choices.items()]


def summary(group):
    return {"seats": [{"token": s.token, "ready": s.location is not None} for s in group.seats],
            "choices": ballot(group), "expires_in": max(0, int(group.expires - monotonic()))}


class NewGroup(BaseModel):
    size: int = Field(ge=2, le=12)


@router.post("")
async def create(request: Request, body: NewGroup):
    cleanup()
    key = owner(request)
    if key in groups:
        raise HTTPException(409, "Önce mevcut daveti kapatın.")
    if body.size > get_settings().public_max_participants or len(groups) >= 100:
        raise HTTPException(429, "Grup kapasitesi aşıldı.")
    group = groups[key] = Group([Seat() for _ in range(body.size)], monotonic() + 7140)
    return summary(group)


@router.get("/mine")
async def mine(request: Request):
    cleanup()
    group = groups.get(owner(request))
    return summary(group) if group else None


@router.delete("/mine", status_code=204)
async def close(request: Request):
    groups.pop(owner(request), None)


@router.post("/locations")
async def locations(request: Request):
    group = require_group(request)
    if not all(s.location for s in group.seats):
        raise HTTPException(409, "Tüm katılımcılar başlangıç noktalarını eklemeli.")
    return [s.location for s in group.seats]


class OpenBallot(BaseModel):
    scenario_id: str = Field(min_length=1, max_length=100)
    candidates: list[str] = Field(min_length=2, max_length=3)


@router.post("/ballot")
async def open_ballot(request: Request, body: OpenBallot):
    group = require_group(request)
    scenario = session_store.get_scenario(body.scenario_id)
    if not scenario or len(scenario.users) != len(group.seats) or not all(
        s.location and abs(s.location.lat - u.lat) < 0.000001 and abs(s.location.lng - u.lng) < 0.000001
        for s, u in zip(group.seats, scenario.users)
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
    for key in [k for k, g in groups.items() if g.scenario == scenario_id]:
        del groups[key]


class GuestAction(BaseModel):
    token: str = Field(min_length=43, max_length=43, pattern=r"^[A-Za-z0-9_-]+$")
    action: Literal["view", "locate", "vote", "withdraw"] = "view"
    location: Coordinate | None = None
    consent: Literal[True] | None = None
    candidate_id: str | None = Field(default=None, max_length=100)


@router.post("/guest")
async def guest(body: GuestAction):
    cleanup()
    for group in groups.values():
        for index, seat in enumerate(group.seats):
            if seat.token != body.token:
                continue
            if body.action == "locate":
                if group.choices:
                    raise HTTPException(409, "Oylama sırasında başlangıç noktası değiştirilemez.")
                if not body.location or not body.consent:
                    raise HTTPException(422, "Koordinat ve açık paylaşım onayı gerekli.")
                seat.location = body.location
            elif body.action == "vote":
                if not seat.location or body.candidate_id not in group.choices:
                    raise HTTPException(409, "Bu oylama seçeneği kullanılamıyor.")
                seat.vote = body.candidate_id
            elif body.action == "withdraw":
                seat.location = None
                seat.vote = None
                if group.choices:
                    group.choices.clear()
                    for other in group.seats:
                        other.vote = None
            return {"seat": index + 1, "ready": seat.location is not None, "choices": ballot(group), "vote": seat.vote}
    raise HTTPException(404, "Davet bağlantısı geçersiz veya süresi dolmuş.")
