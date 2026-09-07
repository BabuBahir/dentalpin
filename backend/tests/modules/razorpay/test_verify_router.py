"""razorpay order/verify endpoints — the trust boundary.

These tests pin the security contract from PR #373 review:
- The amount/currency/method recorded come from Razorpay's capture, never
  from the browser payload.
- The HMAC signature is verified against the clinic's key secret.
- A replay of the same razorpay payment id returns the same Payment
  (idempotency_key), never a double record.
"""

import hashlib
import hmac
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.modules.razorpay.service import RazorpayService

ORDER = "/api/v1/razorpay/order"
VERIFY = "/api/v1/razorpay/verify"

KEY_ID = "rzp_test_abcd1234"
KEY_SECRET = "rzp_test_secret_abcd"

ORDER_ID = "order_RP_791314"


def _signature(payment_id: str, order_id: str, secret: str = KEY_SECRET) -> str:
    payload = f"{order_id}|{payment_id}".encode()
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def _default_payment(payment_id: str) -> dict:
    return {
        "id": payment_id,
        "amount": 1000,
        "currency": "INR",
        "status": "captured",
        "order_id": ORDER_ID,
        "method": "upi",
    }


class _FakeOrder:
    def __init__(self, order_id: str):
        self._order_id = order_id

    def create(self, data: dict) -> dict:
        return {
            "id": self._order_id,
            "amount": data["amount"],
            "currency": data["currency"],
        }


class _FakePayment:
    def __init__(self, payment: dict | None):
        self._payment = payment

    def fetch(self, payment_id: str) -> dict:
        if self._payment is None:
            return _default_payment(payment_id)
        return {**self._payment, "id": payment_id}


class FakeRazorpayClient:
    """Mirrors the subset of razorpay.Client used by RazorpayService."""

    def __init__(self, payment: dict | None = None, order_id: str = ORDER_ID):
        self.order = _FakeOrder(order_id)
        self.payment = _FakePayment(payment)


def _patch_client(monkeypatch, payment: dict | None = None):
    fake = FakeRazorpayClient(payment)
    monkeypatch.setattr(RazorpayService, "_client", staticmethod(lambda settings: fake))
    return fake


