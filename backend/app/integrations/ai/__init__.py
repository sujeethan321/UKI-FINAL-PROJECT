"""Provider-neutral AI generation contracts and adapters."""

from .base import AIClient, AIClientError, AIFailureCategory, GenerationRequest, GenerationResult

__all__ = (
    "AIClient", "AIClientError", "AIFailureCategory",
    "GenerationRequest", "GenerationResult",
)
