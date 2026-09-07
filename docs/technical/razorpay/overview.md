---
module: razorpay
last_verified_commit: 0000000
---

# razorpay — overview

Razorpay online payments (India) as a module, gated onto the
`payments.collect.actions` slot. Refactored out of the payments module
after the PR #373 review; the payments module kept only the prerequisites
(#365): the closed-method expansion (`upi`/`netbanking`), the slot, and
`idempotency_key` support in `record_payment`.

## What it is

- **Per-clinic gateway** — each clinic configures its own Razorpay
  `key_id` / `key_secret` in Settings → Integrations. Keys are
  Fernet-encrypted at rest (`app.core.email.encryption`, same as SMTP
  passwords and whatsapp_webhook secrets).
- **Server-side money flow** — `POST /order` creates a Razorpay order with
  the clinic secret; `POST /verify` verifies the checkout HMAC signature,
  re-fetches the captured payment from Razorpay, and records it through
  `payments.workflow.record_payment`.
- **Trust boundary** — the recorded amount, currency and payment method
  come from Razorpay's captured payload, never from the browser. The
  `RazorpayVerifyCreate` schema has no `amount` field by design.
- **Idempotent** — every verify uses `idempotency_key=razorpay:<payment_id>`,
  so a replay (double callback, browser retry) returns the original payment
  instead of recording money twice.

## Method mapping

Razorpay's `payment.method` maps onto the payments **closed** method list:

| Razorpay method | Recorded `Payment.method` |
|-----------------|---------------------------|
| `upi` | `upi` |
| `netbanking` | `netbanking` |
| `card` | `card` |
| anything else (`wallet`, `emi`, …) | `other` |

`razorpay` is deliberately **not** a `PaymentMethod`; the gateway identity
is kept in `Payment.reference` (the razorpay payment id) and `notes`.

## Frontend

- `RazorpayCollectButton.vue` registers into `payments.collect.actions`
  (IN-country gated, requires a resolvable patient).
- `RazorpaySettingsPage.vue` registers under Settings → Integrations
  (`razorpay`).
- 9 locales (`razorpay.*`): en, es, fr, pt, ta, de, pl, it, hu.

## Lifecycle

`installable=True`, `auto_install=False`, `removable=True`. Own Alembic
branch `razorpay` (`rp_0001`, table `razorpay_settings`).

See the module `CLAUDE.md` for the full security contract and gotchas.
