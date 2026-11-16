# Pilot go/no-go, financial safety, privacy and exit review

Prepared 2026-11-07, Asia/Colombo. **Current decision: NO-GO for live pilot.**
The package is planning only. No launch approval has been received. Completing
documents, passing a build or API tests does not authorize recruitment, real-data
collection, live credit posting, infrastructure changes or deployment.
AI Summary is excluded and is not a blocker.

## Mandatory entry gates

Current statuses are based on repository evidence, not a newly executed pilot.
PASS requires the named evidence; an unchecked/unknown prerequisite cannot be
treated as met. Explicitly reducing feature scope must not waive integrity,
security, privacy, migration/recovery or support gates.

| Gate | Current status | Required evidence / accountable role |
| --- | --- | --- |
| No unresolved critical finance/security defect | PARTIAL | No new critical defect demonstrated in executed suites; security/finance reviewers must assess open risks and approve residual scope |
| Core four-role user journeys | BLOCKED | Step 18.5 adds tested Driver profile submission; verify browser onboarding and all role journeys with recorded expected/actuals before closing full acceptance; QA/engineering |
| Financial workflows reconcile | PARTIAL | Automated synthetic cases pass; complete observed role workflows and authorized reconciliation review; finance/QA |
| Ordering/delivery operations | PARTIAL | Existing API/race/lifecycle cases pass; browser and actual safe pickup/contact/operational arrangements need review; operations/QA |
| Admin scope | PARTIAL | Supported management/audit API pass; reports/full Activity incomplete; implement/test or explicitly exclude with approved manual evaluation process |
| Frontend validation | FAIL | Resolve 8 lint errors/1 warning; tests/build rerun after fixes; engineering/QA |
| Production environment/runtime/security | NOT VERIFIED | Exact domains, TLS, secrets, CORS, ingress/proxy, advisory/Linux/runtime checks, verified shared/edge throttling; security/release owner |
| Isolated migration execution | **BLOCKED** | DBA creates/grants separate empty target; verify identity/access/emptiness then approved guarded migration-chain execution; database/release owner |
| Backup and recovery | NOT VERIFIED | Approved isolated backup/restore rehearsal, integrity/provenance and financial reconciliation, measured recovery expectations; database/finance owner |
| Health/monitoring/rollback | PARTIAL | Local liveness/readiness/runbook exist; actual monitoring, alerts, operator coverage, compatible known-good artifacts and incident rehearsal unverified; operations |
| Devices/accessibility | NOT VERIFIED | Required browser/viewport/keyboard/assistive-technology checks below; QA |
| Privacy/consent and secure storage | NOT VERIFIED | Approved notices/purpose/access/retention/withdrawal process, formal privacy/legal review as needed; privacy/decision owner |
| Support responsibilities | NOT ASSIGNED | Real accountable roles, backup, approved intake/update process and hours; decision owner |
| Explicit live launch approval | NOT RECEIVED | Recorded environment/build/schema/scope/cohort, evidence and accepted risks; authorized decision owner |

Migration target `lankapex_migration_verify_20261107` previously failed CREATE due
to MySQL permissions. Preserve **BLOCKED**, not PASSED, until actual new evidence.
Do not retry with elevated privileges, request an administrator password, reset
lankapex_db/lankapex_test_db or substitute the synthetic test DB. Follow the DBA
template and guardrails in [database operations](day17-database-operations.md).
This task neither creates the target nor runs any migration/backup/restore.

## Device/browser acceptance plan

These are candidate environments, not certified supported combinations. No browser
was available during Day 18 UAT and no actual compatibility results exist.

| Candidate environment | Proposed review | Current evidence |
| --- | --- | --- |
| Android / Chrome | Touch, amounts/input keyboard, cart, Driver actions, retry after network loss | NOT RUN; version/device to be recorded |
| iPhone / Safari where available | Dialog/navigation/focus, statement download, checkout/status | NOT RUN; version/device to be recorded |
| Desktop Chrome | Complete all four role journeys and keyboard navigation | NOT RUN |
| Desktop Edge | Core roles, dialogs, history/download/retry | NOT RUN |
| Tablet browser(s) | Sidebar, tables/cards, approvals and status actions | NOT RUN; select actual OS/browser later |

