# Step 118 — GroqCloud `invalid_response` investigation

Status: **offline investigation and mocked regression tests complete; no live request executed**.

## Confirmed code findings

The PowerShell wrapper set process-only AI configuration and invoked `test_groq_connection.py` once. That runner constructed the existing `GroqAIClient`, whose single `httpx` POST either returned a `GenerationResult` or raised a sanitized `AIClientError`. Authentication, rate-limit, timeout, connection, 5xx, and other HTTP failure paths have distinct categories. The observed `invalid_response` therefore arose after an HTTP response reached response parsing.

The adapter intentionally returns `invalid_response` for non-JSON data; missing, empty, or malformed `choices`; a missing or malformed message; null, empty, or non-string `message.content`; an invalid `finish_reason`; or content exceeding its bounded size. The runner also checks model equality and nonempty text, although the real adapter already enforces those properties before returning.

The prior run did not retain the body, content, reasoning field, finish reason, usage, or status code. That was intentional privacy behavior. Consequently, the exact provider response and exact failing predicate cannot be recovered and must not be fabricated.

## Leading hypothesis

`openai/gpt-oss-120b` is a reasoning model. A 64-token completion budget can be consumed by reasoning before visible assistant content is produced. A structurally valid response with null/empty content and `finish_reason="length"` is rejected correctly because LankaPex requires usable explanatory text. Mocked tests now reproduce that response and confirm the existing sanitized `invalid_response` behavior.

Other plausible explanations remain: malformed/non-JSON 2xx content, a changed choices/message shape, null content for another provider reason, invalid finish metadata, or a redirect body because redirects are disabled. There is no evidence selecting among these alternatives.

## Minimal correction

Only the guarded connection-test budget changed, from 64 to 256 output tokens. This remains bounded and below the application's existing 400-token default. The production adapter, prompt, model, timeout, no-retry behavior, response validation, and privacy controls remain unchanged. Empty or reasoning-only output is still rejected rather than treated as a successful financial-summary response.

A new live request is required to verify whether this correction addresses the actual provider behavior. It requires separate authorization and must not be automatically retried.