async def _configure_gateway(client: AsyncClient, auth_headers: dict) -> None:
    res = await client.put(
        "/api/v1/razorpay/settings",
        json={"key_id": KEY_ID, "key_secret": KEY_SECRET},
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text


def _verify_payload(patient_id, payment_id, amount=10) -> dict:
    return {
        "patient_id": str(patient_id),
        "razorpay_payment_id": payment_id,
        "razorpay_order_id": ORDER_ID,
        "razorpay_signature": _signature(payment_id, ORDER_ID),
        "allocations": [{"target_type": "on_account", "target_id": None, "amount": amount}],
    }


@pytest.mark.asyncio
async def test_order_requires_configured_gateway(
    client: AsyncClient, auth_headers, test_clinic
):
    res = await client.post(
        ORDER,
        json={"patient_id": "00000000-0000-0000-0000-000000000000", "amount": 10},
        headers=auth_headers,
    )
    assert res.status_code == 400
    assert "not configured" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_order_creates_order_server_side(
    client: AsyncClient, auth_headers, test_clinic, test_patient, monkeypatch
):
    await _configure_gateway(client, auth_headers)
    _patch_client(monkeypatch)

    res = await client.post(
        ORDER,
        json={"patient_id": str(test_patient.id), "amount": 10},
        headers=auth_headers,
    )
    assert res.status_code == 201, res.text
    data = res.json()["data"]
    assert data["order_id"] == ORDER_ID
    assert data["amount"] == 1000  # paise
    assert data["currency"] == "INR"
    assert data["key_id"] == KEY_ID


@pytest.mark.asyncio
async def test_order_rejects_zero_amount(
    client: AsyncClient, auth_headers, test_clinic, test_patient
):
    await _configure_gateway(client, auth_headers)
    res = await client.post(
        ORDER,
        json={"patient_id": str(test_patient.id), "amount": 0},
        headers=auth_headers,
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_verify_rejects_bad_signature(
    client: AsyncClient, auth_headers, test_clinic, test_patient, monkeypatch
):
    await _configure_gateway(client, auth_headers)

    payload = _verify_payload(test_patient.id, "pay_RP_001")
    payload["razorpay_signature"] = "deadbeef"
    res = await client.post(VERIFY, json=payload, headers=auth_headers)
    assert res.status_code == 400
    assert "signature" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_verify_rejects_unfinished_capture(
    client: AsyncClient, auth_headers, test_clinic, test_patient, monkeypatch
):
    await _configure_gateway(client, auth_headers)
    _patch_client(
        monkeypatch,
        payment={
            "id": "pay_RP_002",
            "amount": 1000,
            "currency": "INR",
            "status": "authorized",  # not captured → reject
            "order_id": ORDER_ID,
            "method": "upi",
        },
    )

    res = await client.post(
        VERIFY, json=_verify_payload(test_patient.id, "pay_RP_002"), headers=auth_headers
    )
    assert res.status_code == 400
    assert "not captured" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_verify_rejects_order_mismatch(
    client: AsyncClient, auth_headers, test_clinic, test_patient, monkeypatch
):
    await _configure_gateway(client, auth_headers)
    # Captured, but the fake payment belongs to a different order.
    _patch_client(
        monkeypatch,
        payment={
            "id": "pay_RP_003",
            "amount": 1000,
            "currency": "INR",
            "status": "captured",
            "order_id": "order_OTHER",
            "method": "upi",
        },
    )

    res = await client.post(
        VERIFY, json=_verify_payload(test_patient.id, "pay_RP_003"), headers=auth_headers
    )
    assert res.status_code == 400
    assert "different order" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_verify_rejects_allocation_sum_mismatch(
    client: AsyncClient, auth_headers, test_clinic, test_patient, monkeypatch
):
    await _configure_gateway(client, auth_headers)
    _patch_client(monkeypatch)

    # Captured is 10.00 INR, allocation claims 9.00.
    res = await client.post(
        VERIFY,
        json=_verify_payload(test_patient.id, "pay_RP_004", amount=9),
        headers=auth_headers,
    )
    assert res.status_code == 400
    assert "does not match" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_verify_records_captured_payment_with_gateway_values(
    client: AsyncClient, auth_headers, test_clinic, test_patient, monkeypatch
):
    await _configure_gateway(client, auth_headers)
    _patch_client(monkeypatch)

    res = await client.post(
        VERIFY, json=_verify_payload(test_patient.id, "pay_RP_005"), headers=auth_headers
    )
    assert res.status_code == 201, res.text
    data = res.json()["data"]
    assert data["method"] == "upi"
    assert Decimal(data["amount"]) == Decimal("10.00")
    assert data["currency"] == "INR"
    assert data["reference"] == "pay_RP_005"


@pytest.mark.asyncio
async def test_verify_replay_is_idempotent(
    client: AsyncClient, auth_headers, test_clinic, test_patient, monkeypatch
):
    await _configure_gateway(client, auth_headers)
    _patch_client(monkeypatch)

    payload = _verify_payload(test_patient.id, "pay_RP_006")
    first = await client.post(VERIFY, json=payload, headers=auth_headers)
    assert first.status_code == 201
    second = await client.post(VERIFY, json=payload, headers=auth_headers)
    assert second.status_code == 201
    assert second.json()["data"]["id"] == first.json()["data"]["id"]


@pytest.mark.asyncio
async def test_verify_maps_method_names(
    client: AsyncClient, auth_headers, test_clinic, test_patient, monkeypatch
):
    await _configure_gateway(client, auth_headers)

    cases = (
        ("netbanking", "netbanking"),
        ("card", "card"),
        ("upi", "upi"),
        ("wallet", "other"),
        ("emi", "other"),
    )
    for index, (rz_method, expected) in enumerate(cases):
        _patch_client(
            monkeypatch,
            payment={
                "id": f"pay_RP_{index:03d}",
                "amount": 1000,
                "currency": "INR",
                "status": "captured",
                "order_id": ORDER_ID,
                "method": rz_method,
            },
        )
        res = await client.post(
            VERIFY,
            json=_verify_payload(test_patient.id, f"pay_RP_{index:03d}"),
            headers=auth_headers,
        )
        assert res.status_code == 201, res.text
        assert res.json()["data"]["method"] == expected