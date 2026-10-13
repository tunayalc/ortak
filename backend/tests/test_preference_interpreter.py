import asyncio
import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.schemas import PreferenceInterpretRequest
from app.config import Settings
from app.services import preference_interpreter as interpreter


def configure(monkeypatch, provider="openai", **kwargs):
    settings = Settings(_env_file=None, LLM_PROVIDER=provider, OPENAI_API_KEY=kwargs.pop("key", "test-key"), **kwargs)
    monkeypatch.setattr(interpreter, "get_settings", lambda: settings)
    return settings


def request_payload(text="Puan önemli, Ayşe'ye iki kat yakın olsun."):
    return PreferenceInterpretRequest(
        text=text,
        participants=[
            {"id": "user-1", "label": "Ayşe", "delta_weight": 1},
            {"id": "user-2", "label": "Bora", "delta_weight": 1},
        ],
    )


def model_response(**overrides):
    proposal = {
        "criterion_weights": {"rating": 60, "cost": 15, "proximity": 25},
        "participant_proximity_weights": {"user-1": 2, "user-2": 1},
        "min_rating": None,
        "max_duration_minutes": None,
        "explanation": "Mekân puanı ve Ayşe'ye yakınlık öne çıkarıldı.",
        "warnings": [],
    }
    proposal.update(overrides)
    return {"status": "completed", "output": [{
        "type": "message", "content": [{"type": "output_text", "text": json.dumps(proposal)}]
    }]}


def test_interpreter_sends_only_anonymous_preference_and_requires_confirmation(monkeypatch):
    configure(monkeypatch)
    sent = {}

    def handler(request):
        sent.update(json.loads(request.content))
        return httpx.Response(200, json=model_response())

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await interpreter.interpret_preferences(request_payload(), client)

    suggestion = asyncio.run(run())
    assert suggestion.criterion_weights.rating == 60
    assert suggestion.source == "openai"
    assert suggestion.model == "gpt-4o-mini"
    assert suggestion.participant_proximity_weights == {"user-1": 2, "user-2": 1}
    assert sent["store"] is False
    assert sent["text"]["format"]["strict"] is True
    assert "Ayşe" not in json.dumps(sent, ensure_ascii=False)
    assert "Kişi 1" in json.dumps(sent, ensure_ascii=False)
    assert "lat" not in json.dumps(sent, ensure_ascii=False)


def test_interpreter_rejects_location_in_prompt_before_external_call(monkeypatch):
    configure(monkeypatch)
    with pytest.raises(interpreter.PreferenceServiceError) as error:
        asyncio.run(interpreter.interpret_preferences(request_payload("39.92,32.85 yakın olsun")))
    assert error.value.status_code == 400


def test_interpreter_rejects_unknown_person_weight(monkeypatch):
    configure(monkeypatch)

    def handler(_request):
        return httpx.Response(200, json=model_response(
            participant_proximity_weights={"user-1": 2, "user-3": 1}
        ))

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await interpreter.interpret_preferences(request_payload(), client)

    with pytest.raises(interpreter.PreferenceServiceError, match="kişi ağırlıklarını"):
        asyncio.run(run())


def test_interpreter_is_unavailable_without_api_key(monkeypatch):
    configure(monkeypatch, key=None)
    with pytest.raises(interpreter.PreferenceServiceError) as error:
        asyncio.run(interpreter.interpret_preferences(request_payload()))
    assert error.value.status_code == 503


def test_interpreter_drops_unrequested_hard_filters(monkeypatch):
    configure(monkeypatch)

    def handler(_request):
        return httpx.Response(200, json=model_response(min_rating=4.5, max_duration_minutes=20))

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await interpreter.interpret_preferences(request_payload(), client)

    suggestion = asyncio.run(run())
    assert suggestion.min_rating is None
    assert suggestion.max_duration_minutes is None
    assert len(suggestion.warnings) == 2


def ollama_response(edits=None):
    proposal = {"edits": edits if edits is not None else [
        {"target": "rating", "person_id": None, "value": 60, "evidence": "Puan önemli"},
        {"target": "proximity", "person_id": "user-1", "value": 2, "evidence": "Kişi 1"},
    ]}
    return {"done": True, "done_reason": "stop", "model": "untrusted-model-name", "message": {"content": json.dumps(proposal)}}


def call_with(handler, payload=None):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await interpreter.interpret_preferences(payload or request_payload(), client)
    return asyncio.run(run())


def test_ollama_is_default_without_openai_key():
    settings = Settings(_env_file=None, OPENAI_API_KEY=None)
    assert settings.llm_provider == "ollama"
    assert settings.ollama_model == "llama3:8b"
    assert settings.has_llm_config


