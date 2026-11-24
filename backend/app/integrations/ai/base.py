# Purpose: Define the AI request, response, and client contracts so summary logic can use interchangeable providers.
"""Small provider-neutral boundary for explanatory text generation.

The contract deliberately accepts text only. Database sessions, ORM models and
financial writers do not belong at the external-provider boundary.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

MAX_GENERATION_INPUT_BYTES = 16_384


# Group the state and operations for ai failure category in the base module.
class AIFailureCategory(str, Enum):
    CONFIGURATION = "configuration"
    INVALID_REQUEST = "invalid_request"
    AUTHENTICATION = "authentication"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    CONNECTION = "connection"
    PROVIDER_ERROR = "provider_error"
    INVALID_RESPONSE = "invalid_response"


class AIClientError(Exception):
    """Sanitized failure safe to classify without provider response details."""

    # Initialize the dependencies and state this instance needs for later operations.
    def __init__(self, category: AIFailureCategory):
        self.category = category
        super().__init__(f"AI generation failed ({category.value})")


# Group the state and operations for generation request in the base module.
@dataclass(frozen=True, slots=True)
class GenerationRequest:
    system_prompt: str
    user_prompt: str
    response_schema: dict | None = None


# Group the state and operations for generation result in the base module.
@dataclass(frozen=True, slots=True)
class GenerationResult:
    text: str
    model: str
    finish_reason: str | None = None


# Group the state and operations for ai client in the base module.
class AIClient(Protocol):
    async def generate(self, request: GenerationRequest) -> GenerationResult:
        """Generate bounded explanatory text or raise a sanitized error."""

