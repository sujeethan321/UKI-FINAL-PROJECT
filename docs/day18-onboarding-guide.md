# LankaPex role guides — pilot draft

Prepared 2026-11-07. **For future authorized training only.** The pilot has not
started. Current launch status is [NO-GO](day18-pilot-go-no-go.md).
Do not enter real customer or financial information during preparation. Use
approved synthetic demonstrations; these instructions do not create accounts.
AI Summary remains deferred and is not part of onboarding or pilot training.

Use your own authorized account and the common Login page. Your stored role
determines the dashboard. Never share passwords/tokens or choose an Admin role
through public registration. Password guidance is 12–128 characters. Keep screen
recordings and screenshots free of credentials and customer financial details.

## Shop Owner

1. Select **Shop Owner** on registration, provide the required fields and register.
   Log in. Registration alone does not approve a business.
2. On **Dashboard**, follow **Register Your Business** if no business is linked.
   Submit actual required business fields only in a separately authorized pilot.
   The business remains pending until an authorized Admin reviews it. A rejection
   or pending status is not permission to record restricted business transactions.
3. After approval, select the intended business and check the name/status before
   using **Customers**, **Credit Sales**, **Repayments** or **Shop & Products**.
4. In **Customers**, use **Add Customer** for the supported business-scoped
   relationship. Search for the existing Customer first. Review customer details
   and authorized credit-account controls; do not assume matching names/phone
   grant account access. If linking is unclear, ask the authorized operator rather
   than creating another record. Set limits/terms only under existing policy.
5. In **Credit Sales**, select the Customer, review the account/available credit,
   enter the LKR amount and optional notes, then use **Record Credit Sale**.
   Check the confirmed reference, amount and new outstanding/available credit.
   A pending request or error is not a confirmed sale.
6. In **Repayments**, select the correct Customer, review debt, enter a partial
   amount or use **Full Payment**. Choose the supported manually recorded method
   and optional reference; use **Record Repayment** and check the receipt/history.
   Card/bank selections record a method; they do not electronically verify funds.
   Do not record money that has not been appropriately verified under the pilot's
   approved operating process. Repayment must respect existing balance rules.
7. View the Customer's history and statement controls in the supported financial
   pages. Choose the intended period, check business/customer identity and LKR
   totals, and handle downloads privately. Do not send another Customer's statement.
8. In **Shop & Products**, manage categories, product price, publication and
   availability using the shown actions. Draft/unavailable products are not the
   same as public available products. Editing current prices does not change old
   order item snapshots. Image upload is not promised.
9. In **Orders**, open the intended order and review its items, price snapshots,
   payment method and separate order/payment status. For eligible credit orders,
   use **Approve Credit** or **Reject Order** only after review. Approval creates
   the credit sale once; pending/rejected credit creates no debt. Cash is not
   automatically paid. Use **Process Order** and permitted later actions only.
10. On an eligible order's details, use **Request Delivery**, enter supported
    pickup/delivery areas and **Confirm Request Delivery**. Check the recorded
    linked request. Delivery is not created just by placing an order. Follow
    **View Delivery** or **Deliveries** to inspect recorded assignment/progress.
11. Review **Notifications** and their linked resources. A notice is a prompt to
    inspect the current record, not proof an older screen is up to date.

Reports/Settings marked planned are not available pilot features. If a record is
outside your business, stop and report the access issue; do not retry with other IDs.

## Customer

1. Select **Customer**, register and log in. Registration does not automatically
   grant a credit account or link you to every business.
2. Use **Explore Shops** for general approved shop discovery and catalogue search.
   **My Shops** shows authorized linked credit relationships; an empty My Shops
   list does not mean the general catalogue has no shops.
3. Open an eligible shop/product and use **Add to Cart** where available. In
   **Shopping Cart**, review quantities, remove items if needed and check the
   estimated total. Each order is for one shop. The server confirms current
   availability and prices; do not assume an old quote guarantees a price.
4. Open **Checkout**. Choose **Cash — offline, unpaid** or eligible **Credit —
   requires Shop Owner approval**. Read the guidance, then **Place Order**.
   Cash selection is not payment confirmation. Credit submission creates no debt;
   the eligible Shop Owner must approve it before a CreditSale is posted.
5. In **My Orders**, check the confirmed order reference, items/total and statuses.
   An order can be processing/delivered while payment is still unpaid or credit
   is still outstanding. Do not pay again solely because an order status changed.
6. In **My Shops** or **My Credit**, open your authorized credit account. Use
   **Transactions** and **Credit Statement**/the shown statement action to review
   sales, repayments and balance for the correct period. Ask the shop to resolve
   mismatches; you cannot change posted balances yourself.
7. Open an order's linked delivery section for recorded assignment/history and
   refresh when needed. Unlinked orders have no requested delivery yet. Tracking
   is recorded status, not GPS/ETA. Delivered does not settle credit or cash.
8. Read **Notifications** and inspect the linked current resource. On a shared
   device, log out and keep downloaded statements private.

## Delivery Driver — first-time application added in Step 18.5

