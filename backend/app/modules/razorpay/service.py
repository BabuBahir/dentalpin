"""razorpay gateway business logic.

Security-sensitive by design (issue #263 / PR #373 review): the amount,
currency and payment method recorded on a Payment are **never** taken from
the browser. After the checkout ``handler`` fires, we:

1. Verify the HMAC-SHA256 signature of ``order_id|payment_id`` with the
   clinic's key secret (stdlib ``hmac`` + ``compare_digest``).
2. Fetch the payment from Razorpay and assert ``status == "captured"`` and
   ``order_id`` matches.
3. Record the amount/currency from **Razorpay's** payload, mapped onto the
   payments closed method list, with ``idempotency_key=razorpay:<payment_id>``
   so the same checkout response can never be recorded twice.

Per-clinic keys: each clinic configures its own Razorpay account via the
settings endpoint; order creation and verification use that clinic's
decrypted secret. A clinic that has not configured the gateway gets a
``RazorpayNotConfiguredError`` (→ 400), which is also the signal the
frontend uses to hide the collect button.
"""

from __future__ import annotations

import hashlib
import hmac
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select

from app.core.email.encryption import decrypt_password, encrypt_password
from app.modules.payments.workflow import record_payment

from .models import RazorpaySettings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# Razorpay sends payment.method as one of these; map onto the payments
# module's closed list (models.PAYMENT_METHODS / schemas.PaymentMethod).
_METHOD_MAP = {
    "upi": "upi",
    "netbanking": "netbanking",
    "card": "card",
    # wallet / emi / bank_transfer / eft / nach / ... are all "other".
}


class RazorpayNotConfiguredError(RuntimeError):
    """Raised when the clinic has no active Razorpay credentials."""


class RazorpayPaymentError(RuntimeError):
    """Raised when Razorpay rejects the request or the capture is invalid."""


def _map_method(razorpay_method: str) -> str:
    return _METHOD_MAP.get(razorpay_method, "other")


class RazorpayService:
    @staticmethod
    async def get_settings(db: AsyncSession, clinic_id: UUID) -> RazorpaySettings | None:
        return (
            await db.execute(
                select(RazorpaySettings).where(RazorpaySettings.clinic_id == clinic_id)
            )
        ).scalar_one_or_none()

    @staticmethod
    async def upsert_settings(
        db: AsyncSession, clinic_id: UUID, key_id: str, key_secret: str, is_active: bool | None
    ) -> RazorpaySettings:
        settings = await RazorpayService.get_settings(db, clinic_id)
        if settings is None:
            settings = RazorpaySettings(
                clinic_id=clinic_id,
                key_id=key_id,
                key_secret_encrypted=encrypt_password(key_secret),
                is_active=True if is_active is None else is_active,
            )
            db.add(settings)
        else:
            settings.key_id = key_id
            settings.key_secret_encrypted = encrypt_password(key_secret)
            if is_active is not None:
                settings.is_active = is_active
        await db.flush()
        return settings

    @staticmethod
    def _client(settings: RazorpaySettings):
        key_id = settings.key_id.strip()
        key_secret = decrypt_password(settings.key_secret_encrypted)
        if not key_id or not key_secret:
            raise RazorpayNotConfiguredError(
                "Razorpay is not configured for this clinic (key id or secret missing)."
            )
        try:
            import razorpay  # local import: optional at boot time
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise RazorpayNotConfiguredError("The 'razorpay' package is not installed.") from exc
        return razorpay.Client(auth=(key_id, key_secret))

    @staticmethod
    async def create_order(
        db: AsyncSession,
        clinic_id: UUID,
        patient_id: UUID,
        amount: Decimal,
        clinic_currency: str,
    ) -> dict:
        """Create a Razorpay order for ``amount`` in the clinic's currency.

        Returns ``{order_id, amount (paise), currency, key_id}``. The order
        carries ``notes`` (clinic_id / patient_id) so the dashboard side is
        reconcilable, and the key_id returned here is the one the checkout
        popup needs (it is public — never the secret).
        """
        settings = await RazorpayService.get_settings(db, clinic_id)
        if settings is None:
            raise RazorpayNotConfiguredError(
                "Razorpay is not configured for this clinic. Set it in Settings first."
            )
        client = RazorpayService._client(settings)
        paise = int(round(amount * 100))
        order = client.order.create(
            {
                "amount": paise,
                "currency": clinic_currency,
                "payment_capture": 1,
                "notes": {"clinic_id": str(clinic_id), "patient_id": str(patient_id)},
            }
        )
        return {
            "order_id": order["id"],
            "amount": order["amount"],
            "currency": order["currency"],
            "key_id": settings.key_id,
        }

    @staticmethod
    def _verify_signature(
        key_secret: str, payment_id: str, order_id: str, signature: str
    ) -> bool:
        msg = f"{order_id}|{payment_id}".encode()
        digest = hmac.new(key_secret.encode(), msg, hashlib.sha256).hexdigest()
        return hmac.compare_digest(digest, signature)

    @staticmethod
    async def capture_and_record(
        db: AsyncSession,
        *,
        clinic_id: UUID,
        patient_id: UUID,
        recorded_by: UUID,
        payment_date,
        razorpay_payment_id: str,
        razorpay_order_id: str,
        razorpay_signature: str,
        allocations: list[dict],
    ):
        """Verify a checkout response and record the payment transactionally.

        This is the trust boundary: the amount/currency/method come from
        Razorpay's payment payload, never from the request.
        """
        settings = await RazorpayService.get_settings(db, clinic_id)
        if settings is None:
            raise RazorpayNotConfiguredError(
                "Razorpay is not configured for this clinic. Set it in Settings first."
            )

        key_secret = decrypt_password(settings.key_secret_encrypted)
        if not key_secret:
            raise RazorpayNotConfiguredError(
                "Razorpay is not configured for this clinic (key secret missing)."
            )
        if not RazorpayService._verify_signature(
            key_secret, razorpay_payment_id, razorpay_order_id, razorpay_signature
        ):
            raise RazorpayPaymentError("Invalid Razorpay signature — payment not recorded.")

        client = RazorpayService._client(settings)
        payment = client.payment.fetch(razorpay_payment_id)
        if payment.get("status") != "captured":
            raise RazorpayPaymentError(
                f"Razorpay payment {razorpay_payment_id} is not captured "
                f"(status={payment.get('status')})."
            )
        if payment.get("order_id") != razorpay_order_id:
            raise RazorpayPaymentError("Razorpay payment belongs to a different order.")

        amount_paise = payment["amount"]
        amount = Decimal(amount_paise) / Decimal(100)
        currency = payment["currency"]
        method = _map_method(payment.get("method", ""))
        notes = f"Razorpay payment: {razorpay_payment_id} ({razorpay_order_id})"

        allocated = sum(Decimal(a["amount"]) for a in allocations)
        if allocated != amount:
            raise RazorpayPaymentError(
                f"Allocations sum {allocated} does not match captured amount {amount}."
            )

        payment_row = await record_payment(
            db,
            clinic_id=clinic_id,
            currency=currency,
            patient_id=patient_id,
            amount=amount,
            method=method,
            payment_date=payment_date,
            recorded_by=recorded_by,
            allocations=allocations,
            reference=razorpay_payment_id,
            notes=notes,
            context={"gateway": "razorpay", "order_id": razorpay_order_id},
            idempotency_key=f"razorpay:{razorpay_payment_id}",
        )
        return payment_row