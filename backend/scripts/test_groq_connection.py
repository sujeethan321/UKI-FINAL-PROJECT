"""Guarded one-request GroqCloud connectivity check.

This module intentionally has no database, ORM, model, router, or financial
imports. Default mode validates configuration and performs no network request.
"""
import argparse
import asyncio
from dataclasses import dataclass
import sys
from pathlib import Path

MODEL = "openai/gpt-oss-120b"
BASE_URL = "https://api.groq.com/openai/v1"
TIMEOUT_SECONDS = 10.0
# GPT-OSS is a reasoning model. Completion-token accounting can include hidden
# reasoning before visible content. 64 tokens was too tight for a useful
# connectivity assertion; 256 remains below the application's 400-token cap.
MAX_OUTPUT_TOKENS = 256
SYSTEM_PROMPT = "Return one short acknowledgement in Tamil. Do not add facts or advice."
USER_PROMPT = "இது LankaPex GroqCloud இணைப்பு சோதனை. உண்மையான வாடிக்கையாளர் அல்லது நிதித் தரவு இல்லை."
SAFE_CATEGORIES = {
    "configuration", "invalid_request", "authentication", "rate_limited",
    "timeout", "connection", "provider_error", "invalid_response",
}


class Stop(RuntimeError):
    def __init__(self, category="configuration", diagnostic="UNSPECIFIED"):
        self.category = category if category in SAFE_CATEGORIES else "provider_error"
        self.diagnostic = diagnostic
        super().__init__(self.category)


@dataclass(frozen=True, slots=True)
class Options:
    execute: bool
    confirm_model: str | None


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-model")
    parsed = parser.parse_args(argv)
    if parsed.execute and parsed.confirm_model != MODEL:
        raise Stop("configuration")
    if not parsed.execute and parsed.confirm_model is not None:
        raise Stop("configuration")
    return Options(parsed.execute, parsed.confirm_model)


def validate_config(config):
    try:
        secret = config.GROQ_API_KEY.get_secret_value() if config.GROQ_API_KEY else ""
        checks = (
            ("AI_DISABLED", config.AI_ENABLED is True),
            ("KEY_MISSING", bool(secret)),
            ("BASE_URL_MISMATCH", config.GROQ_BASE_URL == BASE_URL),
            ("MODEL_MISMATCH", config.GROQ_MODEL == MODEL),
            ("TIMEOUT_MISMATCH", float(config.GROQ_TIMEOUT_SECONDS) == TIMEOUT_SECONDS),
            ("TOKEN_BUDGET_MISMATCH", int(config.GROQ_MAX_OUTPUT_TOKENS) == MAX_OUTPUT_TOKENS),
        )
    except Exception:
        raise Stop("configuration", "INVALID_SETTINGS_SHAPE") from None
    for diagnostic, valid in checks:
        if not valid:
            raise Stop("configuration", diagnostic)


def load_validated_settings():
    # Imported only for an operator invocation. Importing this script for its
    # database-free tests does not load dotenv or inspect any real secret.
    backend = str(Path(__file__).resolve().parents[1])
    if backend not in sys.path:
        sys.path.insert(0, backend)
    try:
        from app.core.config import load_settings
        return load_settings()
    except ImportError:
        raise Stop("configuration", "BACKEND_IMPORT") from None
    except Exception:
        raise Stop("configuration", "SETTINGS_VALIDATION") from None


async def generate_once(config, request):
    # No retry transport is configured. The adapter itself issues one POST.
    import httpx
    from app.integrations.ai.groq_client import GroqAIClient
    async with httpx.AsyncClient(follow_redirects=False, trust_env=False) as http:
        return await GroqAIClient(config, http).generate(request)


def make_request():
    from app.integrations.ai.base import GenerationRequest
    return GenerationRequest(system_prompt=SYSTEM_PROMPT, user_prompt=USER_PROMPT)


def run(argv=None, config_loader=None, executor=None, request_factory=None):
    options = arguments(argv)
    config = (config_loader or load_validated_settings)()
    validate_config(config)
    if not options.execute:
        return "PASS: exact GroqCloud test configuration; NO NETWORK REQUEST"

    request = (request_factory or make_request)()
    try:
        result = asyncio.run((executor or generate_once)(config, request))
    except Exception as exc:
        category = getattr(getattr(exc, "category", None), "value", None)
        if category not in SAFE_CATEGORIES:
            category = "provider_error"
        raise Stop(category) from None
    if (getattr(result, "model", None) != MODEL
            or not isinstance(getattr(result, "text", None), str)
            or not result.text.strip()):
        raise Stop("invalid_response")
    # Generated provider text is intentionally discarded and never printed.
    return "PASS: one sanitized GroqCloud connection request completed"


def main(argv=None):
    try:
        print(run(argv))
        return 0
    except (Stop, SystemExit) as exc:
        if isinstance(exc, SystemExit):
            print("STOP: GroqCloud connection-test arguments rejected", file=sys.stderr)
        else:
            print(f"STOP: GroqCloud connection test failed category={exc.category}; diagnostic={exc.diagnostic}", file=sys.stderr)
        return 1
    except Exception:
        print("STOP: GroqCloud connection test failed category=configuration", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
