# Step 190 — Multilingual foundation (Phase 1)

Scope: public landing page and reusable language selector. The application as a
whole is not yet multilingual. No automatic translation, business-data translation,
account-language update, authentication change, or backend integration was added.

## Architecture

- `frontend/src/i18n/index.js` initializes i18next/react-i18next with bundled resources.
- `locales/en.json`, `ta.json`, `si.json` contain static landing/UI strings only.
- English is the default, with English fallback for missing keys. No browser-language
  auto-detection is used; only an explicit saved selection overrides English.
- `lankapex_ui_language` is the only local-storage key accessed by this feature.
  Invalid selections and storage access errors fall back safely. JWT/session storage
  and registration `preferred_language` are independent and unchanged.
- The active language updates `<html lang>` and the landing root's `lang` attribute.
  All three languages use left-to-right layout. React renders translated text safely;
  no translation is inserted with `dangerouslySetInnerHTML`.
- `LanguageSelector` is a labelled native select with English, தமிழ், සිංහල endonyms,
  keyboard support, a visible focus ring, and a 44px minimum select target.
- Use `useTranslation()` in future screens; register new namespaces/resources as those
  screens are translated. Inject `t` into pure presentation helpers where needed.
- Collection keys such as `features.0.title` and `roles.0.items.0` follow the existing
  fixed feature/role sequence. Preserve that ordering across locales. Tests compare
  resource structure and array lengths. Routes, icon definitions, element IDs, and
  planned-feature flags stay in code, outside translation resources.
- The optional split-heading suffix is deliberately empty in English and nonempty
  in Tamil/Sinhala to preserve natural word order. Other missing translations use
  English; a key missing from all languages still needs a developer-supplied English
  default or resource entry. No missing-key network reporting is enabled.

## Coverage and preservation

Translated header/navigation, selector accessibility label, hero and image alt text,
registration actions, role badges/tagline, feature rows, timeline, role panels and
notes, editorial benefits, split heading, all six glass cards and planned badges,
FAQ questions/answers, footer links/contact/copyright, and supporting ARIA labels.
Existing images remain unchanged, including the English brand lettering in raster
logos. No new image or external font is downloaded. System fallbacks include
Nirmala UI, Latha, Iskoola Pota and generic sans-serif; installed font availability
differs by operating system.

All section IDs, URL destinations, section order, and the removed-statistics state
remain unchanged. Local-script CSS allows longer titles/actions to wrap, uses auto
header height, and places localized desktop navigation on its own row when needed.
No button color, hover behavior, card, timeline, role-selector, or split-heading
design was replaced. The selector replaces the old English-only indicator.

## Translation review required

Tamil and Sinhala copy is an implementation draft, not professionally verified.
Have native Sri Lankan speakers review the full page before release, particularly:

| English concept | Tamil draft terminology | Sinhala draft terminology |
| --- | --- | --- |
| Credit (shop credit, not an approved loan) | கடன் | ණය |
| Repayment | மீள்செலுத்தல் | ආපසු ගෙවීම |
| Outstanding balance | நிலுவைத் தொகை | හිඟ ශේෂය |
| Credit limit | கடன் வரம்பு | ණය සීමාව |
| Overdue balance (future financial screens) | காலம் கடந்த நிலுவைத் தொகை | ගෙවීම් කාලය ඉක්මවූ හිඟ ශේෂය |

The landing copy does not expose an overdue balance; do not substitute outstanding
for overdue in later screens. Review colloquial Nayam/நயம்/ණය පොත, ledger/permitted
credit, business-specific access, consent/eligibility, delivery roles, and planned
feature disclaimers. English references to supported English/Tamil reminder messages
are retained in every language; choosing Sinhala does not add Sinhala reminder support.
Existing development-stage/business claims were preserved, including planned-feature
statements; reconcile those claims only through a separately approved content task.

## Remaining untranslated screen inventory

| Area | Files/surfaces remaining |
| --- | --- |
| Authentication | `pages/auth/{LoginPage,LoginForm,LoginBrandPanel,RegisterPage,RegistrationForm}.jsx`; registration validation, API/session error utilities |
| Public QR joining | `pages/customer/JoinShop.jsx`, join-state and error messages |
| Shared authenticated navigation | `layouts/{ShopOwnerLayout,CustomerLayout,DriverLayout,AdminLayout}.jsx`; role headers/sidebars, notification bell/inbox, shared dialogs and validation/errors |
| Shop Owner | Dashboard, BusinessOnboarding, Customers, AddCustomerModal, ManageCustomerModal, Products, CreditSales, Repayments, Reports, FinancialDocuments, Notifications, ReminderCommunication, Deliveries, Settings; QR panels; workflow validation/status text |
| Customer | Dashboard, CreditAccounts, CreditAccountDetails, CreditStatement, TransactionHistory, MyShops, Catalogue, ShoppingCart, OrderHistory, Deliveries, Profile, Settings, Notifications |
| Delivery Driver | Dashboard, AvailableJobs, Deliveries, Earnings, Vehicle, Profile, Settings, Notifications |
| Admin | Dashboard, Businesses, Management, Notifications and their dialogs/status/error labels |
| Other shared/legacy components | Any duplicate legacy registration form and diagnostic UI need review before inclusion; user-entered business/product/customer names and backend records remain data, not translation keys |

Existing account `preferred_language`, reminder message language, and Tamil AI output
are domain features rather than app-wide i18n. They were not changed.

## Next phase

Translate authentication and public QR join UI first: labels, instructions, field
errors, session expiry, role cards, safe redirect notices, and accessibility text.
Preserve request payload values, role enums and routes. Then translate shared role
layouts and each authorized workflow in separate reviewed phases. Define shared
financial terminology and localized formatting before translating ledger screens;
keep authoritative Decimal strings/calculations and business data intact.

Validation uses mocked frontend tests, resource-parity checks, persisted-language
tests, English fallback tests, and offline responsive renders. No MySQL, credentials,
external AI calls, migrations, or application servers are required.
