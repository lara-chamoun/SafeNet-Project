"""Integration coverage for the web adapter; no real OpenAI requests."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from safenet import agents
from safenet.graph import build_graph
from safenet.models import CyberSafetyState, SituationAnalysis
from safenet.web import create_app

HEADERS = {"X-SafeNet-Client": "web"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")

    calls = []

    class FakeLLM:
        def __init__(self, **kwargs):
            assert kwargs == {"model": "gpt-4o", "temperature": 0}

        def with_structured_output(self, schema):
            assert schema is SituationAnalysis
            return self

        def invoke(self, prompt):
            calls.append(prompt)
            return SituationAnalysis(
                situation_type="phishing",
                contains_link=True,
                clicked_link=True,
                shared_password="password" in prompt.lower(),
                shared_otp="verification code" in prompt.lower(),
            )

    monkeypatch.setattr(agents, "ChatOpenAI", FakeLLM)
    with TestClient(create_app(tmp_path / "history.sqlite3"), headers=HEADERS) as test_client:
        yield test_client


def create(client, **kwargs):
    response = client.post("/api/conversations", json={"title": "Bank link", **kwargs})
    assert response.status_code == 201
    return response.json()["id"]


def send(client, conversation_id, text, **kwargs):
    return client.post(f"/api/conversations/{conversation_id}/messages", json={
        "message": text, "request_id": str(uuid4()), **kwargs,
    })


def test_frontend_assets_and_private_config(client):
    assert 'id="welcome-title"' in client.get("/").text
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/styles.css").status_code == 200
    config = client.get("/api/config").json()
    assert config["live_available"] is True
    assert config["model"] == "gpt-4o"
    assert config["analysis_mode"] == "live"
    assert "OPENAI_API_KEY" not in config
    assert client.get("/.env").status_code == 404
    assert "frame-ancestors 'none'" in client.get("/").headers["Content-Security-Policy"]


def test_same_thread_updates_one_incident(client):
    conversation_id = create(client)

    first = send(client, conversation_id, "I received a suspicious bank email.").json()
    second = send(client, conversation_id, "I clicked the link but did not enter my password.").json()

    assert len(first["turns"]) == 1
    assert len(second["turns"]) == 2
    assert second["turns"][-1]["mode"] == "live"

    checkpoint = client.app.state.graph.get_state(
        {"configurable": {"thread_id": conversation_id}}
    )
    assert checkpoint.values["conversation_history"] == [
        "I received a suspicious bank email.",
        "I clicked the link but did not enter my password.",
    ]
    assert "I received a suspicious bank email." in checkpoint.values["incident_context"]
    assert "I clicked the link" in checkpoint.values["incident_context"]


def test_followup_uses_human_context_and_does_not_duplicate_agents(client):
    conversation_id = create(client)
    first = send(client, conversation_id, "I clicked a suspicious bank link.").json()
    assert first["turns"][0]["assessment"]["shared_password"] is False
    second = send(client, conversation_id, "I also entered my password and verification code.").json()
    assessment = second["turns"][1]["assessment"]
    assert assessment["clicked_link"] is True
    assert assessment["shared_password"] is True
    assert assessment["shared_otp"] is True
    assert assessment["downloaded_file"] is False  # Advice text mentions downloading; it isn't input.
    assert len(assessment["agents_completed"]) == 5
    assert len(second["turns"]) == 2
    other = create(client)
    isolated = send(client, other, "I received a message.").json()["turns"][0]["assessment"]
    assert isolated["clicked_link"] is False
    assert isolated["shared_password"] is False


def test_history_survives_server_restart_and_can_be_renamed_deleted(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    path = tmp_path / "persistent.sqlite3"
    with TestClient(create_app(path), headers=HEADERS) as first:
        conversation_id = create(first)
        original = send(first, conversation_id, "I clicked a link.").json()
        renamed = first.patch(f"/api/conversations/{conversation_id}", json={"title": "Bank incident"})
        assert renamed.status_code == 200
    with TestClient(create_app(path), headers=HEADERS) as second:
        restored = second.get(f"/api/conversations/{conversation_id}").json()
        assert restored["title"] == "Bank incident"
        assert restored["turns"] == original["turns"]
        assert second.get("/api/conversations").json()[0]["id"] == conversation_id
        followup = send(second, conversation_id, "I entered my password.")
        assert followup.json()["turns"][-1]["assessment"]["clicked_link"] is True
        assert second.delete(f"/api/conversations/{conversation_id}").status_code == 200
        assert second.get(f"/api/conversations/{conversation_id}").status_code == 404
        assert second.get("/api/conversations").json() == []
        assert second.app.state.graph.get_state({"configurable": {"thread_id": conversation_id}}).values == {}


def test_retried_message_is_not_run_or_saved_twice(client):
    conversation_id = create(client)
    request_id = str(uuid4())
    first = send(client, conversation_id, "I clicked a link.", request_id=request_id)
    second = send(client, conversation_id, "I clicked a link.", request_id=request_id)
    assert first.json() == second.json()
    assert len(second.json()["turns"]) == 1
    assert send(client, conversation_id, "Different message", request_id=request_id).status_code == 409


def test_openai_key_is_required(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")
    with TestClient(create_app(tmp_path / "history.sqlite3"), headers=HEADERS) as test_client:
        conversation_id = create(test_client)
        response = send(test_client, conversation_id, "I received an email.")
        assert response.status_code == 503
        assert "OpenAI API key" in response.json()["detail"]
        assert test_client.get(f"/api/conversations/{conversation_id}").json()["turns"] == []


def test_live_reuses_existing_single_structured_llm_call(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")
    calls = []

    class FakeLLM:
        def __init__(self, **kwargs):
            assert kwargs == {"model": "gpt-4o", "temperature": 0}

        def with_structured_output(self, schema):
            assert schema is SituationAnalysis
            return self

        def invoke(self, prompt):
            calls.append(prompt)
            return SituationAnalysis(situation_type="phishing", contains_link=True, clicked_link=True)

    monkeypatch.setattr(agents, "ChatOpenAI", FakeLLM)
    conversation_id = create(client)
    send(client, conversation_id, "I clicked a link.")
    response = send(client, conversation_id, "The sender claimed to be my bank.")
    assert response.status_code == 200
    assert response.json()["turns"][-1]["mode"] == "live"
    assert len(calls) == 1
    assert "I clicked a link.\n\nThe sender claimed to be my bank." in calls[0]
    assert "Do not use unexpected links" not in calls[0]


@pytest.mark.parametrize("status, expected", [(401, "authenticate"), (429, "credit limit"), (500, "unavailable")])
def test_provider_errors_are_understandable_and_redacted(client, monkeypatch, status, expected):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")

    class ProviderError(Exception):
        status_code = status

    def failing_llm(**kwargs):
        raise ProviderError("SECRET-should-not-be-shown")

    monkeypatch.setattr(agents, "ChatOpenAI", failing_llm)
    conversation_id = create(client)
    response = send(client, conversation_id, "Something happened")
    assert response.status_code == 502
    assert expected in response.json()["detail"]
    assert "SECRET" not in response.text
    assert client.get(f"/api/conversations/{conversation_id}").json()["turns"] == []


def test_invalid_input_and_long_history_are_rejected(client):
    conversation_id = create(client)
    for invalid in [" ", "x" * 6001]:
        assert send(client, conversation_id, invalid).status_code == 422
    assert client.patch(f"/api/conversations/{conversation_id}", json={"title": " "}).status_code == 422
    assert client.get("/api/conversations/not-a-uuid").status_code == 422
    for _ in range(5):
        assert send(client, conversation_id, "x" * 6000).status_code == 200
    response = send(client, conversation_id, "x" * 6000)
    assert response.status_code == 422
    assert "new chat" in response.json()["detail"]
    assert len(client.get(f"/api/conversations/{conversation_id}").json()["turns"]) == 5


def test_local_api_rejects_cross_origin_form_mutations(client):
    response = client.post("/api/conversations", json={}, headers={"X-SafeNet-Client": ""})
    assert response.status_code == 403
    assert client.get("/api/config", headers={"Host": "untrusted.example"}).status_code == 400


def test_concurrent_send_and_delete_are_rejected_while_processing(client, monkeypatch):
    conversation_id = create(client)
    started, finish = Event(), Event()
    original = client.app.state.graph.invoke

    def slow_invoke(*args, **kwargs):
        started.set()
        assert finish.wait(10)
        return original(*args, **kwargs)

    monkeypatch.setattr(client.app.state.graph, "invoke", slow_invoke)
    with ThreadPoolExecutor(max_workers=1) as executor:
        pending = executor.submit(send, client, conversation_id, "I clicked a link.")
        try:
            assert started.wait(10)
            assert send(client, conversation_id, "Another message").status_code == 409
            assert client.delete(f"/api/conversations/{conversation_id}").status_code == 409
        finally:
            finish.set()
        assert pending.result().status_code == 200
