"""sms_gateway HTTP surface — mounted at ``/api/v1/sms_gateway/`` (admin only)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse
from app.database import get_db

from .schemas import SmsSettingsResponse, SmsSettingsUpdate, mask_settings
from .service import SmsGatewayService

router = APIRouter()


@router.get("/settings", response_model=ApiResponse[SmsSettingsResponse])
async def get_settings(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("sms_gateway.settings.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[SmsSettingsResponse]:
    row = await SmsGatewayService.get_settings(db, ctx.clinic_id)
    if row is None:
        row = await SmsGatewayService.upsert_settings(db, ctx.clinic_id, {})
    return ApiResponse(data=mask_settings(row))


@router.put("/settings", response_model=ApiResponse[SmsSettingsResponse])
async def update_settings(
    data: SmsSettingsUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("sms_gateway.settings.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[SmsSettingsResponse]:
    row = await SmsGatewayService.upsert_settings(
        db, ctx.clinic_id, data.model_dump(exclude_unset=True)
    )
    return ApiResponse(data=mask_settings(row))


@router.post("/test", response_model=ApiResponse[dict], status_code=status.HTTP_200_OK)
async def test_connection(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("sms_gateway.settings.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[dict]:
    """Dry-run honesty check: reports what WOULD happen. Sends nothing."""
    row = await SmsGatewayService.get_settings(db, ctx.clinic_id)
    if row is None or not row.is_active:
        return ApiResponse(data={"configured": False, "would_send": False})
    if row.provider == "log":
        return ApiResponse(
            data={
                "configured": True,
                "would_send": True,
                "note": "log placeholder: messages are recorded in the server log, NOT SENT",
            }
        )
    return ApiResponse(
        data={
            "configured": True,
            "would_send": False,
            "note": f"provider '{row.provider}' is not implemented in v1",
        }
    )
