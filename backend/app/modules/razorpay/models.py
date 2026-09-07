"""razorpay models — per-clinic gateway credentials.

Keys are per-clinic (one Razorpay account per clinic, never shared across
tenants in a multi-clinic deployment): ``key_id`` is the public identifier
Razorpay hands back to the checkout popup, ``key_secret_encrypted`` is the
Fernet-encrypted secret used server-side for order creation and signature
verification (same scheme as SMTP passwords, whatsapp_webhook secrets and
verifactu certificates — ``app.core.email.encryption``).

The table lives on the module's own Alembic branch so uninstall drops it
cleanly (``removable=True``).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.core.auth.models import Clinic


class RazorpaySettings(Base, TimestampMixin):
    """Per-clinic Razorpay gateway configuration."""

    __tablename__ = "razorpay_settings"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), unique=True, index=True)

    key_id: Mapped[str] = mapped_column(Text)
    key_secret_encrypted: Mapped[str] = mapped_column(Text)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    clinic: Mapped["Clinic"] = relationship(foreign_keys=[clinic_id])

    __table_args__ = (Index("idx_razorpay_settings_clinic", "clinic_id"),)