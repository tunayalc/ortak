from __future__ import annotations

import hashlib
import hmac
import secrets
import time

from starlette.requests import Request
from starlette.responses import JSONResponse

from ..config import Settings
from ..db import get_conn
from .request_context import current_session


MAX_BODY_BYTES = 65536
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def reserve_rate_limits(settings: Settings, session_id: str, ip: str, path: str) -> bool:
    now = int(time.time())
    day = now // 86400
    ip_hash = hmac.new(settings.session_secret.encode(), f"{day}:{ip}".encode(), hashlib.sha256).hexdigest()
    limits = [("requests", 60, 60)]
    if path in {"/locations/parse", "/scenarios", "/candidates/search", "/routes/matrix"}:
        limits.append(("paid", 60, 6))
    if path == "/preferences/interpret":
        limits.extend([("llm", 60, 3), ("llm_day", 86400, 20)])
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM request_limits WHERE expires_at <= ?", (now,))
        for subject in (f"session:{session_id}", f"ip:{ip_hash}"):
            for name, window, maximum in limits:
                bucket = now // window
                row = conn.execute("SELECT count FROM request_limits WHERE subject = ? AND name = ? AND bucket = ?", (subject, name, bucket)).fetchone()
                if row is not None and row["count"] >= maximum:
                    return False
        for subject in (f"session:{session_id}", f"ip:{ip_hash}"):
            for name, window, _ in limits:
                bucket = now // window
                conn.execute(
                    "INSERT INTO request_limits (subject, name, bucket, count, expires_at) VALUES (?, ?, ?, 1, ?) "
                    "ON CONFLICT(subject, name, bucket) DO UPDATE SET count = count + 1",
                    (subject, name, bucket, (bucket + 1) * window),
                )
    return True


class PublicSafetyMiddleware:
    def __init__(self, app, settings: Settings):
        self.app = app
        self.settings = settings

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not self.settings.production:
            await self.app(scope, receive, send)
            return
        request = Request(scope)

        async def reject(status: int, message: str):
            await JSONResponse({"detail": message}, status_code=status, headers={"Cache-Control": "no-store"})(scope, receive, send)

        if "id" not in request.session:
            request.session.update(id=secrets.token_urlsafe(24), csrf=secrets.token_urlsafe(24))
        if request.method in MUTATING_METHODS:
            if request.headers.get("origin") != self.settings.public_base_url:
                await reject(403, "İstek kaynağı doğrulanamadı.")
                return
            expected = request.session.get("csrf", "")
            if not expected or not hmac.compare_digest(request.headers.get("x-ortak-csrf", ""), expected):
                await reject(403, "Oturum doğrulaması gerekli. Sayfayı yenileyin.")
                return
        session_id = request.session["id"]
        ip = request.client.host if request.client else "unknown"
        if not reserve_rate_limits(self.settings, session_id, ip, request.url.path):
            await reject(429, "İstek sınırına ulaşıldı. Bir süre sonra yeniden deneyin.")
            return

        replay_receive = receive
        if request.method in MUTATING_METHODS:
            chunks = []
            total = 0
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                part = message.get("body", b"")
                total += len(part)
                if total > MAX_BODY_BYTES:
                    await reject(413, "İstek boyutu izin verilen sınırı aşıyor.")
                    return
                chunks.append(part)
                if not message.get("more_body", False):
                    break
            body = b"".join(chunks)
            delivered = False

            async def replay_receive():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {"type": "http.request", "body": body, "more_body": False}
                return await receive()

        async def safe_send(message):
            if message["type"] == "http.response.start":
                message["headers"] = list(message.get("headers", [])) + [
                    (b"cache-control", b"no-store"),
                    (b"x-content-type-options", b"nosniff"),
                    (b"referrer-policy", b"no-referrer"),
                ]
            await send(message)

        token = current_session.set(session_id)
        try:
            await self.app(scope, replay_receive, safe_send)
        finally:
            current_session.reset(token)
