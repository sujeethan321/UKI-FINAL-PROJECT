# Day 9 Step 9.6 — Customer Communication & Delivery Integration

Date: 2026-11-04 (Asia/Colombo).

## Audit, implementation and existing code reused

Inspected payment-reminder model/schema/router/service, reminder creation and history UI, customer profile/schema/phone handling, notification architecture and session-scoped frontend, approved-owner authorization, existing Axios/JWT handling, route registration, isolated pytest fixtures, frontend Node/Vite SSR tests and Git status. There was no preference/opt-out model or communication-attempt history. Notification read state is an inbox feature and is not suitable as message-delivery evidence.

Reused existing saved outstanding-v1 reminder messages, effective ledger reads, account locking, approved-owned-business checks, active Shop Owner JWT/RBAC, SQLAlchemy request transactions, UTC timestamp helper, Axios interceptor, secure keys/fingerprints, financial formatting and existing card/form/alert styles. The existing Notifications page now exposes Review WhatsApp handoff on a confirmed saved reminder or its history details. Selecting a history record selects its authorized customer; a scoped review panel appears alongside the existing reminder form/history. Notification inbox, sidebar, header, English/Tamil reminder previews and all financial calculations are retained.

The implementation adds the smallest usable preference audit and handoff request log rather than assuming consent or borrowing notification statuses. No default-true permission exists. Only manual WhatsApp click-to-chat is implemented. Goods delivery and Driver workflows are unchanged.

## WhatsApp integration and message source

