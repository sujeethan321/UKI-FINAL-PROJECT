# Customer credit account linking — source-only implementation

## Verified cause

`create_business_customer` creates `CustomerProfile.user_id=None`.
`customer_dashboard_service.scoped_accounts`, linked shops, history and
statements require `CustomerProfile.user_id` to equal the JWT Customer ID.
The Owner ledger is therefore populated while the separately registered
Customer sees zero linked accounts. The isolated test reproduced that empty
state before linking and a `75.15` balance after one `100.25` credit sale and
one `25.10` repayment. No ledger entry was altered by linking.

The active demo records could not be inspected from the sandbox identity
because the demo credential is DPAPI CurrentUser protected for the operator.
The test connection was independently confirmed as `APP_ENV=testing`, actual
`lankapex_test_db`, revision `03b9c2d1e671`. No test was run on the demo or
development database.

## Workflow

An authenticated Owner of an approved business requests an invitation for one
of that business's unlinked customer profiles and names the registered
Customer's email. The backend verifies an active Customer account, signs a
15-minute invitation for that exact Customer ID, business, profile and Owner,
and returns the code once with `Cache-Control: no-store`. The Owner shares it
privately. The Customer logs in and pastes the code in the Customer Dashboard.
Acceptance verifies signature, type, expiry, registered account/role, current
Owner membership, business approval and the still-unlinked profile, then sets
only `CustomerProfile.user_id` within a transaction. The business/profile row
locks serialize concurrent acceptances. A second use or a different Customer
gets the same generic unavailable response. No name, phone or email-only
automatic linking occurs. The code is neither put in a URL nor persisted in
browser storage. Existing ledger amounts and balances remain untouched.

Routes under `/api/v1`:

- `POST /shop-owner/customers/{customer_id}/link-invitations?business_id=N`
  with `{"recipient_email":"registered@example.com"}`; response has
  `invitation` and `expires_at`.
- `POST /customer/link-invitations/accept` with `{"invitation":"..."}`;
  response has `customer_id`, `business_id`, `linked:true`.

The invitation is a signed bearer code, so it must be shared privately. A
registered Customer explicitly accepting it is the consent step; it does not
establish real-world identity independently. The Owner should verify the
Customer's registered address with them before issuing it. The token is
effectively single-use because the profile cannot be accepted twice; there is
no unlink API. No migration is required, and no live database was changed.

## Verification and rollout boundary

Backend: 57 targeted customer and linking tests passed in the verified
isolated `lankapex_test_db`, including JWT role denial, wrong Owner, wrong
Customer, expired code, replay, balance, history, statement and cross-Customer
isolation. Frontend: 12 targeted tests passed; production build passed with a
temporary valid build URL. Browser/live demo verification has not run.

Deploying or restarting the demo backend with this new source, issuing an
invitation, and accepting it against `lankapex_demo_db` would change live demo
state and require separate authorization. The current demo server may still
be running old code; do not infer that these routes are live until restarted
and verified. `lankapex_db` and existing financial records were untouched.
