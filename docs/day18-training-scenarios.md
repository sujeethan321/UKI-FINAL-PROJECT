# Pilot training and synthetic demonstrations

Prepared 2026-11-07. **Draft; no sessions scheduled or delivered.** These are
future facilitator instructions, not execution evidence or real transactions.
Follow the [launch gates](day18-pilot-go-no-go.md) and
[role guide](day18-onboarding-guide.md). AI Summary is not included.

Step 18.5 update: first-time vehicle submission now exists on Driver Dashboard
as **Submit Driver application → Submit for review**. Historical ONB01 references
in the original scenarios below describe the earlier gap; use this current form
before Admin review rather than fixture setup when rehearsing new onboarding.
The browser exercise is still NOT RUN and pilot launch remains NO-GO.

## Sessions proposed for planning

| Role | Suggested duration | Objectives | Practice / teach-back | Common mistakes |
| --- | --- | --- | --- | --- |
| Shop Owner | 20–30 minutes | Select correct business/Customer; distinguish sale/repayment/order/payment | A, B, D; explain one confirmed receipt and an uncertain retry | Wrong Customer, starting a new intent after timeout, treating a request as confirmed |
| Customer | 10–15 minutes | Distinguish Explore Shops/My Shops; review checkout and own credit/tracking | C, D; explain cash unpaid and credit pending | Assuming credit eligibility or delivery is payment |
| Driver | 15–20 minutes | Understand approval boundary and own assignment; record actual next event | E only with approved synthetic profile; identify ONB01 in fresh registration | Accepting without confirmation, skipping status, assuming GPS/earnings |
| Administrator | 20–30 minutes | Review targets, confirm supported decisions, inspect audit and escalate | F plus one duplicate-decision conflict | Approving an absent profile, treating Coming soon reports as available, generic ledger correction |

Durations are proposed, not measured. Facilitator should ask each participant to
explain the outcome in their own words; assistance should be logged separately
from independent task completion. Do not certify understanding solely by attendance.

## Shared synthetic preparation and safety

Use an explicitly approved isolated demonstration environment with clearly marked
synthetic actors/business/products and no external messaging/payment integrations.
The existing automated fixtures use lankapex_test_db with identity/rollback guards;
they do not provide persistent demo accounts. A persistent browser demo needs a
separately verified synthetic setup and reviewed cleanup process. Do not reset,
copy or write real data to make a demo possible, and do not repurpose this database
for unrestricted migration verification. No fixture command or database write is
executed by this document.

Record case ID, roles, preconditions, expected vs actual, status, facilitator
assistance, redacted evidence reference and related defect ID. Start every exercise
**NOT RUN**. A screenshot or learner action must be real before PASS is assigned.
Use fresh request intentions and avoid reusing the same account across unrelated
calculations. Exclude reversed entries using the authoritative ledger rules.

## A. CreditSale

Preconditions: approved synthetic shop, active authorized Customer credit account
with limit LKR 1,000.00, zero effective balance, two separate role logins where
needed. Scenario numbers are invented demonstration inputs, not observed results.

1. Owner opens **Credit Sales**, selects the correct business/Customer and reviews
   available credit. Enter **LKR 125.25**, review, then **Record Credit Sale** once.
2. Read the confirmed reference, exact amount and resulting balance. Open authorized
   history/statement and compare the Customer's own view.
3. Discuss a double-click/uncertain response without creating another intent.

Expected if executed successfully: one effective CreditSale, outstanding 125.25,
available credit 874.75; statement and both authorized views agree. Current status:
**NOT RUN**. Related automated coverage: Step 18 UAT/credit-sale suites.

## B. Partial then full repayment

Preconditions: the exact A account/confirmed debt, no other activity. No actual
money is exchanged; facilitator states that repayment method is manually recorded.

1. Owner opens **Repayments**, checks the Customer and records **LKR 50.10**.
2. Review the confirmed receipt/history and Customer statement. Explain that a
   same-request replay should confirm the original, not record a second repayment.
