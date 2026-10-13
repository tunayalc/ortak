from __future__ import annotations

from contextvars import ContextVar


current_session: ContextVar[str | None] = ContextVar("ortak_session", default=None)
