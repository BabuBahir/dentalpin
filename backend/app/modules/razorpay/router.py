"""razorpay HTTP surface — mounted at ``/api/v1/razorpay/``.

Three endpoints:
- ``GET/PUT /settings`` — clinic's own gateway credentials (per-clinic,
  encrypted at rest). The collect button is gated on this being set.
- ``POST /order`` — create a Razorpay order server-side (never hands the
  secret to the browser; only the public key id).
- ``POST /verify`` — verify the checkout signature, fetch+validate the
  captured payment from Razorpay, and record it via the payments module's
  ``record_payment`` with an idempotency key.

Every query is tenant-scoped via ``ctx.clinic_id``.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse
from app.database import get_db
from app.modules.payments.schemas import PaymentResponse
from app.modules.payments.service import PaymentService
from app.modules.payments.workflow import PaymentWorkflowError

from .schemas import (
    RazorpayOrderCreate,
    RazorpayOrderResponse,
    RazorpaySettingsResponse,
    RazorpaySettingsUpdate,
    RazorpayVerifyCreate,
)
from .service import RazorpayNotConfiguredError, RazorpayPaymentError, RazorpayService

router = APIRouter()


def _settings_response(settings) -> RazorpaySettingsResponse:
    if settings is None:
        return RazorpaySettingsResponse(key_id="", is_active=False, has_key_secret=False)
    return RazorpaySettingsResponse(
        key_id=settings.key_id,
        is_active=settings.is_active,
        has_key_secret=bool(settings.key_secret_encrypted),
    )


@router.get("/settings", response_model=ApiResponse[RazorpaySettingsResponse])
async def get_settings(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("razorpay.settings.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[RazorpaySettingsResponse]:
    settings = await RazorpayService.get_settings(db, ctx.clinic_id)
    return ApiResponse(data=_settings_response(settings))


@router.put("/settings", response_model=ApiResponse[RazorpaySettingsResponse])
async def update_settings(
    data: RazorpaySettingsUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("razorpay.settings.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[RazorpaySettingsResponse]:
    settings = await RazorpayService.upsert_settings(
        db,
        ctx.clinic_id,
        key_id=data.key_id,
        key_secret=data.key_secret,
        is_active=data.is_active,
    )
    return ApiResponse(data=_settings_response(settings))


@router.post("/order", response_model=ApiResponse[RazorpayOrderResponse], status_code=201)
async def create_order(
    payload: RazorpayOrderCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("razorpay.collect"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[RazorpayOrderResponse]:
    try:
        order = await RazorpayService.create_order(
            db,
            clinic_id=ctx.clinic_id,
            patient_id=payload.patient_id,
            amount=payload.amount,
            clinic_currency=ctx.clinic.currency,
        )
    except RazorpayNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return ApiResponse(data=RazorpayOrderResponse(**order))


@router.post("/verify", response_model=ApiResponse[PaymentResponse], status_code=201)
async def verify_payment(
    payload: RazorpayVerifyCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("razorpay.collect"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PaymentResponse]:
    try:
        payment = await RazorpayService.capture_and_record(
            db,
            clinic_id=ctx.clinic_id,
            patient_id=payload.patient_id,
            recorded_by=ctx.user_id,
            payment_date=payload.payment_date,
            razorpay_payment_id=payload.razorpay_payment_id,
            razorpay_order_id=payload.razorpay_order_id,
            razorpay_signature=payload.razorpay_signature,
            allocations=[a.model_dump() for a in payload.allocations],
        )
    except RazorpayNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except RazorpayPaymentError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except PaymentWorkflowError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    fresh = await PaymentService.get(db, ctx.clinic_id, payment.id)
    if fresh is None:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail="Payment vanished after create")
    return ApiResponse(data=PaymentResponse.from_model(fresh))
