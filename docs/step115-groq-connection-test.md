# Step 115 — Guarded GroqCloud connection test

Status: **source and mocked tests complete; no live request executed**.

`backend/scripts/test_groq_connection.ps1` uses existing backend `Settings` and `GroqAIClient`. It enables AI only in its child process, pins `https://api.groq.com/openai/v1`, model `openai/gpt-oss-120b`, a 10-second timeout and 256 output tokens, and restores every changed process variable. It does not alter `backend/.env`; persistent `AI_ENABLED` remains false. The original 64-token connection-test cap was replaced after the first live response was unusable: GPT-OSS completion accounting can spend tokens on reasoning before visible content. The revised cap remains below the application's 400-token default.

The Python runner imports no database engine, ORM model, router, financial service, or QR evidence tool. Default mode validates the secret-backed settings but never constructs an HTTP client. Execution requires both `--execute` and exact model confirmation, constructs one `httpx.AsyncClient` with no retry layer, calls `GroqAIClient.generate` once, validates the small result, discards its text, and prints only PASS or a sanitized failure category.

The sole user prompt is the reviewed harmless Tamil sentence. It contains no customer or financial data. The fixed system message only requests a short Tamil acknowledgement and prohibits added facts or advice. Neither prompt nor the response is printed.

## Future operator commands

Read-only/network-free preflight from the repository root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\test_groq_connection.ps1
```

Expected:

```text
PASS: exact GroqCloud test configuration; NO NETWORK REQUEST
```

One-request execution requires separate explicit authorization:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\test_groq_connection.ps1 -Execute -ConfirmModel openai/gpt-oss-120b
```

Possible sanitized STOP categories are `configuration`, `invalid_request`, `authentication`, `rate_limited`, `timeout`, `connection`, `provider_error`, and `invalid_response`. Do not retry automatically. Preserve only the timestamp, exit code, and category; never capture environment values, headers, prompts, or provider bodies.

Prerequisites are an existing backend-only `GROQ_API_KEY`, persistent `AI_ENABLED=false`, outbound HTTPS permission to `api.groq.com:443`, and explicit authorization for one external request. No MySQL credential or application server is needed.