def test_ollama_schema_privacy_and_authoritative_metadata(monkeypatch):
    configure(monkeypatch, "ollama", key=None)
    calls = []

    def handler(request):
        calls.append(str(request.url))
        assert str(request.url) == "http://127.0.0.1:11434/api/chat"
        body = json.loads(request.content)
        assert body["stream"] is False
        assert body["options"]["temperature"] == 0
        assert body["format"]["additionalProperties"] is False
        assert body["format"]["$defs"]["PreferenceEdit"]["properties"]["person_id"]["enum"] == ["user-1", "user-2", None]
        assert "Ayşe" not in json.dumps(body, ensure_ascii=False)
        assert "Bora" not in json.dumps(body, ensure_ascii=False)
        assert "authorization" not in request.headers
        assert request.extensions["timeout"]["connect"] <= 5
        return httpx.Response(200, json=ollama_response())

    result = call_with(handler)
    assert result.source == "ollama"
    assert result.model == "llama3:8b"
    assert len(calls) == 1


@pytest.mark.parametrize("body", [
    {"done": False},
    {"done": True, "done_reason": "length", "message": {"content": "{}"}},
    {"done": True, "message": {"content": "not json"}},
    {"done": True, "message": {"content": "[]"}},
    {"done": True, "message": {}},
])
def test_ollama_rejects_invalid_or_incomplete_responses(monkeypatch, body):
    configure(monkeypatch, "ollama")
    with pytest.raises(interpreter.PreferenceServiceError) as error:
        call_with(lambda _: httpx.Response(200, json=body))
    assert error.value.status_code == 502


@pytest.mark.parametrize("overrides", [
    {"criterion_weights": {"rating": 0, "cost": 0, "proximity": 0}},
    {"criterion_weights": {"rating": 101, "cost": 0, "proximity": 0}},
    {"criterion_weights": {"rating": -1, "cost": 1, "proximity": 1}},
    {"criterion_weights": {"rating": float("inf"), "cost": 1, "proximity": 1}},
    {"participant_proximity_weights": {"user-1": 3, "user-2": 1}},
    {"participant_proximity_weights": {"user-1": 1, "user-3": 1}},
    {"max_duration_minutes": float("inf")},
])
def test_ollama_rejects_invalid_weights_and_limits(monkeypatch, overrides):
    configure(monkeypatch, "ollama")
    with pytest.raises(interpreter.PreferenceServiceError):
        raw = json.loads(model_response(**overrides)["output"][0]["content"][0]["text"])
        interpreter._validate_suggestion(raw, request_payload())


@pytest.mark.parametrize("failure,code", [("offline", 503), ("timeout", 504), ("missing", 503)])
def test_ollama_failure_never_falls_back_to_cloud(monkeypatch, failure, code):
    configure(monkeypatch, "ollama", key="available-but-not-selected")
    calls = []

    def handler(request):
        calls.append(str(request.url))
        if failure == "offline":
            raise httpx.ConnectError("offline", request=request)
        if failure == "timeout":
            raise httpx.ReadTimeout("slow", request=request)
        return httpx.Response(404)

    with pytest.raises(interpreter.PreferenceServiceError) as error:
        call_with(handler)
    assert error.value.status_code == code
    assert calls == ["http://127.0.0.1:11434/api/chat"]


def test_disabled_provider_makes_no_requests(monkeypatch):
    configure(monkeypatch, "disabled")
    with pytest.raises(interpreter.PreferenceServiceError) as error:
        call_with(lambda _: pytest.fail("Provider disabled but requested"))
    assert error.value.status_code == 503


def test_unknown_self_reference_preserves_people(monkeypatch):
    configure(monkeypatch, "ollama")
    raw = json.loads(model_response()["output"][0]["content"][0]["text"])
    result = interpreter._validate_suggestion(raw, request_payload("Bana yakın olsun."))
    assert result.participant_proximity_weights == {"user-1": 1, "user-2": 1}
    assert any("kişi belirtilmedi" in warning for warning in result.warnings)


def test_money_warning_and_no_unrequested_filter(monkeypatch):
    configure(monkeypatch, "ollama")
    raw = json.loads(model_response(min_rating=4)["output"][0]["content"][0]["text"])
    result = interpreter._validate_suggestion(raw, request_payload("Bütçem 300 TL olsun."))
    assert result.min_rating is None
    assert any("bütçe sınırı uygulanamaz" in warning for warning in result.warnings)


@pytest.mark.parametrize("case,expected", [("present", "ready"), ("absent", "model_missing"), ("offline", "unreachable"), ("slow", "timeout"), ("malformed", "unreachable")])
def test_ollama_readiness(monkeypatch, case, expected):
    configure(monkeypatch, "ollama")

    def handler(request):
        assert request.url.path == "/api/tags"
        if case == "offline":
            raise httpx.ConnectError("offline")
        if case == "slow":
            raise httpx.ReadTimeout("slow")
        return httpx.Response(200, json={"models": [{"name": "llama3:8b"}] if case == "present" else None if case == "malformed" else []})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await interpreter.llm_status(client)

    status = asyncio.run(run())
    assert status["ai_status"] == expected
    assert status["ai_ready"] == (case == "present")
    assert status["ai_configured"]


def test_openai_configuration_does_not_claim_live_readiness(monkeypatch):
    configure(monkeypatch)
    status = asyncio.run(interpreter.llm_status())
    assert status["ai_status"] == "configured"
    assert status["ai_ready"] is False


