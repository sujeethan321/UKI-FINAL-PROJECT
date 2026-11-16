# LankaPex pilot preparation plan — Day 18 Step 18.4

Prepared 2026-11-07, Asia/Colombo. **DRAFT — PLANNING ONLY; launch NO-GO.**
No participants recruited, accounts created, messages sent, personal data collected,
live credit transactions processed, database changed or deployment executed.
AI Summary is excluded and is not a pilot blocker.

## Package and audit evidence

- [Role onboarding and operations](day18-onboarding-guide.md)
- [Synthetic training exercises](day18-training-scenarios.md)
- [Questionnaire, feedback, support and incident templates](day18-feedback-template.md)
- [Launch gates, privacy preparation and exit decision](day18-pilot-go-no-go.md)

Reviewed actual routes/sidebars and registration/financial/order/delivery/Admin
implementation together with [Day 17 readiness](day17-production-readiness.md),
[18.1 UAT](day18-uat-matrix.md), [18.2 experience review](day18-shop-customer-uat.md)
and [18.3 Driver/Admin review](day18-driver-admin-uat.md). Base HEAD is `d917e4f`
on `main`; UAT describes the uncommitted working tree, not that commit alone.
No root README exists; frontend/README.md is a generic Vite template. Existing
technical/operations guides are reused through links rather than copied into a
second deployment manual. No equivalent pilot package was found.

Recorded evidence, **not rerun in this documentation step**:

| Evidence | Recorded result | Limit |
| --- | --- | --- |
| Step 18.1 full backend | 1229 passed, 1 skipped | Migration execution blocked |
| Step 18.2 selected backend | 686 passes across three runs | API tests; not browser sign-off |
| Step 18.3 selected backend + onboarding guard | 347 + 1 passed | New Driver cannot submit required profile through public workflow |
| Latest full frontend | 806 passed | Node/controller/server-rendered React contracts |
| Latest build | Passed | Nonresolving test API URL; not production configured |
| Full lint | 8 errors, 1 warning | Existing unresolved findings |
| Browser/mobile/accessibility | No browser execution | All proposed device combinations unverified |

No critical financial/security defect was demonstrated by these suites; that
does not certify absence of defects. ONB01 is a HIGH functional blocker: Driver
registration creates an account, but no public profile/vehicle submission journey
exists. Fixture-provisioned Driver operations pass. Admin Reports/full Activity
remain incomplete. Isolated migration execution is **BLOCKED** after MySQL CREATE
permission denial; restore, external throttling and live operations are unverified.

Step 18.5 supersedes the historical ONB01 implementation gap above: the Dashboard
now supports first-time authenticated vehicle submission for pending Admin review.
API/controller coverage passes; browser acceptance and all launch gates remain
open. See [final review](day18-final-uat-readiness.md) for current decisions.

## Objectives and conditional scope

Evaluate whether a small, manageable Jaffna group can complete everyday credit,
repayment, shopping and coordination tasks accurately and understand the recorded
outcomes. Measure difficulty and recovery as well as task completion. Use approved
synthetic rehearsals before any separately authorized live pilot.

| Candidate scope after gates pass | Supported capability / condition |
| --- | --- |
| Owner registration/business review | Existing registration and pending-only Admin approval; browser onboarding still to be tested |
| Customer registration/linked accounts | Existing ownership-scoped accounts; registration does not grant arbitrary shop credit |
| Credit sales/repayments/statements | Existing Decimal ledger, manual repayment recording, receipts/statements and scoped history |
| Products/discovery/cart | Existing publication/availability/category/price/cart workflows; one shop per order |
| Cash/Credit orders and fulfilment | Server prices; pending credit needs approval; cash does not imply paid |
| Delivery request/acceptance/tracking | Linked request, atomic acceptance and recorded lifecycle; requires eligible stored Driver profile |
| Admin management and notifications | Supported user/business/Driver review, safe status changes, recent audit/API and in-app notices |
| Driver registration through approval | Step 18.5 adds first-time Dashboard vehicle submission; complete browser acceptance before activating a delivery cohort |
| Operational reports/full Activity | **Excluded from current pilot promises:** Coming soon/incomplete. Manual pilot metrics may be used after scope approval; do not pretend they are platform reports |

Out of scope: AI Summary; electronic payment gateways/verified card or bank
collection; automated SMS/WhatsApp/email; offline syncing; live GPS/ETA; guaranteed
earnings/ratings; job-to-vehicle compatibility matching; public Admin registration;
product image upload where unsupported; unsupported loan/interest/financial
products. Selecting a language preference does not promise a translated UI.

## Proposed participants and rollout

These are **planning assumptions**, not recruited people or account commitments:

| Role | Proposed count | Selection criteria |
| --- | --- | --- |
| Shop Owner | 5 | Active neighborhood retail, frequent customer credit, willing to compare records, smartphone/computer access, time for feedback |
| Customer | 20 | Familiar with participating shops, voluntary interest in credit visibility/shopping, smartphone access and ability to report difficulty |
| Delivery Driver | 3 | Appropriate available vehicle, willing to follow safe pickup/status procedures and provide feedback; onboarding gate must be closed first |
| Platform Administrator | 1 | Trusted authorized operator, understands review/account boundaries and can coordinate incidents; no shared credentials |
| Total | **29** | Counts may be reduced after review; no identities collected now |

Start in a geographically manageable Jaffna-area group selected later. No invented
addresses, delivery distances, travel times or recruited shops are supplied.
Proposed first wave: one shop/four customers; remaining four shops/16 customers
only after its reconciliation and feedback review. Activate up to three Drivers
only after onboarding and operational gates pass. Smaller scope does not waive
database, privacy, financial or security gates. Expand outside this group only
after exit review and explicit approval.

