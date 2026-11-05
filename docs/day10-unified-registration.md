# Day 10 Step 10.3 — Unified registration

## Routes and selection
/register now renders the existing RegisterPage directly, selecting Shop Owner initially. /register/shop-owner, /register/customer and /register/driver render the same page with their corresponding initial selection. Unsupported role URLs return to /register without displaying an Admin option.

Role selection stays within the mounted form and updates the existing brand panel. Switching roles clears all fields, password confirmation and validation errors, preventing a previous role's draft from being submitted accidentally. Switching to the currently selected role leaves the draft intact. The existing native radios, teal selected border, light teal fill, circular checkmark, icons, focus styles, card descriptions and responsive classes are retained. No colors or CSS files changed.

The role cards, inputs, language selector, password-visibility button and submit control are disabled during submission. The shared controller synchronously locks duplicate submissions. Leaving the page suppresses stale success navigation; cancellation before dispatch prevents an unsent request from starting. A request already sent to the backend cannot be undone by leaving the page.

## API and post-registration flow
Verified app.main mounts auth_router at /api/v1, and auth_router has prefix /auth. Existing services remain unchanged:
- POST /api/v1/auth/register/shop-owner
- POST /api/v1/auth/register/customer
- POST /api/v1/auth/register/driver

The selected public role determines which existing service is called. Payloads contain only the existing full_name, email, password, phone and preferred_language fields. Name/email/phone trimming and email normalization are retained; required fields, password confirmation and backend-aligned length/language bounds are checked before dispatch. Backend validation remains authoritative.

Successful registration retains the existing navigation to /login, with registrationSuccess in router state. Registration does not store a token, sign in automatically, change account status or approve a business. Backend role assignment, driver account-status rules, JWT authentication and business isolation remain unchanged. There is no public Admin registration endpoint or role card.

Landing Get Started and the login form's Create an account link now use /register. Landing login and registration login links continue to use /login. Existing role-specific registration links remain valid.

## Files changed in this step
- frontend/src/App.jsx
- frontend/src/pages/auth/RegisterPage.jsx
- frontend/src/pages/auth/RegistrationForm.jsx
- frontend/src/pages/auth/LoginForm.jsx (registration link only)
- frontend/src/pages/landing/LandingPage.jsx (Get Started destination only)
- frontend/tests/authenticationRoles.test.js

Created:
- frontend/src/utils/registration.js (state/submission controller used by the existing form)
- docs/day10-unified-registration.md

No second registration page or form was created. No backend, database, JWT, financial, reminder or notification implementation was changed. Pre-existing edits were preserved; no commit or push was performed.

## Verification
Registration tests cover /register, all three legacy routes, initial and changed role selection, one checked radio, existing selected-card styling, correct service and API contracts, validation failures, duplicate submission, locked controls, draft clearing, no Admin registration, navigation links, post-registration success and stale-request handling. Existing protected-route/login and financial tests remain in the full suite.

Vite build and targeted registration/auth JSX lint passed. The existing JavaScript bundle-size warning remains.

The first parallel full-suite run passed 357 of 358 tests; an unchanged repayment test failed its fixed 15 ms scheduling assertion. The full suite was rerun serially to distinguish this timing failure from a regression. See the final result below.

Backend tests were not run because backend files were unchanged; no development or test database was mutated.

Browser inventory returned no connected browsers. Desktop/mobile visual inspection, live role-card keyboard interaction and real account creation are not claimed. Existing mobile classes and native radio behavior were retained and checked in rendered markup.

Final full-suite result: node --test --test-concurrency=1 — 358 passed, 0 failed (48.5 seconds). This uses the existing package test runner with sequential test-file execution. The unrelated timing-sensitive repayment test passed without modifications.
