"""razorpay Pydantic schemas.

Security contract (issue #263 / PR #373 review):
- ``RazorpayVerifyCreate`` deliberately carries **no** ``amount``. The
  verified amount/currency/method are fetched from Razorpay's own payment
  payload after the HMAC signature check — the client never decides what
  gets recorded. Its allocations (budget/on-account targeting) are
  client-supplied but their sum is re-validated server-side against the
  verified gateway amount.
- Settings never expose the key secret; the response carries a boolean
  ``has_key_secret``.
"""

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.payments.schemas import AllocationCreate


class RazorpaySettingsUpdate(BaseModel):
    key_id: str = Field(min_length=1, max_length=200)
    key_secret: str = Field(min_length=1, max_length=500)
    is_active: bool | None = None


class RazorpaySettingsResponse(BaseModel):
    key_id: str
    is_active: bool
    has_key_secret: bool


class RazorpayOrderCreate(BaseModel):
    patient_id: UUID
    amount: Decimal = Field(gt=0)


class RazorpayOrderResponse(BaseModel):
    order_id: str
    amount: int  # paise, per Razorpay convention
    currency: str
    key_id: str


class RazorpayVerifyCreate(BaseModel):
    """Payload sent by the client in the Razorpay checkout ``handler``.

    Only pointers, never money values: amount, currency and payment method
    are read from Razorpay's payment payload server-side after signature
    verification (and the allocation sum is re-checked against that
    amount). ``idempotency_key`` guards replay of the same razorpay
    payment id.
    """

    patient_id: UUID
    payment_date: date = Field(default_factory=date.today)
    razorpay_payment_id: str
    razorpay_order_id: str
    razorpay_signature: str
    allocations: list[AllocationCreate] = Field(min_length=1)