## Proposed four-week schedule

No calendar start date or events are created. Week 1 starts only after the signed
go/no-go decision authorizes the specific environment, scope and participants.
All times in future records should state Asia/Colombo and include an offset.

| Relative week | Proposed work | End-of-week review / stop condition |
| --- | --- | --- |
| 1 | Authorized account setup, consent, role training, small first-wave tasks, device/keyboard checks | Onboarding completion and support coverage; stop expansion on unresolved core access or privacy issues |
| 2 | Credit/partial/full repayment, Customer statement comparison, catalogue/cart and cash/credit orders | Daily financial reconciliation and duplicate checks; freeze affected writes on any unexplained mismatch |
| 3 | Delivery request, eligible Driver acceptance, pickup/transit/delivered, Owner/Customer refresh and notices | Confirm unique assignments, status history and no payment side effects; delivery cohort conditional on ONB01 resolution |
| 4 | Final reconciliation, feedback questionnaire, metric review, defect prioritization and exit meeting | Explicit expand/extend/stop decision; no automatic rollout |

Suggested training durations are in the [training guide](day18-training-scenarios.md).
This schedule is neither measured capacity nor a promise of feature completion.
If gates remain blocked, use the period for approved synthetic rehearsal only;
do not describe that as a live pilot or replace live metrics with test results.

## Proposed metrics and measurement definitions

**All thresholds below are PROPOSED TARGETS. There are no actual pilot results.**
Record numerator and denominator as well as a percentage. With no eligible
observations, report N/A, never 100%. Freeze the planned task/cohort denominators
before measurement; publish exclusions with reasons rather than dropping failures.
Manual tracking means an access-controlled worksheet using the templates, not a
new database model or a claim that Admin Reports exists.

| Metric | Definition / numerator | Denominator | Source and frequency | Responsible role | Proposed threshold |
| --- | --- | --- | --- | --- | --- |
| Onboarding completion | Selected participants completing the approved role onboarding checklist | All selected consented participants due to complete onboarding; include blocked attempts | Manual coded task register; daily in week 1, weekly after | Onboarding coordinator | At least 90%; Driver application must actually be submitted/reviewed, account registration alone is insufficient |
| Critical task completion | Planned critical workflow attempts reaching their defined expected outcome without workaround | All planned critical attempts due in period, including failed/blocked attempts | UAT IDs and manual observation log; daily/weekly | QA lead | At least 95%; any financial/security defect still independently stops release |
| Reconciliation accuracy | In-scope account-period comparisons with exact authorized ledger/statement agreement | Every in-scope account-period comparison due, including zero-activity accounts | Authorized account statements and restricted reconciliation register; daily and final | Finance reviewer | **100% exact**; any mismatch pauses affected workflow, no tolerance based on cohort averages |
| Duplicate financial transactions | Confirmed unintended extra posted sale/repayment entries for the same intent | All accepted financial intents (also report incident count) | Entry references/idempotency/exception review; daily | Finance reviewer / engineering | **Zero** duplicates; a single duplicate triggers escalation |
| Critical security/privacy incidents | Confirmed critical incidents | Pilot participant-days observed; always report absolute count too | Restricted incident register; continuous triage/daily review | Security reviewer | **Zero**; lack of reports is not proof of no incident |
| Expected order processing | Eligible submitted pilot orders reaching their pre-agreed valid terminal outcome | All eligible submitted pilot orders due by cutoff | Supported order history + manual cohort mapping; daily/weekly | Operations coordinator | At least 90%; show completed/rejected/cancelled separately; no submitted totals labeled collected revenue |
| Delivery valid final state | Assigned pilot deliveries reaching delivered or permitted cancelled with recorded reason/history | All assigned pilot deliveries due by cutoff | Supported delivery history + restricted manual log; daily/weekly | Delivery coordinator | At least 90%; report delivered/cancelled separately, never cancel merely to meet target |
| Satisfaction | Sum of submitted valid overall-confidence ratings (1–5) | Number of valid answered overall-confidence questions | Optional coded questionnaire; weekly/final | Feedback coordinator | Mean at least 4/5; also report response count and invited count, not fabricated nonresponses |
| Onboarding difficulty | Participants needing facilitator assistance; separately record median observed minutes | Observed onboarding attempts; report observation count | Manual task log; week 1/final | Onboarding coordinator | Baseline only; no invented time target |

Account reconciliation is per account/business; do not net one Customer's advance
against another's debt. No platform-wide credit report or hidden Customer balances
should be exposed to generic Admin management to calculate these metrics.

## Operations, evaluation and ownership

Before launch, assign people to the generic roles in this plan, including a backup
for the single proposed Admin. No current staff names, support number, SLA or
staffing availability is asserted. One person may hold multiple roles only with
explicit accountability and an independent financial/security review for incidents.
Support intake, escalation and closure are defined in the
[feedback/support templates](day18-feedback-template.md).

Daily proposed review: critical/high incidents, uncertain writes, reconciliation,
approval/assignment conflicts, account restrictions, stale records and support
backlog. Weekly: publish a de-identified metric summary and scoped improvement list.
No automatic messaging or external support account is created here.

Pilot evaluation is complete only when planned tasks and unexecuted exceptions
are accounted for, all financial comparisons finish, critical issues are resolved
and retested, feedback is reviewed, usability/operational issues are prioritized,
and a next-release recommendation is documented. Use
[exit criteria](day18-pilot-go-no-go.md) to choose expand, extend, pause or stop.
This package supports Step 18.5 review; it does not authorize launch.