At 375/768/1024/1366/1536 px record width, actual browser/OS/version, task ID,
expected/actual outcome and evidence. Emulation helps layout testing but does not
certify real device behavior. Check no page overflow or hidden actions, readable
LKR amounts, tap targets, labels, error/loading announcements, logical keyboard
focus, confirmation focus return and measured contrast. Existing responsive CSS
and server-render tests do not establish these results. Reuse manual cases in
[18.2](day18-shop-customer-uat.md) and [18.3](day18-driver-admin-uat.md).

## Financial reconciliation procedure — future authorized operation

No real records are processed now. Before any future live pilot, agree the
authorized scope, cutoff/time basis, reviewer access, baseline/statement policy
and private evidence storage. Generic Admin management must not be expanded into
unrestricted financial access for convenience.

1. Select the exact business/Customer/credit account and period. Confirm identity
   through authorized records. Record a restricted coded reference, opening
   effective balance and cutoff; include all in-scope zero-activity accounts.
2. Read authoritative effective ledger entries using existing reversal semantics:
   original credit_sale/repayment entries referenced by reversal are excluded;
   reversal rows are not treated as additional sales/repayments. Do not sum raw
   history blindly or modify posted entries. Use exact Decimal amounts.
3. Compare effective CreditSale and Repayment totals, opening/closing balance and
   authorized Shop Owner and Customer statements under the same period/time basis.
   For the full effective history, balance = effective sales minus repayments;
   outstanding = max(balance, 0), advance = max(-balance, 0), available credit =
   max(limit minus outstanding, 0). For a period, reconcile opening balance plus
   its effective net movement to closing. Do not net across accounts or let an
   advance inflate the permitted credit limit. This describes existing
   ledger_service rules; it does not implement replacement calculations.
4. Match approved credit orders to exactly one linked sale. Pending/rejected credit
   and cash orders must create no credit debt. Inspect order price snapshots;
   product edits must not rewrite them. Confirm delivery/Admin operations have no
   ledger/payment effect. Posted credit is debt, not a collected repayment.
5. Check confirmed intent/reference/idempotency linkage for duplicate sales and
   repayments. Same-intent replay should return the original result. Repeated
   amounts alone do not prove duplicates; investigate references and context.
6. Compare receipts and the Shop Owner's approved record to authorized statement
   results. Document cutoff/date/timezone/reversal limitations; aggregate totals
   alone can hide customer-account mismatches. Never label order totals as revenue
   or assert cash/card/bank funds were electronically verified.
7. Record every mismatch/uncertain write as an exception, pause affected workflow,
   preserve safe references and follow [incident escalation](day18-feedback-template.md).
   No manual SQL/balance adjustment, compensating fake sale/payment, destructive
   migration or blanket retry is permitted. Engineering/finance reviewers must
   investigate and approve a tested correction through supported policy.
8. Re-run relevant integrity/regression checks and the account comparison after a
   correction, obtain reviewer sign-off, then record the authorized resume decision.
   At daily/final review, report compared/due accounts, exact matches, outstanding
   exceptions and who verified them. An unresolved mismatch blocks live expansion.

Blank restricted reconciliation register (no data collected):

| Review ID | Business/account code | Period/cutoff/time basis | Opening effective balance | Effective sales | Effective repayments | Closing/outstanding/advance | Owner/Customer statement agree? | Intent/order duplicate check | Exception ID | Reviewer/date/status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

Large interactive accounts may hit existing read limits; a failed/bounded response
is not a complete reconciliation. Escalate for an authorized reviewed method;
never treat a truncated or unavailable amount as zero. Use
[database safety](day17-database-safety-review.md) and
[operations](day17-database-operations.md) for future integrity/restore controls.