3. Optionally demonstrate **Full Payment** for the remaining debt.

Expected after partial: effective sales 125.25, repayments 50.10, outstanding
75.15, available credit 924.85. After the optional full 75.15: outstanding 0.00,
repayments total 125.25; account need not close and unrelated orders are unchanged.
Current status: **NOT RUN**. A mismatch stops the exercise; no manual repair.

## C. Cash order

Preconditions: separate synthetic published product priced LKR 125.25, two units,
approved business and Customer; quote succeeds. Keep separate from A/B ledger.

Customer uses **Explore Shops → Add to Cart → Shopping Cart → Checkout**, reviews
two units and selects **Cash — offline, unpaid**, then **Place Order**. Owner opens
**Orders**, reviews and processes only permitted actions. Customer opens **My Orders**.

Expected: order total 250.50, one order per intent, no CreditSale/debt, payment
unpaid, no automatic DeliveryRequest. Order progress is not proof of collected
cash. Current status: **NOT RUN**.

## D. Credit order and decision

Preconditions: a separate active authorized credit account, limit 1,000.00 and
zero balance; same 250.50 cart. Do not combine this with A/B account totals.

Customer selects eligible **Credit**, submits and reads the pending status. Owner
opens **Orders**, reviews target and amount, then **Approve Credit**. Review the
confirmed entry and Customer statement. Use a separate new order to demonstrate
rejection rather than trying to reverse an approved order decision.

Expected: pending creates no debt; approved intent creates exactly one 250.50
CreditSale and outstanding 250.50. Duplicate approval cannot post another sale;
rejected order creates none. Credit payment state posted is not repayment.
Current status: **NOT RUN**.

## E. Order-to-delivery coordination

Preconditions: eligible processed order and legitimately approved synthetic Driver
profile/vehicle, plus unrelated Driver for conflict discussion. Step 18.5 adds
first-time submission for pending Admin review; full browser onboarding still
needs acceptance. Fixture preparation must not be counted as browser evidence.

Owner uses **Request Delivery → Confirm Request Delivery**, reviews the linked
record; Driver opens **Available Jobs**, reviews, accepts and verifies **My
Deliveries**. Record **Confirm Pickup → Start Delivery → Mark Delivered → Confirm
Delivered** as each synthetic event is observed. Customer/Owner refresh tracking
and inspect in-app notices. Review what to do if another Driver wins acceptance.

Expected: one linked request/assignment, permitted recorded statuses/timestamps,
correct recipient privacy, delivered history, no financial snapshot change, no
cash payment confirmation or credit repayment. No GPS/ETA is demonstrated.
If operational pickup/contact information is insufficient, stop and log it rather
than inventing an address or proceeding with a real delivery. **NOT RUN**.

## F. Administrator reviews

Preconditions: trusted authorized synthetic Admin; pending business with active
Owner; already submitted pending Driver profile with valid paired vehicle fields.
Use the new Driver Dashboard application form before this review exercise when
testing first-time onboarding; submission does not approve the profile.

Open **Delivery Drivers**, inspect and confirm an allowed approve/reject action.
Use **Business Management** for a pending business review. Inspect the resulting
status, supported recent activity/audit evidence and recipient notification.
Refresh after a duplicate/competing decision; do not overwrite it. Use separate
pending records for approval and rejection practice.

Expected: one valid decision/audit/notice per reviewed target; no ledger changes.
No nonexistent application may be approved. Reports/full Activity exercise remains
**BLOCKED**; supported review demonstration itself is **NOT RUN**.

## Completion and frequently asked questions

Facilitator records actual outcomes, discrepancies and unexecuted steps using the
[feedback templates](day18-feedback-template.md). Ask: Which record confirms
posting? What do pending/unpaid/posted mean? What happens after timeout? Who can
approve? Can delivery change a balance? What data should never enter a bug report?
Refer uncertain answers to the role guide, then repeat a safe synthetic task.

Never substitute scripted expected numbers for actual readings. These exercises
are preparation only; no attendance, completion rate or learner feedback exists yet.
