"""Tests for the clinic-scoped role management API (issue #46).

The endpoints live under ``/api/v1/roles`` and are gated by
``admin.roles.read`` / ``admin.roles.write``. The caller's clinic owns custom
roles; system roles are shared and only their per-clinic overrides are
mutable.
"""

from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.auth.models import ClinicMembership, Role
from app.core.auth.rbac import has_permission_in_clinic
from app.core.auth.seed_rbac import seed_rbac


@pytest.fixture(autouse=True)
async def _seeded(db_session):
    """Populate the RBAC tables so the catalog and system roles exist."""
    await seed_rbac(db_session)
    return db_session


async def test_list_permission_catalog_returns_grantable_codes(client, auth_headers, test_clinic):
    resp = await client.get("/api/v1/roles/catalog", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()["data"]
    codes = {p["code"] for p in body}
    # Core + a module code should be present.
    assert "admin.users.write" in codes


async def test_create_and_list_custom_role(client, auth_headers, test_clinic):
    resp = await client.post(
        "/api/v1/roles",
        json={"name": "frontdesk", "permissions": ["patients.read"]},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    created = resp.json()["data"]
    assert created["name"] == "frontdesk"
    assert created["is_system"] is False
    assert "patients.read" in created["permissions"]

    listed = await client.get("/api/v1/roles", headers=auth_headers)
    names = {r["name"] for r in listed.json()["data"]}
    assert "frontdesk" in names


async def test_create_rejects_system_role_name(client, auth_headers, test_clinic):
    resp = await client.post(
        "/api/v1/roles",
        json={"name": "admin", "permissions": []},
        headers=auth_headers,
    )
    assert resp.status_code == 409


async def test_create_rejects_duplicate_custom_role(client, auth_headers, test_clinic):
    await client.post(
        "/api/v1/roles",
        json={"name": "hygiene_lead", "permissions": []},
        headers=auth_headers,
    )
    resp = await client.post(
        "/api/v1/roles",
        json={"name": "hygiene_lead", "permissions": []},
        headers=auth_headers,
    )
    assert resp.status_code == 409


async def test_create_rejects_unknown_permission(client, auth_headers, test_clinic):
    resp = await client.post(
        "/api/v1/roles",
        json={"name": "badrole", "permissions": ["nosuch.permission"]},
        headers=auth_headers,
    )
    assert resp.status_code == 422


async def test_update_custom_role_permissions(client, auth_headers, test_clinic):
    created = (
        await client.post(
            "/api/v1/roles",
            json={"name": "labkit", "permissions": ["patients.read"]},
            headers=auth_headers,
        )
    ).json()["data"]
    role_id = created["id"]

    resp = await client.put(
        f"/api/v1/roles/{role_id}",
        json={"permissions": ["patients.write"]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    updated = resp.json()["data"]
    assert "patients.write" in updated["permissions"]
    assert "patients.read" not in updated["permissions"]


async def test_delete_custom_role(client, auth_headers, test_clinic):
    created = (
        await client.post(
            "/api/v1/roles",
            json={"name": "temp", "permissions": []},
            headers=auth_headers,
        )
    ).json()["data"]
    role_id = created["id"]

    resp = await client.delete(f"/api/v1/roles/{role_id}", headers=auth_headers)
    assert resp.status_code == 204

    # Re-delete / fetch of a missing role is a 404.
    again = await client.delete(f"/api/v1/roles/{role_id}", headers=auth_headers)
    assert again.status_code == 404


async def test_delete_blocks_when_role_assigned(client, auth_headers, test_clinic, db_session):
    """A role still held by a member cannot be deleted."""
    created = (
        await client.post(
            "/api/v1/roles",
            json={"name": "duty", "permissions": []},
            headers=auth_headers,
        )
    ).json()["data"]
    role_id = created["id"]

    # Assign a second membership in this role to the test user in test_clinic.
    user_id = (await client.get("/api/v1/auth/me", headers=auth_headers)).json()["data"]["user"][
        "id"
    ]
    db_session.add(
        ClinicMembership(
            id=uuid4(),
            user_id=user_id,
            clinic_id=test_clinic.id,
            role="duty",
        )
    )
    await db_session.commit()

    resp = await client.delete(f"/api/v1/roles/{role_id}", headers=auth_headers)
    assert resp.status_code == 409


async def test_unknown_role_id_is_404(client, auth_headers, test_clinic):
    """A role id that does not exist (or belongs to another clinic) 404s."""
    missing = await client.delete(f"/api/v1/roles/{uuid4()}", headers=auth_headers)
    assert missing.status_code == 404


async def test_role_override_grant_and_revoke(client, auth_headers, test_clinic, db_session):
    """Per-clinic override on a system role adds/removes a permission."""
    dentist = (
        (await db_session.execute(select(Role).where(Role.name == "dentist"))).scalars().first()
    )
    assert dentist is not None and dentist.is_system

    # Revoke agents.supervise for the dentist in this clinic.
    resp = await client.put(
        f"/api/v1/roles/{dentist.id}/overrides",
        json={"granted": [], "revoked": ["agents.supervise"]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["revoked"] == ["agents.supervise"]

    assert (
        await has_permission_in_clinic(db_session, test_clinic.id, "dentist", "agents.supervise")
        is False
    )
    # System default unaffected.
    assert await has_permission_in_clinic(db_session, None, "dentist", "agents.supervise") is True


async def test_role_override_rejects_custom_role(client, auth_headers, test_clinic):
    """Overrides apply only to system roles, not clinic-custom ones."""
    created = (
        await client.post(
            "/api/v1/roles",
            json={"name": "customtmp", "permissions": []},
            headers=auth_headers,
        )
    ).json()["data"]
    resp = await client.put(
        f"/api/v1/roles/{created['id']}/overrides",
        json={"granted": ["patients.read"], "revoked": []},
        headers=auth_headers,
    )
    assert resp.status_code == 422
