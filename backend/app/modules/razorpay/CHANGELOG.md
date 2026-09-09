# Changelog — razorpay module

## Unreleased

- test(rebased onto main): verify-router assertions now read the
  `ErrorResponse.message` envelope (the raw FastAPI `detail` shape shipped
  before main's global HTTP exception handler) and pin the order test to an
  INR clinic so the currency assertion is stable against main's EUR clinic
  default.

- feat(#263, PR #373): Razorpay online payments module, refactored out of
  the payments module (which gained the `payments.collect.actions` slot and
  `idempotency_key` support in #365). Per-clinic `key_id`/`key_secret`
  (Fernet-encrypted) in `razorpay_settings` on its own Alembic branch.
  Order creation and verification are server-side: HMAC signature is
  verified against the clinic secret, the captured payment is re-fetched
  from Razorpay (status/order match), and the recorded amount/currency/
  method come from the gateway (mapped onto the payments closed method
  list — `razorpay` is intentionally NOT a new method). Recording goes
  through `record_payment` with `idempotency_key=razorpay:<payment_id>` so
  a replay can never double-book. Frontend registers the collect button into
  `payments.collect.actions` (IN-gated) and a Razorpay settings page under
  Settings → Integrations. 9 locales.