Official reference: [WhatsApp Help Center — How to use click to chat](https://faq.whatsapp.com/5913398998672934).

URL format: https://wa.me/<international numeric mobile>?text=<URL-encoded saved message>.

The backend uses urllib.parse.quote with UTF-8 and the frontend independently validates the destination origin/path/query against the reviewed message, then uses encodeURIComponent for its validated URL. English, Tamil and reserved characters round-trip without translation or amount changes. Only the number and text are included: no authentication tokens, internal entity IDs, account records, notes or confidential application links are added to the outgoing URL. Saved content containing HTTP links, www links or Bearer-style text is blocked rather than silently rewritten.

A saved server-generated reminder is mandatory. Local unsaved previews cannot be handed off. The panel retrieves the exact saved message and amount snapshot, shows them for review, and explains what will be shared with WhatsApp. The backend verifies that the account remains active, its current effective balance is positive, and that balance still equals the saved snapshot. A changed/settled balance blocks the old message; the owner must review the account and create a new reminder when the existing cooldown allows. No regeneration or frontend financial calculation changes the saved text.

Only the explicit Open WhatsApp click opens a blank window, severs its opener reference, and requests the authorized handoff. The window navigates to the validated wa.me URL only after the API confirms the attempt. Failed/blocked/unsafe operations close the blank window or report a popup issue. No automatic opening occurs on selection, preview or save. WhatsApp still requires the user to send manually. Tests use fake windows and never contact WhatsApp.

## Phone normalization

The existing customer API stores local Sri Lankan mobile numbers and accepts local/+94 entry; stored numbers were not rewritten and existing validators were not relaxed. Handoff normalization separately supports:

- 0771234567 -> 94771234567.
- +94771234567 -> 94771234567.
- 94771234567 -> 94771234567.
- ASCII spaces, parentheses and hyphens around these supported representations.

The accepted mobile shape is 07 followed by eight ASCII digits, or the equivalent 947 followed by eight digits, matching the project's existing mobile-number scope. Missing, short/long, unsupported foreign, nine-digit country-ambiguous, 0094-prefixed, non-ASCII-digit and URL-like inputs are rejected. This validates supported formatting, not actual phone ownership or WhatsApp registration. No country code is invented for an ambiguous number.

## Consent, opt-out and accurate status semantics

communication_consents is an append-only audit of an owner's recording of the customer's actual stated WhatsApp preference. Each record includes business/customer/recording-user FKs, channel=whatsapp, granted or opted_out, normalized phone when present, short required evidence of when/how the customer stated it, operation key and UTC time. An explicit true confirmation is required; unknown is represented by no applicable grant, never by an assumed/default grant.

A grant binds to the customer's current normalized number. Changing the number makes permission unknown until a new customer statement is recorded. An opt-out blocks the channel regardless of a number change. A new, explicitly recorded customer statement can supersede a prior preference; replaying an old grant does not create a newer entry or undo a later opt-out. Evidence is retained internally and is not placed in WhatsApp messages or notifications. The API/UI explicitly labels this owner-recorded evidence as not independently verified; it is not a claim that the application obtained or independently verified customer consent.

Current eligibility is checked on every handoff, including key replays. A previously prepared attempt cannot bypass a subsequent opt-out, contact change or settled account. The preview exposes unknown/granted/opted_out and a meaningful restriction before enabling Open WhatsApp. Existing reminder responses now reflect current permission metadata instead of permanently claiming unknown; automated delivery remains unavailable.

communication_attempts records only status=handoff_requested, with business/customer/reminder/consent/requesting-user FKs, channel, normalized destination, key and UTC time. The server prepared a URL for an authenticated request; it cannot confirm browser navigation, WhatsApp launch, sending, receipt or reading. Recent requests (at most 20) are displayed in the review panel. No user-reported-sent feature, provider-confirmed state, delivered/read mutation or reminder-status update was added. Existing reminder.status always remains recorded. Existing notification.is_read remains solely an inbox read state.

## Backend API contracts and security

All routes use existing /api/v1 conventions, active Shop Owner JWT authentication, approved owned-business authorization and no-store responses. Helpers never commit; routes commit preference/attempt transactions and sanitize database failures. Existing account-before-customer locking serializes handoff eligibility with financial/reminder writes; customer locking serializes preference changes and current consent reads. Cross-business/customer/reminder IDs are concealed with scoped 404 responses, while unowned/unapproved business access is forbidden.

GET /api/v1/shop-owner/payment-reminders/{reminder_id}/communication?business_id=<id>&customer_id=<id>

Returns business_id, customer_id, reminder_id, exact message, language, outstanding_amount decimal string, currency=LKR, consent_status, consent_source, normalized_phone, eligible, blocked_reason, at most 20 attempt summaries and provider_delivery_available=false. It reads authorized saved records; it does not create an attempt or call a provider.

POST /api/v1/shop-owner/customers/{customer_id}/communication/consent?business_id=<id>

Body: channel=whatsapp, consent_status=granted|opted_out, evidence (trimmed printable 1..500 characters), confirmed=true (strict boolean), idempotency_key. No arbitrary phone field is accepted. Returns consent_id, scoped business/customer IDs, recorded_by, channel/status, UTC created_at, source=owner_recorded_customer_statement, independently_verified=false and replayed. New records return 201; exact replays return 200.

POST /api/v1/shop-owner/payment-reminders/{reminder_id}/whatsapp-handoff?business_id=<id>

Body: customer_id (strict positive integer), channel=whatsapp, idempotency_key. Returns attempt_id, business/customer/reminder IDs, normalized_phone, exact message, handoff_url, channel, status=handoff_requested, UTC created_at, replayed and provider_delivery_available=false. New records return 201; exact eligible replays return 200.

Unknown fields, custom phone/message/amount/status, unsupported channels and invalid IDs/keys are rejected. The server derives all contact, permission, business and financial information from authorized database rows. There is no arbitrary-recipient or arbitrary-phone messaging endpoint. 401/403/404/409/422/5xx are handled with sanitized frontend feedback. Raw diagnostics, full handoff URLs, contact values and message text are not logged by the new code.

## Idempotency and safe retry

Both tables have case-sensitive unique (business_id, idempotency_key) constraints. Replays compare scoped entity, actor and operation content; different intent conflicts. Concurrent handoff requests serialize on the existing credit-account lock, and DB uniqueness/retry handling arbitrates remaining key races. The real independent-session race test confirms one attempt for two simultaneous identical requests.

Frontend operations retain an opaque SHA-256 fingerprint/key/pending record in per-user session storage. No phone, message, evidence or balance is stored there. The handoff fingerprint includes the reviewed phone/message and saved-reminder scope. Duplicate clicks are locked synchronously. Timeout/uncertain results retain the same key across remounts; a different operation cannot overwrite an unresolved intent. Confirmed operations remain retryable with the same key without duplicating the audit row. A definitive first rejection can allow a different intent, while prior uncertainty remains protected. Unmount/business/customer/reminder changes abort stale requests and close pending blank windows.

## Additive migration

backend/alembic/versions/e5f1a4b3c803_add_communication_records.py follows d4e0f3a2b702 and creates only communication_consents and communication_attempts, their FKs, constraints and indexes. No stored customer phones, ledger entries, reminders, notifications or migration history were rewritten. Downgrade refuses to delete audit records; any rollback must be an additive forward migration.

The configured database, engine target and actual SELECT DATABASE() were checked as lankapex_test_db before upgrade. Upgrade succeeded and comparison of both new tables against ORM metadata returned no differences. No development migration was applied and backend/.env was not changed. Live development use requires deliberate application of pending additive migrations to the intended development database.

## Verification

Final full backend regression: **633 passed, 0 failed, 0 skipped**, exit 0 (170.69 seconds), including all 62 new communication checks and the existing reminder, notification, Credit Sales, Repayments, financial-document, database, JWT and authorization suites. One existing InsecureKeyLengthWarning comes from the deliberately short incorrect signing key in test_tampered_token_rejected. All eleven application tables were verified empty after the suite, with no residual test preference, handoff or financial rows. The applied test revision and sole migration head are e5f1a4b3c803; a repeat upgrade was a no-op. Python syntax/import/OpenAPI and Git whitespace checks passed. The final full backend suite was restarted after adding live preference metadata to existing reminder responses so that the complete run covers the final code.

Frontend verification: npm test passed 288 tests, 0 failed/skipped/cancelled (33.82 seconds). This includes 38 new communication checks and all prior reminder/notification/financial frontend tests. npm run build passed with Vite 8.3.5 and 2156 modules. The final JavaScript chunk is 542.84 kB minified / 158.13 kB gzip, retaining the project's non-failing warning above 500 kB. Targeted ESLint passed on all new/modified frontend files. Frontend API adapters and window navigation are mocked; no development records or real WhatsApp messages are created.

Focused backend communication tests initially passed 60 cases and the independent-session race passed separately; the final suite also includes the added live-permission reminder-response test. Coverage includes real JWT/roles/approval, cross-business/customer/reminder isolation, missing/invalid IDs, normalized phones, unknown permission, opt-out and grant replay, changed contacts/balances, exact saved English/Tamil encoding, no financial or reminder-status writes, duplicate handoff requests, input rejection, safe database errors and schema constraints.

Browser smoke test is unavailable: no browsers were connected, and opening an in-app browser returned Browser is not available: iab. Real popup/navigation behavior and visual layout need checking in a connected authenticated browser. No actual customer message was opened or sent during verification.

Day 9 Step 9.6 implementation and required test/build verification are complete. Development migration activation and interactive browser verification remain pending.

## Deferred SMS/email provider extension

No provider client or unused abstraction was added. Future work should extend the controlled channel enum and per-channel preference/contact validation only when the corresponding provider integration is implemented. SMS requires verified/eligible mobile contact; email requires a separately verified customer email address, which must not be inferred from a user login email or customer name.

A future server-side adapter should accept an authorized persisted communication intent, validate current contact/permission and message policy, and return a provider operation reference plus its actual evidence state. Do not accept client-provided balances or arbitrary destination URLs. Durable post-commit dispatch/outbox handling must avoid making network calls while holding financial locks or causing a provider failure to rewrite a financial transaction.

Use one stable outbound idempotency key per intended provider operation and a unique provider-event identifier. Network timeouts remain uncertain; reconcile the original operation before a retry rather than generating a new send. Provider acceptance alone is not independently verified delivery.

Delivery callbacks must verify the provider's documented signature/HMAC over the original raw request, use timestamp/replay protection where supported, match the configured provider/account/reference, deduplicate event IDs and validate allowed transitions. Store append-only evidence; introduce provider-confirmed sent/delivered/read states only when authenticated provider evidence supports them. Existing reminder snapshots and ledger history remain immutable.

Keep future credentials in server-only environment/secret management, never VITE variables or browser storage. Redact message/contact/URL bodies in logs. Configure explicit provider timeouts, rate limits, retry policy and credential rotation. No SMS/email send buttons, credentials, paid integrations, webhooks, background infrastructure or delivery claims exist in this step.

## Files created

- backend/app/models/communication.py
- backend/app/schemas/communication.py
- backend/app/services/communication_service.py
- backend/app/routers/shop_owner_communication.py
- backend/alembic/versions/e5f1a4b3c803_add_communication_records.py
- backend/tests/test_communication.py
- backend/tests/test_communication_concurrency.py
- frontend/src/services/communicationService.js
- frontend/src/utils/communication.js
- frontend/src/pages/shopOwner/communicationWorkflow.js
- frontend/src/pages/shopOwner/ReminderCommunication.jsx
- frontend/tests/communication.test.js
- frontend/tests/communicationView.test.js
- docs/day9-customer-communication.md

## Files modified

- backend/app/models/__init__.py: register communication models.
- backend/app/main.py: mount the communication router.
- backend/app/schemas/payment_reminder.py: truthful current permission metadata and unchanged unavailable provider-delivery state.
- backend/app/services/shop_owner_reminder_service.py: reflect current preference metadata without changing saved amount/message/status or creation cooldown.
- frontend/src/pages/shopOwner/ShopOwnerNotifications.jsx: scoped saved-reminder handoff review, accurate permission/provider wording, existing reminder/inbox preservation.

All pre-existing edits from earlier steps were retained. No automatic commits, pushes, real sends, goods-delivery integration or role changes were performed.
