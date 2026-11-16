# Step 99 — GroqCloud HTTP client

The backend AI boundary consists of immutable text request/result objects, a
provider-neutral client protocol, sanitized failure categories, and a GroqCloud
adapter built on the existing `httpx` dependency. The adapter is constructed
with validated backend settings and an injected `httpx.AsyncClient`; it owns no
database session and cannot write credit, repayment, ledger or customer data.

The adapter sends two bounded messages to the configured
`/chat/completions` endpoint, uses the configured model and output-token limit,
and performs no automatic retry. It never returns raw provider responses. API
keys, prompts, generated text and financial context must not be logged.

The later Tamil credit-summary service will first use LankaPex's authorized,
deterministic ledger calculations to build a minimal financial snapshot. It
will convert only necessary non-identifying facts into fixed system/user
messages, ask this adapter for explanatory Tamil text, and keep the verified
backend snapshot authoritative. This client does not itself read a ledger,
select a customer, approve credit or persist generated output.

All current tests use `httpx.MockTransport` or an injected in-memory method.
No live provider request is part of Step 99. A future connection check requires
separate authorization and must use synthetic input only.
