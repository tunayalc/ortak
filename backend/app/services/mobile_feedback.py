from __future__ import annotations

import time
import uuid
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import ConfigDict

from ..db import get_conn
from ..schemas import BaseModel, CriterionWeights


router = APIRouter()
RETENTION_SECONDS = 30 * 86400


class Feedback(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    reason: Literal["incorrect_preferences", "unsafe_response", "other"]
    criterion_weights: CriterionWeights


def cleanup_feedback() -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM mobile_feedback WHERE created_at <= ?", (int(time.time()) - RETENTION_SECONDS,))


@router.post("/mobile/feedback", status_code=201)
def report_feedback(payload: Feedback, request: Request):
    if not request.scope.get("ortak.mobile"):
        raise HTTPException(403, "Mobil oturum gereklidir.")
    weights = payload.criterion_weights.model_dump()
    total = sum(weights.values())
    if not 0 < total <= 1_000_000:
        raise HTTPException(422, "Kriter ağırlıkları geçersiz.")
    identifier = str(uuid.uuid4())
    cleanup_feedback()
    # Deliberately omit text, coordinates, participant labels and session/IP identifiers.
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO mobile_feedback (id, created_at, reason, rating, cost, proximity) VALUES (?, ?, ?, ?, ?, ?)",
            (identifier, int(time.time()), payload.reason, *(weights[key] / total for key in ("rating", "cost", "proximity"))),
        )
    return {"id": identifier}
