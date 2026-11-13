from __future__ import annotations

import hashlib
import secrets

from itsdangerous import BadData, URLSafeTimedSerializer
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from ..config import Settings
from .session_store import SESSION_TTL_SECONDS


def _signer(settings: Settings) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(
        settings.session_secret or "local-development-only-not-for-production",
        salt="ortak-native-session-v1",
        signer_kwargs={"digest_method": hashlib.sha256},
    )


def issue_mobile_token(settings: Settings, session_id: str) -> str:
    return _signer(settings).dumps({"v": 1, "id": session_id})


def read_mobile_token(settings: Settings, token: str) -> str:
    if not token or len(token) > 1024:
        raise ValueError("Invalid mobile session")
    try:
        payload = _signer(settings).loads(token, max_age=SESSION_TTL_SECONDS)
    except BadData as exc:
        raise ValueError("Expired or invalid mobile session") from exc
    if not isinstance(payload, dict) or payload.get("v") != 1:
        raise ValueError("Invalid mobile session")
    session_id = payload.get("id")
    if not isinstance(session_id, str) or not session_id.startswith("mobile:") or len(session_id) != 39:
        raise ValueError("Invalid mobile session")
    return session_id


class ClientSessionMiddleware:
    """Keep native bearer sessions separate from browser cookies and CSRF."""

    def __init__(self, app, settings: Settings):
        self.app = app
        self.settings = settings
        self.browser = SessionMiddleware(
            app,
            secret_key=settings.session_secret or "local-development-only-not-for-production",
            session_cookie="ortak_session",
            max_age=SESSION_TTL_SECONDS,
            same_site="lax",
            https_only=settings.production,
        )

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request = Request(scope)
        bootstrap = request.url.path == "/mobile/session" and request.method == "POST"
        authorization = request.headers.get("authorization")
        if not bootstrap and authorization is None:
            return await self.browser(scope, receive, send)

        async def reject(status, detail):
            await JSONResponse({"detail": detail}, status_code=status,
                               headers={"Cache-Control": "no-store"})(scope, receive, send)

        # Native clients have no Origin. Browsers must still be explicitly trusted.
        origin = request.headers.get("origin")
        if origin is not None and origin not in self.settings.origins:
            return await reject(403, "İstek kaynağı doğrulanamadı.")
        if request.cookies.get("ortak_session"):
            return await reject(400, "Mobil ve web oturumları birlikte kullanılamaz.")
        if bootstrap:
            if authorization is not None:
                return await reject(400, "Yeni oturum için mevcut erişim anahtarını göndermeyin.")
            session_id = "mobile:" + secrets.token_urlsafe(24)
        else:
            try:
                if not authorization or not authorization.startswith("Bearer "):
                    raise ValueError("Invalid authorization")
                session_id = read_mobile_token(self.settings, authorization[7:])
            except ValueError:
                return await reject(401, "Mobil oturumun süresi doldu. Yeni bir buluşma oluşturun.")
        scope["session"] = {"id": session_id}
        scope["ortak.mobile"] = True

        async def private_send(message):
            if message["type"] == "http.response.start":
                message["headers"] = list(message.get("headers", [])) + [(b"cache-control", b"no-store")]
            await send(message)

        await self.app(scope, receive, private_send)
