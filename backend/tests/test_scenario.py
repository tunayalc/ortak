import asyncio
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.db import get_conn, init_db
from app.schemas import ParticipantLocationInput, ScenarioCreate, SyntheticUser
from app.services.scenario import create_scenario


def test_custom_users_require_synthetic_fixture_flag(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'scenario.db'}")
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    get_settings.cache_clear()
    init_db()

    payload = ScenarioCreate(
        users=[
            SyntheticUser(id="u1", label="Test 1", lat=39.9, lng=32.8),
            SyntheticUser(id="u2", label="Test 2", lat=39.91, lng=32.81),
        ]
    )

    with pytest.raises(ValueError, match="synthetic_fixture=true"):
        asyncio.run(create_scenario(payload))


def test_custom_users_are_allowed_as_explicit_synthetic_fixture(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'scenario_fixture.db'}")
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    get_settings.cache_clear()
    init_db()

    payload = ScenarioCreate(
        synthetic_fixture=True,
        users=[
            SyntheticUser(id="u1", label="Test 1", lat=39.9, lng=32.8),
            SyntheticUser(id="u2", label="Test 2", lat=39.91, lng=32.81),
        ],
    )

    scenario = asyncio.run(create_scenario(payload))

    assert scenario.group_size == 2
    assert [user.id for user in scenario.users] == ["u1", "u2"]


def test_link_mode_scenario_is_session_only_and_not_persisted(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'scenario_link.db'}")
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    get_settings.cache_clear()
    init_db()

    payload = ScenarioCreate(
        input_mode="link",
        session_only=True,
        participant_locations=[
            ParticipantLocationInput(label="A", value="39.90,32.80", delta_weight=1.4),
            ParticipantLocationInput(label="B", value="39.91,32.81", delta_weight=0.8),
        ],
    )

    scenario = asyncio.run(create_scenario(payload))

    assert scenario.session_only is True
    assert scenario.input_mode == "link"
    assert scenario.users[0].delta_weight == 1.4
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM scenarios WHERE id = ?", (scenario.id,)).fetchone()
    assert row is None


def test_link_mode_requires_session_only():
    payload = ScenarioCreate(
        input_mode="link",
        session_only=False,
        participant_locations=[
            ParticipantLocationInput(label="A", value="39.90,32.80"),
            ParticipantLocationInput(label="B", value="39.91,32.81"),
        ],
    )

    with pytest.raises(ValueError, match="session_only=true"):
        asyncio.run(create_scenario(payload))
