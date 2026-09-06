---
module: razorpay
last_verified_commit: 0000000
---

# razorpay — events

This module **emits no events of its own and registers no handlers**. It
records payments synchronously via `payments.workflow.record_payment`, so
the payments module's own `payment.recorded` / `payment.allocated` events
are what downstream modules (e.g. billing's budget↔invoice bridge) observe.
