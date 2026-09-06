"""razorpay — Razorpay online payment gateway for Indian clinics.

Owned by the ``payments.collect.actions`` slot: when the clinic's country
is ``IN`` and a staff member with ``razorpay.collect`` opens the payments
screen / budget card / patient ledger, the Razorpay collect button is
rendered. The gateway is per-clinic (each clinic configures its own
``key_id`` / ``key_secret`` in Settings) and takes the *request* flow
through the module's own endpoints:

- ``POST /razorpay/order``  — create a Razorpay order server-side.
- ``POST /razorpay/verify`` — HMAC-verify the checkout callback, fetch the
  captured payment from Razorpay, and record it via ``payments.workflow``
  with an idempotency key (a replay can never double-record money).

Depends on ``payments`` only. ``record_payment`` is the single write path —
this module never duplicates payment logic. Migration lives on its own
``razorpay`` Alembic branch, so uninstall is branch-scoped.
"""

from fastapi import APIRouter

from app.core.plugins import BaseModule

from .models import RazorpaySettings
from .router import router


class RazorpayModule(BaseModule):
    manifest = {
        "name": "razorpay",
        "version": "0.1.0",
        "summary": "Razorpay online payments (India) via the payments collect slot.",
        "author": "DentalPin Core Team",
        "license": "BSL-1.1",
        "category": "official",
        "depends": ["payments"],
        "installable": True,
        "auto_install": False,
        "removable": True,
        "role_permissions": {
            "admin": ["*"],
            # Same roles payments' ``record.write`` grants: whoever can
            # record a payment at the counter can collect via the gateway.
            "dentist": ["collect"],
            "assistant": ["collect"],
            "receptionist": ["collect"],
        },
        "frontend": {
            "layer_path": "frontend",
            "navigation": [],
        },
    }

    def get_models(self) -> list:
        return [RazorpaySettings]

    def get_router(self) -> APIRouter:
        return router

    def get_permissions(self) -> list[str]:
        # Namespaced → razorpay.settings.read / .write and razorpay.collect
        return ["settings.read", "settings.write", "collect"]