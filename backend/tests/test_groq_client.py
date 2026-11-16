"""Fully mocked, database-free tests for the GroqCloud transport adapter."""
import asyncio
import json

import httpx
import pytest

from app.core.config import Settings
from app.integrations.ai.base import AIClientError, AIFailureCategory, GenerationRequest
from app.integrations.ai.groq_client import GroqAIClient, MAX_INPUT_BYTES

SYNTHETIC_KEY = "gsk_offline_client_7Qx2mN9pL4vR8sT6"


def config(**updates):
    values = dict(
        MYSQL_USER="fixture", MYSQL_PASSWORD="fixture-password",
        MYSQL_DATABASE="lankapex_db", JWT_SECRET_KEY="fixture-signing-secret",
        AI_ENABLED=True, GROQ_API_KEY=SYNTHETIC_KEY,
    )
    return Settings(_env_file=None, **(values | updates))


def request():
    return GenerationRequest(
        system_prompt="Explain only the supplied synthetic facts in Tamil.",
        user_prompt="Synthetic balance: LKR 10.00",
    )


def response():
    return httpx.Response(200, json={"choices": [{"message": {"content": "சோதனை சுருக்கம்"},
                                                    "finish_reason": "stop"}]})


def run(client, value=None):
    return asyncio.run(client.generate(value or request()))


def mocked(handler, **updates):
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return GroqAIClient(config(**updates), http), http


def test_exact_endpoint_model_header_messages_and_limits():
    seen = []

    def handler(incoming):
        seen.append(incoming)
        assert str(incoming.url) == "https://api.groq.com/openai/v1/chat/completions"
        assert incoming.headers["authorization"] == f"Bearer {SYNTHETIC_KEY}"
        body = json.loads(incoming.content)
        assert body == {
            "model": "openai/gpt-oss-120b",
            "messages": [
                {"role": "system", "content": request().system_prompt},
                {"role": "user", "content": request().user_prompt},
            ],
            "max_tokens": 400,
            "temperature": 0.2,
        }
        return response()

    client, http = mocked(handler)
    try:
        result = run(client)
    finally:
        asyncio.run(http.aclose())
    assert result.text == "சோதனை சுருக்கம்"
    assert result.model == "openai/gpt-oss-120b"
    assert result.finish_reason == "stop"
    assert len(seen) == 1


@pytest.mark.parametrize("status, category", [
    (401, AIFailureCategory.AUTHENTICATION),
    (403, AIFailureCategory.AUTHENTICATION),
    (429, AIFailureCategory.RATE_LIMITED),
    (500, AIFailureCategory.PROVIDER_ERROR),
    (503, AIFailureCategory.PROVIDER_ERROR),
    (400, AIFailureCategory.INVALID_REQUEST),
])
def test_http_failures_are_sanitized_and_never_retried(status, category):
    calls = 0

    def handler(_):
        nonlocal calls
        calls += 1
        return httpx.Response(status, text=f"private provider detail {SYNTHETIC_KEY}")

    client, http = mocked(handler)
    try:
        with pytest.raises(AIClientError) as error:
            run(client)
    finally:
        asyncio.run(http.aclose())
    assert error.value.category is category
    assert SYNTHETIC_KEY not in str(error.value)
    assert "private provider detail" not in str(error.value)
    assert calls == 1


@pytest.mark.parametrize("exception, category", [
    (httpx.ReadTimeout("slow"), AIFailureCategory.TIMEOUT),
    (httpx.ConnectError("offline"), AIFailureCategory.CONNECTION),
])
def test_transport_failures_are_sanitized_and_never_retried(exception, category):
    calls = 0

    def handler(_):
        nonlocal calls
        calls += 1
        raise exception

    client, http = mocked(handler)
    try:
        with pytest.raises(AIClientError) as error:
            run(client)
    finally:
        asyncio.run(http.aclose())
    assert error.value.category is category
    assert calls == 1


@pytest.mark.parametrize("provider_response", [
    httpx.Response(200, text="not-json"),
    httpx.Response(200, json={}),
    httpx.Response(200, json={"choices": []}),
    httpx.Response(200, json={"choices": [{"message": {}}]}),
    httpx.Response(200, json={"choices": [{"message": {"content": None}}]}),
    httpx.Response(200, json={"choices": [{"message": {"content": ""}}]}),
    httpx.Response(200, json={"choices": [{
        "message": {"content": None, "reasoning": "synthetic hidden reasoning"},
        "finish_reason": "length",
    }]}),
])
def test_malformed_provider_responses_are_rejected(provider_response):
    client, http = mocked(lambda _: provider_response)
    try:
        with pytest.raises(AIClientError) as error:
            run(client)
    finally:
        asyncio.run(http.aclose())
    assert error.value.category is AIFailureCategory.INVALID_RESPONSE


def test_disabled_ai_stops_before_transport_or_credential_use():
    calls = 0

    def handler(_):
        nonlocal calls
        calls += 1
        return response()

    client, http = mocked(handler, AI_ENABLED=False, GROQ_API_KEY=None)
    try:
        with pytest.raises(AIClientError) as error:
            run(client)
    finally:
        asyncio.run(http.aclose())
    assert error.value.category is AIFailureCategory.CONFIGURATION
    assert calls == 0


@pytest.mark.parametrize("bad_request", [
    GenerationRequest("", "user"),
    GenerationRequest("system", "   "),
    GenerationRequest("system\x00secret", "user"),
    GenerationRequest("system", SYNTHETIC_KEY),
    GenerationRequest("s" * MAX_INPUT_BYTES, "u"),
])
def test_input_boundaries_and_secret_in_prompts_are_rejected_before_transport(bad_request):
    calls = 0

    def handler(_):
        nonlocal calls
        calls += 1
        return response()

    client, http = mocked(handler)
    try:
        with pytest.raises(AIClientError) as error:
            run(client, bad_request)
    finally:
        asyncio.run(http.aclose())
    assert error.value.category is AIFailureCategory.INVALID_REQUEST
    assert calls == 0


def test_configured_timeout_and_output_limit_are_sent():
    observed = {}

    async def inspect_post(url, **kwargs):
        observed.update(url=url, **kwargs)
        return response()

    http = httpx.AsyncClient()
    http.post = inspect_post
    client = GroqAIClient(config(GROQ_TIMEOUT_SECONDS=1.5,
                                 GROQ_MAX_OUTPUT_TOKENS=64), http)
    try:
        run(client)
    finally:
        asyncio.run(http.aclose())
    assert observed["json"]["max_tokens"] == 64
    assert observed["timeout"].read == 1.5
    assert observed["timeout"].connect == 1.5


def test_oversized_output_is_rejected():
    oversized = "x" * (64 * 32 + 1)
    client, http = mocked(
        lambda _: httpx.Response(200, json={"choices": [{"message": {"content": oversized}}]}),
        GROQ_MAX_OUTPUT_TOKENS=64,
    )
    try:
        with pytest.raises(AIClientError) as error:
            run(client)
    finally:
        asyncio.run(http.aclose())
    assert error.value.category is AIFailureCategory.INVALID_RESPONSE

