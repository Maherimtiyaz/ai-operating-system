"""OpenAI-compatible client tests (no real network)."""

import pytest

from aiop.automation.llm import (
    DEFAULT_BASE_URL,
    OPENAI_API_KEY_ENV,
    LLMError,
    OpenAICompatibleClient,
    resolve_api_key,
)


class _FakeResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


class _FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def build_client(session, api_key="sk-test", base_url=None):
    return OpenAICompatibleClient(session=session, api_key=api_key, base_url=base_url)


# --------------------------------------------------------------- key resolution
def test_resolve_api_key_uses_configured_first(monkeypatch):
    assert resolve_api_key("configured") == "configured"


def test_resolve_api_key_falls_back_to_environment(monkeypatch):
    monkeypatch.setenv(OPENAI_API_KEY_ENV, "env-key")
    assert resolve_api_key(None) == "env-key"


def test_resolve_api_key_raises_when_missing(monkeypatch):
    monkeypatch.delenv(OPENAI_API_KEY_ENV, raising=False)
    with pytest.raises(LLMError, match="API key"):
        resolve_api_key(None)


# ---------------------------------------------------------------- completion
def test_complete_returns_assistant_message():
    session = _FakeSession(_FakeResponse(200, {"choices": [{"message": {"content": "  hello  "}}]}))
    client = build_client(session)
    assert client.complete("hi") == "hello"
    call = session.calls[0]
    assert call["url"] == f"{DEFAULT_BASE_URL}/chat/completions"
    assert call["headers"]["Authorization"] == "Bearer sk-test"
    assert call["json"]["messages"] == [{"role": "user", "content": "hi"}]
    assert call["json"]["model"] == "gpt-4o-mini"


def test_complete_passes_system_prompt_and_model():
    session = _FakeSession(_FakeResponse(200, {"choices": [{"message": {"content": "ok"}}]}))
    client = build_client(session)
    client.complete("user text", system="be brief", model="gpt-4.1-mini", max_tokens=512)
    call = session.calls[0]
    assert call["json"]["model"] == "gpt-4.1-mini"
    assert call["json"]["messages"] == [
        {"role": "system", "content": "be brief"},
        {"role": "user", "content": "user text"},
    ]
    assert call["json"]["max_tokens"] == 512


def test_complete_uses_custom_base_url():
    session = _FakeSession(_FakeResponse(200, {"choices": [{"message": {"content": "ok"}}]}))
    client = build_client(session, base_url="http://localhost:11434/v1/")
    client.complete("hi")
    assert session.calls[0]["url"] == "http://localhost:11434/v1/chat/completions"


def test_complete_401_error_mentions_api_key():
    session = _FakeSession(_FakeResponse(401, {"error": {"message": "bad key"}}))
    with pytest.raises(LLMError, match="API key"):
        build_client(session).complete("hi")


def test_complete_non_200_returns_detail():
    session = _FakeSession(_FakeResponse(429, {"error": {"message": "rate limited"}}))
    with pytest.raises(LLMError, match="HTTP 429"):
        build_client(session).complete("hi")


def test_complete_network_failure_is_llm_error():
    session = _FakeSession(ConnectionError("boom"))
    with pytest.raises(LLMError):
        build_client(session).complete("hi")


def test_complete_unexpected_body_is_llm_error():
    session = _FakeSession(_FakeResponse(200, {"nope": True}))
    with pytest.raises(LLMError, match="unexpected"):
        build_client(session).complete("hi")


def test_missing_key_never_reaches_the_wire(monkeypatch):
    monkeypatch.delenv(OPENAI_API_KEY_ENV, raising=False)
    session = _FakeSession(_FakeResponse(200, {"choices": [{"message": {"content": "x"}}]}))
    client = OpenAICompatibleClient(session=session, api_key=None)
    with pytest.raises(LLMError):
        client.complete("hi")
    assert session.calls == []