@pytest.mark.parametrize("edit", [
    {"target": "proximity", "person_id": "user-3", "value": 2, "evidence": "Kişi 1"},
    {"target": "proximity", "person_id": "user-2", "value": 2, "evidence": "Kişi 1"},
    {"target": "proximity", "person_id": "user-1", "value": 200, "evidence": "Kişi 1"},
    {"target": "rating", "person_id": None, "value": 80, "evidence": "not in user text"},
    {"target": "rating", "person_id": None, "value": float("inf"), "evidence": "Puan önemli"},
    {"target": "other", "person_id": None, "value": 80, "evidence": "Puan önemli"},
])
def test_invalid_or_ungrounded_edit_is_rejected(monkeypatch, edit):
    configure(monkeypatch, "ollama")
    with pytest.raises(interpreter.PreferenceServiceError) as error:
        call_with(lambda _: httpx.Response(200, json=ollama_response([edit])))
    assert error.value.status_code == 502


def test_sparse_edits_preserve_every_unspecified_value(monkeypatch):
    configure(monkeypatch, "ollama")
    payload = request_payload("Fiyat önemli olsun.")
    payload.participants[0].delta_weight = 1.5
    payload.min_rating = 4.5
    payload.max_duration_minutes = 30
    edits = [{"target": "cost", "person_id": None, "value": 70, "evidence": "Fiyat önemli"}]
    result = call_with(lambda _: httpx.Response(200, json=ollama_response(edits)), payload)
    assert result.criterion_weights.model_dump() == {"rating": 34, "cost": 70, "proximity": 33}
    assert result.participant_proximity_weights == {"user-1": 1.5, "user-2": 1}
    assert result.min_rating == 4.5
    assert result.max_duration_minutes == 30


def test_balanced_people_and_derived_explanation(monkeypatch):
    configure(monkeypatch, "ollama")
    payload = request_payload("Kişiler dengeli olsun.")
    payload.participants[0].delta_weight = 2
    edits = [{"target": "equal_people", "person_id": None, "value": 1, "evidence": "Kişiler dengeli"}]
    result = call_with(lambda _: httpx.Response(200, json=ollama_response(edits)), payload)
    assert result.participant_proximity_weights == {"user-1": 1, "user-2": 1}
    assert "1 kişinin yakınlık ağırlığı değişti" in result.explanation


def test_conflicting_person_edits_are_rejected(monkeypatch):
    configure(monkeypatch, "ollama")
    edit = {"target": "rating", "person_id": None, "value": 70, "evidence": "Puan önemli"}
    with pytest.raises(interpreter.PreferenceServiceError):
        call_with(lambda _: httpx.Response(200, json=ollama_response([edit, edit])))


def test_grounded_criterion_label_cross_check(monkeypatch):
    configure(monkeypatch, "ollama")
    edits = [{"target": "rating", "person_id": None, "value": 70, "evidence": "Fiyat uygunluğu"}]
    result = call_with(lambda _: httpx.Response(200, json=ollama_response(edits)), request_payload("Fiyat uygunluğu önemli."))
    assert result.criterion_weights.model_dump() == {"rating": 34, "cost": 70, "proximity": 33}


def test_ambiguous_person_edit_asks_instead_of_guessing(monkeypatch):
    configure(monkeypatch, "ollama")
    edits = [{"target": "proximity", "person_id": "user-1", "value": 2, "evidence": "Bana yakın"}]
    result = call_with(lambda _: httpx.Response(200, json=ollama_response(edits)), request_payload("Bana yakın olsun."))
    assert result.participant_proximity_weights == {"user-1": 1, "user-2": 1}
    assert result.criterion_weights.proximity == 33
    assert result.warnings


def test_turkish_inflected_duration_is_preserved(monkeypatch):
    configure(monkeypatch, "ollama")
    edits = [{"target": "max_duration_minutes", "person_id": None, "value": 20, "evidence": "20 dakikayı aşmasın"}]
    result = call_with(lambda _: httpx.Response(200, json=ollama_response(edits)), request_payload("Yolculuk 20 dakikayı aşmasın."))
    assert result.max_duration_minutes == 20


def test_local_model_evidence_with_minor_language_error(monkeypatch):
    configure(monkeypatch, "ollama")
    edits = [{"target": "cost", "person_id": None, "value": 70, "evidence": "Fiyat uygunluğu daha importante olsun"}]
    result = call_with(lambda _: httpx.Response(200, json=ollama_response(edits)), request_payload("Fiyat uygunluğu daha önemli olsun."))
    assert result.criterion_weights.cost == 70


def test_fuzzy_evidence_cannot_invent_another_criterion(monkeypatch):
    configure(monkeypatch, "ollama")
    edits = [{"target": "cost", "person_id": None, "value": 70, "evidence": "Fiyat önemli olsun"}]
    with pytest.raises(interpreter.PreferenceServiceError):
        call_with(lambda _: httpx.Response(200, json=ollama_response(edits)), request_payload("Puan önemli olsun."))
