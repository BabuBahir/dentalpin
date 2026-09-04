# razorpay — CHANGELOG

## Unreleased

- Initial implementation (#263, PR 1 of #365): `RazorpayAdapter`
  implementing `payment_gateways.adapters.GatewayAdapter`. UPI intent/
  checkout and cards via the Orders API (`payment_capture=1`), dynamic
  QR via the QR Codes API, and Payment Links — all through a thin
  `httpx` REST client (`client.py`, no SDK dependency, HTTP Basic Auth
  `key_id:key_secret`, same pattern as `whatsapp_kapso`/verifactu).
- Per-clinic settings (`GET`/`PUT /api/v1/razorpay/settings`): test/live
  mode, write-only `key_id`/`key_secret`/`webhook_secret` (Fernet-
  encrypted at rest, never echoed back — only `has_key_secret`/
  `has_webhook_secret`), active flag, and webhook health (last
  received/processed timestamp, last event type, last error).
- Signed public webhook (`POST /webhook/{clinic_id}`) — HMAC-SHA256
  verification against the clinic's own secret, payload parsing into
  neutral `payment_succeeded`/`payment_failed`/`payment_authorized`/
  `payment_expired`/`payment_cancelled`/`refund_completed`/
  `refund_failed`/unrecognized events, dispatched onto a row-locked
  `PaymentRequest`/`GatewayRefundRequest` in `payment_gateways`.
  Unknown clinics and unrecognized events are accept-and-ignore (200);
  a data-problem `GatewayError` is logged to webhook health and still
  answers 200; a transport/programmer error answers 500 so Razorpay
  retries.
- Frontend: `RazorpayPaymentModal` — a full replacement for `payments`'
  own `PaymentCreateModal`, mounted via the new `payments.create.modal`
  slot (India-clinic-gated; resolved directly, not through
  `<ModuleSlot>`, since it needs `v-model`/props/events the generic
  slot can't carry). Same "New payment"/"Cobrar" trigger; the panel
  adds UPI/UPI QR/Razorpay rails next to the four existing manual
  methods, an allocation table (several invoices + on-account as a
  row) in place of the single "Apply to" target, and a received/
  allocated/unallocated footer. Manual rails record instantly; gateway
  rails hand off to `PaymentRequest` polling. PhonePe has no adapter in
  this PR and is not rendered. Also `RazorpayPaymentBadge` +
  `RazorpayTransactionDetailModal` (via the `payments.list.row.meta`
  slot — audit trail, allocation, settlement, refund history, and a
  "refund via Razorpay" action), `/settings/razorpay` settings page +
  `settings.sections` card. en/es/ta locales.
- Migrations: `rzp_0001` (own Alembic branch).
- Tests: amount/method mapping (pure), webhook signature verification
  and payload parsing (pure, all event types), settings isolation/
  secret-masking/permission gating, end-to-end webhook confirmation
  (exactly one `Payment` with `method="upi"`, duplicate-delivery
  idempotency, failed-path never creates a `Payment`, refund
  completion idempotency) — all against mocked/fixture data, no live
  Razorpay credentials or network access.

### Prerequisite changes landed alongside this module

- `payments.PAYMENT_METHODS`/`PaymentMethod` gained `upi`/`netbanking`
  (see `payments/CHANGELOG.md`).
- `payments` gained one new slot consumed by this module:
  `payments.create.modal` (a full override of the modal opened by "New
  payment"/"Cobrar" on `/payments` and the patient Pagos tab; resolved
  directly via `resolveSlot`, not `<ModuleSlot>`). The badge rides the
  `payments.list.row.meta` slot that PR #370 already added (small badge
  on gateway-collected payment rows). Neither slot renders anything
  when no provider module is installed, or for a non-India clinic. `BudgetPaymentsCard`'s own
  "Cobrar" (which opens the unrelated `BudgetCollectModal`) is
  untouched and out of scope for this PR.
