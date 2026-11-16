# Pilot feedback, issue and support templates

Prepared 2026-11-07. **Blank planning templates; no feedback collected, messages
sent or external support accounts created.** Use only after the
[launch/privacy gates](day18-pilot-go-no-go.md) authorize collection.
AI Summary remains deferred; do not solicit AI-feature test results or treat its
absence as a pilot defect.

## Optional participant questionnaire

Use a participant code and role, not a full name/email/phone. Explain the purpose,
voluntary nature, intended audience and approved retention before requesting a
response. Separate any necessary recontact mapping into restricted storage.
Do not ask participants to paste passwords, tokens, account statements, customer
names, exact private delivery addresses or financial payloads into feedback.

Rate only tasks attempted: **1 very difficult/unclear, 2 difficult, 3 neutral,
4 easy/clear, 5 very easy/clear**; N/A for not attempted/unsupported. Record task
completion and facilitator assistance separately; a rating is not a pass result.

| Question | Rating 1–5 or N/A | Optional short explanation |
| --- | --- | --- |
| How easy was registration and understanding your next step? | | |
| How clear was navigation to the task you needed? | | |
| How easy was recording/reviewing a CreditSale, if applicable? | | |
| How easy was recording/reviewing a repayment and receipt? | | |
| How clear were your statement and outstanding balance? | | |
| How easy was shopping/cart/checkout, if attempted? | | |
| How clear were pending credit approval and order/payment statuses? | | |
| How clear were job acceptance and recorded delivery progress? | | |
| How useful/clear were notifications and their links? | | |
| How usable was the app on your device? | | |

Overall confidence: **1 no confidence to 5 very confident**, or N/A: ______.
Use this specific item for the satisfaction metric; do not mix rating scales.

Open questions:

- What was difficult? What prevented you from completing a task?
- What worked well? What would you improve first?
- Would you use LankaPex regularly? Why, why not, or what would need to change?
- What language/accessibility or connectivity support would help? Avoid health
  diagnoses or other unnecessary sensitive information.

## Blank feedback and task registers

Controlled feedback register (no real rows created here):

| Feedback ID | Date/time + offset | Participant code/role | Feature/UAT ID | Rating/N/A | Summary (redacted) | Severity/priority | Proposed action | Responsible role | Status | Linked issue |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

Suggested IDs `FB-<sequence>`; states New → Triaged → Planned/In progress →
Verified/Deferred → Closed. Record why a request was deferred. Keep severity
(impact) separate from priority (ordering), and record accessibility needs without
unnecessary personal detail. Roles are placeholders until assigned.

Manual task/metric observation register:

| Observation ID | Participant code/role | Environment/build | Planned task ID | Due/cutoff | Started/completed time | Independent/assisted | Expected outcome | Actual outcome | PASS/FAIL/BLOCKED/NOT RUN | Redacted evidence | Issue ID |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

Freeze planned cohort/task counts before measuring. Record failures and blocked
attempts; no silent deletion to improve rates. N/A and excluded cases require a
reason. Pilot metrics are manual unless a supported data source is explicitly
verified; no new platform analytics or reporting feature is implied.

## Bug/incident report template

Copy this blank block into an approved access-controlled tracker; no tracker or
external account is provisioned by this package.

```text
Issue ID: ISSUE-<sequence>
Reported at (Asia/Colombo offset, include UTC if available):
Role / coded reporter / optional separately protected recontact reference:
Feature / UAT ID / synthetic or separately authorized pilot environment:
Build identifier / device / browser and version / viewport:
Preconditions (redacted):
Steps to reproduce:
Expected result:
Actual result:
First occurrence / frequency / known scope (unknown if not established):
Severity / priority and reason:
Workflow stopped or containment taken:
Redacted evidence reference / server request ID if available:
Assigned responsible role / reviewer / next update checkpoint:
Root cause (unknown until established):
Fix / regression test / reconciliation reference:
Status / verified by / closure date and participant update reference:
```

Never include passwords, full JWTs, database URLs/credentials, private notes or
complete financial payloads. Screenshots/logs must be reviewed and redacted before
support sharing. Preserve the original restricted evidence separately if needed;
ordinary feedback viewers should not gain access to raw financial records.

## Severity and escalation rules — proposed operating process

| Severity | Examples | Immediate handling | Required before resuming |
| --- | --- | --- | --- |
| CRITICAL | Unexplained wrong balances, unauthorized financial access, data loss, serious privacy breach | Stop affected writes/access and pilot expansion; privately escalate to security/finance/engineering and decision owner | Scope established, tested remedy, authorized reconciliation and incident-owner approval |
| HIGH | Duplicate sale/repayment, broken checkout, wrong approval/assignment, missing core onboarding | Stop affected task/cohort; preserve references; engineering/operations review before retry | Reproduction addressed or explicitly limited scope approved; regression and relevant reconciliation pass |
| MEDIUM | Important usability/noncritical workflow failure | Log/triage; support helps only through existing safe workflow | Verified targeted fix or clearly documented accepted limitation |
| LOW | Minor visual/copy problem | Record and prioritize for next reviewed change | Review resolution; no false financial confirmation introduced |

If severity or financial outcome is uncertain, treat the affected workflow as
unsafe until reviewed. Never delete/modify ledger rows, fabricate repayment,
force assignment, run migrations/restores, disable checks or share credentials
as a support workaround. A duplicate financial incident is at least HIGH; any
uncertain balance/privacy impact escalates to CRITICAL.

## Support ownership and lifecycle

Before launch the decision owner must assign actual people, a private intake
channel, operating hours, backup coverage and realistic response/update targets.
None is assumed here. Use generic accountable roles:

- Support coordinator: intake, redaction, acknowledgement, issue ID and status.
- QA/engineering reviewer: reproduce safely in a synthetic environment, identify
  root cause, propose minimal fix and run regression checks.
- Finance reviewer: compare authorized ledger/statement/reference evidence; do not
  grant a generic Admin broad balance-edit permissions.
- Security reviewer: privacy/access incidents, containment and evidence access.
- Operations/decision owner: pause/stop/restart decisions and participant updates.

Proposed flow: receive through the future approved channel → acknowledge and
sanitize → classify and assign → contain urgent impact → reproduce/investigate →
test fix → reconcile affected financial/operational records → independent review →
authorized restart → confirm resolution with affected participant through the
approved channel → close and record lessons. Do not promise a resolution deadline
before staffing is assigned. Do not send any of these updates now.

Keep a visible next-update checkpoint and owner for each open incident. Closure
requires expected/actual verification, regression evidence, residual limitations,
reconciliation where applicable and decision-owner review. Reopen on recurrence.
Weekly de-identified lessons should capture root cause and preventive action,
not participant/customer financial detail. Security communication and any required
external reporting need the designated reviewer; no legal reporting deadline is
invented by this document.
