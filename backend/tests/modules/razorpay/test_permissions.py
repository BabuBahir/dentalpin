"""Role permission boundaries for razorpay endpoints.

manifest.role_permissions grants ``collect`` to the same roles that can
record a counter payment (dentist / assistant / receptionist) and keeps
``settings.{read,write}`` admin-only — gateway credentials are a clinic-level
secret, not a clinical concern.
"""

from __future__ import annotations

from uuid import uuid4

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership, User

ORDER = "/api/v1/razorpay/order"
SETTINGS = "/api/v1/razorpay/settings"


@pytest_asyncio.fixture
async def razorpay_clinic(db_session: AsyncSession, auth_headers, client: AsyncClient) -> Clinic:
    from uuid import uuid4

    from app.core.auth.models import Clinic as _Clinic
    from app.core.auth.models import ClinicMembership as _Membership
    from app.modules.agenda.models import Cabinet

    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = me.json()["data"]["user"]["id"]

    clinic = _Clinic(
        id=uuid4(),
        name="Razorpay Test Clinic",
        tax_id="B12345678",
        address={"street": "Test St", "city": "Chennai"},
        settings={"country": "IN"},
    )
    db_session.add(clinic)
    await db_session.flush()
    db_session.add(_Membership(id=uuid4(), user_id=user_id, clinic_id=clinic.id, role="admin"))
    db_session.add(
        Cabinet(
            id=uuid4(),
            clinic_id=clinic.id,
            name="Gabinete 1",
            color="#3B82F6",
            display_order=0,
            is_active=True,
        )
    )
    await db_session.commit()
    return clinic


@pytest_asyncio.fixture
async def role_headers(db_session: AsyncSession, razorpay_clinic: Clinic):
    """Factory: auth headers for a fresh user with the given role."""
    from app.core.auth.service import create_access_token, hash_password

    async def _make(role: str) -> dict[str, str]:
        user = User(
            email=f"{role}-{uuid4().hex[:8]}@example.com",
            password_hash=hash_password("TestPass1234"),
            first_name=role.title(),
            last_name="Test",
        )
        db_session.add(user)
        await db_session.flush()
        db_session.add(
            ClinicMembership(id=uuid4(), user_id=user.id, clinic_id=razorpay_clinic.id, role=role)
        )
        await db_session.commit()
        token = create_access_token(user.id, token_version=user.token_version)
        return {"Authorization": f"Bearer {token}"}

    return _make


async def test_receptionist_can_collect_but_not_configure(client: AsyncClient, role_headers):
    headers = await role_headers("receptionist")

    res = await client.post(
        ORDER,
        json={"patient_id": "00000000-0000-0000-0000-000000000000", "amount": 10},
        headers=headers,
    )
    # Reaches the (not configured) service → 400, not 403: permission is granted.
    assert res.status_code == 400

    res = await client.get(SETTINGS, headers=headers)
    assert res.status_code == 403
    res = await client.put(
        SETTINGS,
        json={"key_id": "k", "key_secret": "s"},
        headers=headers,
    )
    assert res.status_code == 403


async def test_hygienist_has_no_razorpay_access(client: AsyncClient, role_headers):
    headers = await role_headers("hygienist")

    res = await client.post(
        ORDER,
        json={"patient_id": "00000000-0000-0000-0000-000000000000", "amount": 10},
        headers=headers,
    )
    assert res.status_code == 403
    res = await client.get(SETTINGS, headers=headers)
    assert res.status_code == 403
