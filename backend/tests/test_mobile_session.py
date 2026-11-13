import pytest
from itsdangerous import TimestampSigner

from app.config import get_settings
from app.services import google_usage
from app.services.mobile_session import read_mobile_token
from test_public_release import client, headers, production, scenario_body


def token(browser):
    response = browser.post("/mobile/session")
    assert response.status_code == 200
    assert "set-cookie" not in response.headers
    assert "no-store" in response.headers["cache-control"]
    assert response.json()["expires_in"] == 7200
    return response.json()["access_token"]


def test_mobile_native_flow_without_browser_origin_or_cookies(production):
    with client(production) as native:
        auth = {"Authorization": f"Bearer {token(native)}"}
        config = native.get("/runtime-config", headers=auth)
        assert config.status_code == 200
        assert config.json()["csrf_token"] == ""
        assert "set-cookie" not in config.headers
        response = native.post("/scenarios", headers=auth, json=scenario_body())
        assert response.status_code == 200
        sid = response.json()["id"]
        assert native.get(f"/scenarios/{sid}", headers=auth).status_code == 200
        assert native.delete(f"/scenarios/{sid}", headers=auth).status_code == 204
    assert google_usage.usage_status()["used_today"] == 0


def test_native_and_web_and_other_native_sessions_are_isolated(production):
    with client(production) as owner, client(production) as other, client(production) as web:
        auth = {"Authorization": f"Bearer {token(owner)}"}
        other_auth = {"Authorization": f"Bearer {token(other)}"}
        sid = owner.post("/scenarios", json=scenario_body(), headers=auth).json()["id"]
        assert other.get(f"/scenarios/{sid}", headers=other_auth).status_code == 404
        assert other.delete(f"/scenarios/{sid}", headers=other_auth).status_code == 404
        assert web.get(f"/scenarios/{sid}").status_code == 404
        web_auth = headers(web)
        assert web.post("/scenarios", headers=web_auth, json=scenario_body()).status_code == 200
        assert web.post("/scenarios", json=scenario_body()).status_code == 403
        assert web.get("/runtime-config", headers=auth).status_code == 400


@pytest.mark.parametrize("authorization", ["", "Basic abc", "Bearer broken", "Bearer " + "x" * 1025])
def test_invalid_auth_never_falls_back_to_browser_session(production, authorization):
    with client(production) as native:
        response = native.get("/runtime-config", headers={"Authorization": authorization})
        assert response.status_code == 401
        assert "set-cookie" not in response.headers


def test_expiration_and_tampering(production, monkeypatch):
    with client(production) as native:
        monkeypatch.setattr(TimestampSigner, "get_timestamp", lambda _: 10000)
        value = token(native)
        assert read_mobile_token(get_settings(), value).startswith("mobile:")
        monkeypatch.setattr(TimestampSigner, "get_timestamp", lambda _: 17201)
        assert native.get("/runtime-config", headers={"Authorization": f"Bearer {value}"}).status_code == 401
        with pytest.raises(ValueError):
            read_mobile_token(get_settings(), value[:-8] + "tampered")


def test_browser_cannot_use_mobile_to_bypass_origin_check(production):
    with client(production) as native:
        value = token(native)
        assert native.post("/mobile/session", headers={"Origin": "https://evil.test"}).status_code == 403
        assert native.post("/scenarios", json=scenario_body(), headers={
            "Origin": "https://evil.test", "Authorization": f"Bearer {value}",
        }).status_code == 403


def test_bootstrap_rate_limit_cannot_be_evaded_with_new_sessions(production):
    with client(production) as native:
        for _ in range(6):
            token(native)
        assert native.post("/mobile/session").status_code == 429
    assert google_usage.usage_status()["used_today"] == 0


def test_feedback_minimizes_data_and_expires(production, monkeypatch):
    from app.db import get_conn
    from app.services import mobile_feedback
    clock = [1000000]
    monkeypatch.setattr(mobile_feedback.time, "time", lambda: clock[0])
    with client(production) as native:
        auth = {"Authorization": f"Bearer {token(native)}"}
        body = {"reason": "incorrect_preferences", "criterion_weights": {"rating": 20, "cost": 60, "proximity": 20}}
        response = native.post("/mobile/feedback", json=body, headers=auth)
        assert response.status_code == 201
        invalid = native.post("/mobile/feedback", json={**body, "text": "PRIVATE-TEXT"}, headers=auth)
        assert invalid.status_code == 422 and "PRIVATE-TEXT" not in invalid.text
        with get_conn() as conn:
            rows = [dict(row) for row in conn.execute("SELECT * FROM mobile_feedback")]
            assert len(rows) == 1
            assert set(rows[0]) == {"id", "created_at", "reason", "rating", "cost", "proximity"}
        clock[0] += mobile_feedback.RETENTION_SECONDS + 1
        mobile_feedback.cleanup_feedback()
        with get_conn() as conn:
            assert conn.execute("SELECT COUNT(*) FROM mobile_feedback").fetchone()[0] == 0
