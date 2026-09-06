---
module: razorpay
last_verified_commit: 0000000
---

# razorpay — permissions

Namespaced by the registry from the module's `get_permissions()`.

| Permission | Gates | Endpoints |
|------------|-------|-----------|
| `razorpay.settings.read` | View gateway credentials | `GET /api/v1/razorpay/settings` |
| `razorpay.settings.write` | Configure/rotate gateway credentials | `PUT /api/v1/razorpay/settings` |
| `razorpay.collect` | Create an order and record a verified online payment | `POST /api/v1/razorpay/order`, `POST /api/v1/razorpay/verify` |

`razorpay.collect` is granted (`collect` in `manifest.role_permissions`) to
the same roles that can record a counter payment — `dentist`, `assistant`,
`receptionist`. Settings are **admin-only** (`admin: ["*"]`): gateway
secrets are a clinic-level secret, not a clinical concern.
