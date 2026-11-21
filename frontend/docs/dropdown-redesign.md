# Dropdown audit and shared design

Counts refer to source control templates, not dynamic rows or repeated mounted
instances. The original inventory contains **58 dropdown/menu templates**:

| Kind | Original templates | Existing behavior retained |
| --- | ---: | --- |
| Native selects | 48 in 24 files | Original option JSX, values, handlers, disabled options, required/name/label/validation attributes |
| Account menus | 3 | Owner logout and its redirect; Customer/Driver profile, settings and logout |
| Notification popover | 1, reused by roles | Count, loading/error/retry, read/unread, mark-read and existing navigation |
| Product action menu | 1 | Availability, publication, archive confirmation and disabled states |
| Mobile navigation | 5 | Four role sidebars plus landing navigation; existing routes unchanged |

Admin's existing account identity/logout is additionally presented with the same
account-menu component (one new menu, no new action). Three inline disclosures
(transaction detail, reminder message, communication preference) also receive
matching visual styling; they intentionally remain inline disclosures rather
than floating menus that dismiss while a user reads/edits them.

The exact select sites and original option/control attributes are recorded in
`dropdown-audit.json`. Regression tests compare those attributes and preserve
every option and event handler, including long dynamic business/customer/product
lists, filters, forms inside modals, and legacy registration views.

## Shared components

- `Select`: native select with common surface, focus, validation and disabled
  styling. Supports native keyboard navigation/typeahead, touch and form
  submission. Uses the styled native top-layer picker where `base-select` is
  supported, and the OS picker elsewhere. No simulated change event or replacement
  value model is introduced. Long lists retain native typeahead and scrolling.
- `Popover`: controlled fixed panel in the native top layer (body portal fallback),
  with viewport clamping/flipping, resize/scroll repositioning and bounded scrolling.
- `Dropdown`: action menu trigger, expanded chevron and popup semantics; arrow,
  Home/End, typeahead, Tab, Escape, outside-pointer/focus dismissal and cleanup.
- `AccountMenu`: existing user information, role-specific existing actions,
  icons and separated logout. It does not implement account/business switching.
- `MobileNavigation`: native modal dialog with native focus containment and
  restoration, Escape and backdrop dismissal, responsive close and shared styles.

CSS includes 12–16px surfaces, brand focus/selected states, selected option
checkmarks in styled native pickers, 160ms animations and reduced-motion/forced
color overrides. Menu widths remain contextual (notifications 384px maximum,
account/action menus 260px maximum, selects retain their caller's sizing).

## Scope

Only frontend components, styles, navigation presentation and tests changed.
API services, request payloads, authentication/role rules, source translations,
backend, schema, financial/order/delivery logic and environment files are untouched.

## Verification

New tests cover original select options/handlers, native form attributes,
disabled states, multilingual labels, popup semantics, focus/keyboard/dismissal
logic, positioning and event cleanup. Existing frontend behavior tests and a
production build are also run. Production validation uses a temporary process-only
HTTPS placeholder API URL; it does not change .env or contact that endpoint.

Browser automation reported no connected browser or native app. Live desktop,
mobile, touch, rendered overflow/clipping and browser-console QA remain to be
performed on the running app. Older browsers intentionally retain system-native
select picker visuals rather than a custom inaccessible listbox.

Final offline results: 966 tests passed, zero failed; scoped ESLint passed;
production build passed with the existing chunk-size warning. Live browser QA
is outstanding, so the delivery status remains PARTIAL pending that check.