Step 18.5 adds **Submit Driver application** on Dashboard for a **Not submitted**
account. Enter **Vehicle type** and **Registration reference** (single line,
at most 50 characters each), then **Submit for review**. Check **Pending review**
after refresh. Admin review remains separate; submission does not verify identity
or grant job access. This first-time form cannot replace an existing profile.
If submission conflicts or is uncertain, use **Refresh profile** before retrying.
API/controller tests cover this fix for ONB01; browser acceptance is still pending.
Do not manually edit databases, reuse another Driver's account or weaken approval.

The remaining operational instructions apply only when a valid profile with
stored vehicle type/registration has already been legitimately provided and
explicitly approved under an authorized process:

1. Check **Dashboard** status and **Profile** (dashboard section). Pending review,
   rejected, suspended or incomplete vehicle information prevents job acceptance.
   Stored details/approval do not claim automatic identity verification.
2. Open **Available Jobs**, refresh and review the supported shop/pickup/delivery
   area information. Exact customer contacts/addresses, operational instructions
   and vehicle-matching requirements are not stored in this delivery record.
   Do not infer missing logistics or accept an unsuitable task merely to progress
   a pilot exercise. A safe authorized operational arrangement is a launch gate.
3. Use the shown accept action for an eligible job. Wait for confirmation. Another
   Driver may accept first; a conflict is not your assignment. Do not assume a
   network timeout means acceptance failed.
4. Open **My Deliveries** and its **Delivery Details**. For the assigned job use
   **Confirm Pickup**, then **Start Delivery** for in-transit, then **Mark Delivered**
   and **Confirm Delivered** only after the actual approved exercise event occurs.
   Follow the server's permitted next action; do not skip statuses or fabricate times.
5. Use **Delivery History** for delivered/cancelled records and **Notifications**
   for supported review/assignment/cancellation messages. No general new-job
   broadcast, automatic assignment, guaranteed earnings, live GPS or ETA is promised.
6. If cancellation is needed, report it through the approved support process.
   There is no general public Driver cancellation override. Do not mark delivered
   just to remove a job. Refresh uncertain updates and check recorded state before
   retrying the same action. No delivery action collects money or repays credit.

## Platform Administrator operations

Use an individually authorized Admin account supplied by a separately approved
operator process. There is no public Admin registration. This guide creates no
credentials, invitation or Admin account.

1. Log in and open **Dashboard**. Check actual pending business/Driver counts and
   section-specific errors; unavailable is not zero. Confirm the environment before
   actions. Keep sign-in credentials and review notes out of feedback logs.
2. Use **Shop Owners** and **Customers** to search/filter/page and review supported
   details. Owner business associations are available where authorized. Generic
   account management is not access to full credit histories or direct balance edits.
3. In **Delivery Drivers**, open a genuinely pending application; review stored
   vehicle information and allowed actions. Confirm approve/reject with the shown
   optional note. A conflict requires refreshing the target, not overwriting the
   prior decision. A not-submitted account is not reviewable; see ONB01 above.
4. In **Business Management**, review the pending business and active Owner
   association. Confirm the supported approve/reject decision. Do not approve your
   own business using a Shop Owner identity or bypass a missing active owner.
5. Use supported suspend/reactivate controls with the required reason. Existing
   active jobs/orders/last-owner safeguards may block suspension. Admin targets
   are excluded from generic account management; no self/last-Admin removal is
   provided. Reactivation restores access, not automatic business/Driver approval.
6. Review **Recent Administrative Activity** on Dashboard and authorized audit/API
   history through existing tooling. Full Activity investigation UI and **Platform
   Reports** are incomplete. Do not instruct participants to export a report or
   use date-filtered metrics that do not exist; use the restricted manual templates
   for pilot evaluation after approval.
7. Review **Notifications**. Record participant issues using the
   [incident template](day18-feedback-template.md), route them to assigned roles,
   and follow the stop/reconcile rules. No generic Admin operation repairs ledger
   balances, and no audit edit/delete workflow is provided.

## Connectivity and common questions

- **Can I work offline?** Live backend operations need network access. Offline
  synchronization is not implemented or certified. A browser's cached screen is
  not confirmation that a transaction posted.
- **The request timed out; should I submit another?** First review the exact
  Customer ledger/order/assignment reference. Existing financial workflows support
  same-intent retries with saved request keys. Use the displayed same-request retry
  when appropriate; do not clear storage/start a new intent to force success.
- **A warning says the result is uncertain.** Keep the scope, amount and details
  unchanged; review recorded state. If you cannot confirm it, stop and ask the
  approved support operator. Do not create a second payment or sale.
- **The Customer balance differs.** Stop the affected financial workflow, preserve
  a redacted reference and request reconciliation. Never manually adjust balances.
- **Cash order delivered: is it paid?** No. Recorded delivery and payment are
  different. Credit posted means debt was recorded, not repaid.
- **Preferred language?** Current preference fields do not certify Tamil/Sinhala
  translations. Arrange understandable training and document language needs
  without silently switching the app or promising a translated interface.
