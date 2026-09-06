"""sms_gateway: encrypted settings, masked views, honest placeholder, isolation."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.notifications.channels import Channel, channel_registry
from app.modules.notifications.gateway import NotificationGateway
from app.modules.sms_gateway.adapter import SmsGatewayAdapter
from app.modules.sms_gateway.schemas import mask_settings
from app.modules.sms_gateway.service import SmsGatewayService

SID = "ACaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
TOKEN = "supersecrettoken"


async def _configure(db, clinic_id, **kw):
    data = {"provider": "log", "is_active": True}
    data.update(kw)
    return await SmsGatewayService.upsert_settings(db, clinic_id, data)


@pytest.mark.asyncio
async def test_settings_roundtrip_masked(db_session: AsyncSession, test_clinic: Clinic):
    clinic_id = test_clinic.id
    row = await _configure(db_session, clinic_id, account_sid=SID, auth_token=TOKEN)
    out = mask_settings(row)
    assert out.has_account_sid is True
    assert out.has_auth_token is True
    assert out.provider == "log"
    dumped = out.model_dump_json()
    assert SID not in dumped
    assert TOKEN not in dumped
    assert row.account_sid_encrypted != SID
    assert row.auth_token_encrypted != TOKEN


@pytest.mark.asyncio
async def test_adapter_log_provider_sends(db_session: AsyncSession, test_clinic: Clinic):
    from app.modules.notifications.channels import OutboundMessage

    clinic_id = test_clinic.id
    await _configure(db_session, clinic_id)
    adapter = SmsGatewayAdapter()
    assert adapter.channel == Channel.SMS
    assert await adapter.supports(db_session, clinic_id) is True
    result = await adapter.send(
        db_session,
        OutboundMessage(
            channel=Channel.SMS,
            to_address="+34666123456",
            clinic_id=clinic_id,
            template_key="appointment_confirmation",
            message_kind="session",
            body_text="hola",
        ),
    )
    assert result.status.value == "sent"


@pytest.mark.asyncio
async def test_unimplemented_provider_fails_honestly(db_session: AsyncSession, test_clinic: Clinic):
    from app.modules.notifications.channels import OutboundMessage

    clinic_id = test_clinic.id
    await _configure(db_session, clinic_id, provider="twilio")
    adapter = SmsGatewayAdapter()
    result = await adapter.send(
        db_session,
        OutboundMessage(
            channel=Channel.SMS,
            to_address="+34666123456",
            clinic_id=clinic_id,
            template_key="appointment_confirmation",
        ),
    )
    assert result.status.value == "failed"
    assert "not implemented" in (result.error_message or "")


@pytest.mark.asyncio
async def test_gateway_end_to_end_over_sms(db_session: AsyncSession, test_patient):
    """Real adapter registered: an sms enqueue queues (log placeholder)."""
    clinic_id = test_patient.clinic_id
    patient_id = test_patient.id
    patient_phone = test_patient.phone
    await _configure(db_session, clinic_id)
    channel_registry.register(SmsGatewayAdapter())
    try:
        msg = await NotificationGateway.enqueue(
            db_session,
            clinic_id,
            "appointment_confirmation",
            context={},
            patient_id=patient_id,
            channels=["sms"],
        )
    finally:
        channel_registry.unregister("sms_gateway")
    assert msg.status == "queued"
    assert msg.channel == "sms"
    assert msg.to_address == patient_phone


@pytest.mark.asyncio
async def test_cross_clinic_isolation(db_session: AsyncSession, test_clinic: Clinic):
    other = Clinic(
        id=uuid4(),
        name="Other Clinic",
        tax_id="B99999994",
        address={"street": "Otra", "city": "Madrid"},
        settings={"slot_duration_min": 15},
    )
    db_session.add(other)
    await db_session.commit()
    await _configure(db_session, other.id)
    assert await SmsGatewayService.get_settings(db_session, test_clinic.id) is None
