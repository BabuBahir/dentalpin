# razorpay module

Razorpay online payments (India) via the `payments.collect.actions` slot.
The gateway is **per-clinic** (each clinic configures its own Razorpay
account in Settings) and the request flow is server-side — the browser
never sees the key secret and never dictates the recorded amount.

Issue #263 / PR #373 review (refactored out of the payments module).

## Public API

Routes mounted at `/api/v1/razorpay/`:

| Method | Path | Permission |
|---|---|---|
| GET | `/settings` | `razorpay.settings.read` |
| PUT | `/settings` | `razorpay.settings.write` |
| POST | `/order` | `razorpay.collect` |
| POST | `/verify` | `razorpay.collect` |

`GET/PUT /settings` read/write the clinic's own `key_id` + Fernet-encrypted
`key_secret` (`app.core.email.encryption`). The secret is **never** returned;
the response carries only `has_key_secret: bool`.

`POST /order` creates a Razorpay order server-side and returns
`{ order_id, amount (paise), currency, key_id }` — the key_id is the public
identifier the checkout popup needs.

`POST /verify` is the trust boundary. Body: `{ patient_id, payment_date,
razorpay_payment_id, razorpay_order_id, razorpay_signature, allocations }`.
It does **not** accept an amount: the recorded amount/currency/method come
from Razorpay's own captured payment payload.

## Dependencies

`manifest.depends = ["payments"]`. The only cross-module import is
`payments.workflow.record_payment` (allowed by `depends`) — this module
never duplicates payment logic.

## Security contract (PR #373 review — do not regress)

1. **HMAC signature verified server-side** with the clinic's key secret
   (`hmac` + `compare_digest`, stdlib — no SDK helper that could be
   drifted).
2. **Payment re-fetched from Razorpay** and asserted `status == "captured"`
   **and** `order_id` matches.
3. **Amount/currency/method from the gateway**, never from the request:
   `amount = payment.amount / 100`, `currency = payment.currency`, method
   mapped onto the payments **closed** list (`upi → upi`, `netbanking →
   netbanking`, `card → card`, anything else → `other`).
4. **Idempotency** via `idempotency_key=f"razorpay:{payment_id}"` — a replay
   of the same checkout callback returns the original Payment, never a
   double record.
5. **Per-clinic keys**: `RazorpaySettings` is keyed by `clinic_id`, every
   query filters by `ctx.clinic_id`, keys are encrypted at rest.
6. **Allocation sum re-validated** against the captured amount before
   recording.

## Permissions

`razorpay.settings.read`, `razorpay.settings.write`, `razorpay.collect`.

`collect` is granted to the same roles that can record a counter payment
(dentist / assistant / receptionist). Settings are admin-only.

## Events

None published, none consumed. Recording is synchronous via
`record_payment`, which publishes the payments module's own
`payment.recorded` / `payment.allocated` events.

## Lifecycle

- `installable=True`, `auto_install=False` (activated from Admin → Modules),
  `removable=True`.
- Own Alembic branch `razorpay` (`rp_0001`, table `razorpay_settings`).
  Round-trip uninstall drops only that table.
- `uninstall()` is default — no settings are sensitive enough to block it
  (they are per-gateway and non-fiscal).

## Tools exposed

None (`get_tools()` → `[]`). Recording stays on the HTTP trust boundary.

## Frontend

- **`payments.collect.actions` slot** — `RazorpayCollectButton.vue` renders
  only when the clinic's server-side country is `IN` and a patient is
  resolvable. It creates the order, opens the Razorpay checkout popup
  (`checkout.js` from the CDN), and forwards the callback ids + signature to
  `/verify`. On success it reloads the current route so the payments hosts
  (which only refresh on their own modal events) reconcile.
- **Settings → Integrations** — `razorpay` page (`RazorpaySettingsPage.vue`)
  with the per-clinic key id + secret (blank secret = keep the stored one).
- **i18n**: 9 locales (en, es, fr, pt, ta, de, pl, it, hu) under `razorpay.*`.
- Component names are prefixed (`RazorpayCollectButton`, `RazorpaySettingsPage`)
  because layers auto-import with `pathPrefix: false`.

## Gotchas

- **`razorpay` is NOT added to `PAYMENT_METHODS` / `PaymentMethod`.** The
  recorded method is one of the existing closed values (`upi`,
  `netbanking`, `card`, `other`); the gateway identity lives in the payment
  `reference` (the razorpay payment id) and `notes`. Do not widen the
  closed list again (PR #373's original mistake).
- **The SDK is used only for order creation + payment fetch** —
  `import razorpay` is local to `_client()`. Signature verification uses
  stdlib `hmac`, so a malformed/drifted SDK can't silently weaken it.
- **`clinic.currency` is the order currency**, but the recorded currency
  comes from Razorpay's capture. They normally agree (INR); if a clinic
  ever mismatched, the recorded Payment keeps the gateway's value.
- **Frontend must not send an amount to `/verify`.** The schema has no
  `amount` field precisely so a tampered client can't inflate the record.

## Related ADRs

- `docs/adr/0001-modular-plugin-architecture.md`
- `docs/adr/0002-per-module-alembic-branches.md`
- `docs/adr/0010-payments-as-primitive-module.md` (slot-based gateways)

## CHANGELOG

See `./CHANGELOG.md`.