## Privacy, consent and data-handling preparation

This is an operational checklist, **not certified legal compliance or legal advice**.
Before collecting real information, the designated owner must obtain a formal
privacy/legal review appropriate to purpose, financial records and participant
rights. No legal retention period or compliance status is asserted here.

- Define collection purpose, essential fields, responsible operator and approved
  recipients. Explain voluntary pilot participation, limitations, support route,
  intended uses of feedback and withdrawal process before consent.
- Use minimum necessary account data for approved workflows. Keep feedback coded
  and optional; do not request identity documents, broad financial histories or
  private addresses merely to measure usability. Handle any necessary delivery
  logistics only through an explicitly reviewed safe operational process.
- Assign role-based least-privilege access and individual accounts; no credential
  sharing. Protect uploads/downloads/screenshots/logs and any recontact mapping
  with restricted access and approved storage; no public repository or group chat
  for statements, tokens, credentials or raw financial payloads.
- Propose for review: de-identified working feedback kept during the four-week
  evaluation, review/redact/delete or anonymize unnecessary raw feedback within
  30 days after evaluation. This is a **proposed operational target**, not an
  adopted/legal retention policy. No data is deleted by this plan.
- Establish separate legally/operationally approved retention for financial,
  audit, consent and incident records before launch; do not use the feedback
  target to delete mandatory records or erase transaction history.
- Define who receives withdrawal/access/deletion requests, privately verifies
  identity without asking for passwords, separates stopping participation from
  record obligations, assesses required retained records and communicates the
  decision. There is no certified self-service deletion endpoint or guaranteed
  immediate financial-record erasure. Apply only authorized supported procedures.
- Assign incident escalation, evidence restrictions, participant communications
  and any required external notifications to designated reviewers. No current
  support phone, staff member, legal deadline or external channel is invented.
- Confirm meaningful training/consent communication for the selected participants;
  current language preferences do not guarantee Tamil/Sinhala UI translations.

## Go/no-go decision record — blank, not approval

```text
Review date/time and decision owner:
Environment / exact build artifact or commit / schema revision:
Approved candidate feature scope and explicit exclusions:
Proposed cohort and observation period:
Gate evidence references, verifier and verification date:
Open defects, severity, affected workflows and accepted limitations:
Financial/security/privacy/database/recovery reviewer decisions:
Support roles, coverage, private channel and next review checkpoint:
Decision: GO / NO-GO / limited synthetic rehearsal only
Reason and conditions (no bypass of mandatory safety gates):
Explicit approval reference, if any:
Next review / stop or rollback decision authority:
```

Current record: **NO-GO**, no approval reference, no deployment environment or start
date approved. A single approved document or proposed metric cannot fill these fields.

## Exit/evaluation criteria

At the end of the authorized observation period, account for every planned task,
failed/blocked attempt, feedback nonresponse and metric denominator. Finish exact
financial reconciliation and resolve/retest critical/high defects affecting the
agreed scope. Review feedback, prioritize usability findings, document operational
incidents/lessons and prepare next-release scope with owners and evidence.

- **Expand:** only after entry gates remain satisfied, zero unresolved financial/
  security integrity incidents, exact reconciliation, proposed targets assessed,
  device/operations confidence demonstrated and explicit expansion approval.
- **Extend:** objectives/response sample not yet sufficient but safety gates remain
  satisfied; authorize a bounded extension with revised tasks/date and review point.
- **Pause:** integrity, privacy, recovery or core workflow uncertainty; stop affected
  operations/expansion, preserve evidence and investigate before restart.
- **Stop:** unacceptable residual risk, unresolved core defect or inability to
  operate safely; protect/retain records under approved policy, support affected
  participants and document closure. No automatic destructive cleanup or restore.

Do not call the pilot successful before it runs. Step 18.5 may review this package,
test evidence and Git scope; it does not automatically authorize a live pilot,
deployment, recruitment, database operation or push.
