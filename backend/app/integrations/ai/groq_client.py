"""GroqCloud adapter using its OpenAI-compatible chat-completions API."""
from typing import Any

import httpx

from app.core.config import Settings
from app.integrations.ai.base import (
    AIClientError, AIFailureCategory, GenerationRequest, GenerationResult,
    MAX_GENERATION_INPUT_BYTES,
)

# Backward-compatible local name used by the adapter's focused tests.
MAX_INPUT_BYTES = MAX_GENERATION_INPUT_BYTES


class GroqAIClient:
    """Transport-only adapter; it has no database or financial write access."""

    def __init__(self, config: Settings, http_client: httpx.AsyncClient):
        self._config = config
        self._http = http_client
        timeout = config.GROQ_TIMEOUT_SECONDS
        self._timeout = httpx.Timeout(timeout, connect=min(3.0, timeout))

    def _credential(self) -> str:
        if not self._config.AI_ENABLED or self._config.GROQ_API_KEY is None:
            raise AIClientError(AIFailureCategory.CONFIGURATION)
        secret = self._config.GROQ_API_KEY.get_secret_value()
        if not secret:
            raise AIClientError(AIFailureCategory.CONFIGURATION)
        return secret

    def _validate_request(self, request: GenerationRequest, credential: str) -> None:
        if not isinstance(request, GenerationRequest):
            raise AIClientError(AIFailureCategory.INVALID_REQUEST)
        prompts = (request.system_prompt, request.user_prompt)
        if any(not isinstance(value, str) or not value.strip() or "\x00" in value
               for value in prompts):
            raise AIClientError(AIFailureCategory.INVALID_REQUEST)
        if sum(len(value.encode("utf-8")) for value in prompts) > MAX_INPUT_BYTES:
            raise AIClientError(AIFailureCategory.INVALID_REQUEST)
        # Fail closed if the provider credential is ever accidentally placed in
        # prompt text. The adapter never adds configuration values to messages.
        if any(credential in value for value in prompts):
            raise AIClientError(AIFailureCategory.INVALID_REQUEST)

    @staticmethod
    def _result(payload: Any, model: str, max_tokens: int) -> GenerationResult:
        try:
            choices = payload["choices"]
            choice = choices[0]
            content = choice["message"]["content"]
            finish_reason = choice.get("finish_reason")
        except (KeyError, IndexError, TypeError):
            raise AIClientError(AIFailureCategory.INVALID_RESPONSE) from None
        if (not isinstance(choices, list) or not isinstance(choice, dict)
                or not isinstance(content, str) or not content.strip()
                or (finish_reason is not None and not isinstance(finish_reason, str))
                or len(content.encode("utf-8")) > max_tokens * 32):
            raise AIClientError(AIFailureCategory.INVALID_RESPONSE)
        return GenerationResult(text=content.strip(), model=model, finish_reason=finish_reason)

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        credential = self._credential()
        self._validate_request(request, credential)
        endpoint = f"{self._config.GROQ_BASE_URL}/chat/completions"
        body = {
            "model": self._config.GROQ_MODEL,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "max_tokens": self._config.GROQ_MAX_OUTPUT_TOKENS,
            "temperature": 0.2,
        }
        try:
            response = await self._http.post(
                endpoint,
                headers={"Authorization": f"Bearer {credential}",
                         "Content-Type": "application/json"},
                json=body,
                timeout=self._timeout,
            )
        except httpx.TimeoutException:
            raise AIClientError(AIFailureCategory.TIMEOUT) from None
        except httpx.NetworkError:
            raise AIClientError(AIFailureCategory.CONNECTION) from None

        if response.status_code in (401, 403):
            raise AIClientError(AIFailureCategory.AUTHENTICATION)
        if response.status_code == 429:
            raise AIClientError(AIFailureCategory.RATE_LIMITED)
        if 500 <= response.status_code <= 599:
            raise AIClientError(AIFailureCategory.PROVIDER_ERROR)
        if response.status_code >= 400:
            raise AIClientError(AIFailureCategory.INVALID_REQUEST)
        try:
            payload = response.json()
        except (ValueError, TypeError):
            raise AIClientError(AIFailureCategory.INVALID_RESPONSE) from None
        return self._result(
            payload, self._config.GROQ_MODEL,
            self._config.GROQ_MAX_OUTPUT_TOKENS,
        )

