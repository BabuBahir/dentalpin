"""razorpay settings API tests (per-clinic encrypted credentials, never
re-emitted to the client)."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.razorpay.models import RazorpaySettings

SETTINGS = "/api/v1/razorpay/settings"

KEY_ID = "rzp_test_abcd1234"
KEY_SECRET = "rzp_test_secret_abcd"


@pytest.mark.asyncio
async def test_settings_lifecycle_never_returns_secret(
    client: AsyncClient, auth_headers, test_clinic, db_session: AsyncSession
):
    res = await client.put(
        SETTINGS,
        json={"key_id": KEY_ID, "key_secret": KEY_SECRET},
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()["data"]
    assert body["key_id"] == KEY_ID
    assert body["has_key_secret"] is True
    assert "key_secret" not in body

    # Stored Fernet-encrypted, never plaintext.
    stored = (
        await db_session.execute(
            select(RazorpaySettings).where(RazorpaySettings.clinic_id == test_clinic.id)
        )
    ).scalar_one()
    assert KEY_SECRET not in stored.key_secret_encrypted

    # Reads never leak the secret either.
    res = await client.get(SETTINGS, headers=auth_headers)
    body = res.json()["data"]
    assert body["has_key_secret"] is True
    assert body["key_id"] == KEY_ID
    assert "key_secret" not in body


@pytest.mark.asyncio
async def test_settings_read_before_write_reports_unconfigured(
    client: AsyncClient, auth_headers, test_clinic
):
    res = await client.get(SETTINGS, headers=auth_headers)
    assert res.status_code == 200, res.text
    body = res.json()["data"]
    assert body["key_id"] == ""
    assert body["is_active"] is False
    assert body["has_key_secret"] is False


@pytest.mark.asyncio
async def test_settings_disabled_mid_stream(client: AsyncClient, auth_headers, test_clinic):
    await client.put(
        SETTINGS,
        json={"key_id": KEY_ID, "key_secret": KEY_SECRET},
        headers=auth_headers,
    )
    res = await client.put(
        SETTINGS,
        json={"key_id": KEY_ID, "key_secret": KEY_SECRET, "is_active": False},
        headers=auth_headers,
    )
    assert res.json()["data"]["is_active"] is False


@pytest.mark.asyncio
async def test_settings_requires_key_id_and_secret(client: AsyncClient, auth_headers, test_clinic):
    res = await client.put(SETTINGS, json={"key_id": ""}, headers=auth_headers)
    assert res.status_code == 422
