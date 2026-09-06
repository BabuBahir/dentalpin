"""razorpay: initial schema.

One table (own Alembic branch ``razorpay`` per ADR 0002, so uninstall is
branch-scoped and drops only this):
    - ``razorpay_settings`` — per-clinic gateway key id + encrypted secret.

Revision ID: rp_0001
Revises:
Create Date: 2026-09-06
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "rp_0001"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = ("razorpay",)
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "razorpay_settings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("key_id", sa.Text(), nullable=False),
        sa.Column("key_secret_encrypted", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clinic_id"),
    )
    op.create_index("idx_razorpay_settings_clinic", "razorpay_settings", ["clinic_id"])


def downgrade() -> None:
    op.drop_index("idx_razorpay_settings_clinic", table_name="razorpay_settings")
    op.drop_table("razorpay_settings")