"""sms_gateway: seed system SMS templates (smg_0002).

Template-kind SMS sends render ``body_text`` from the template row at
dispatch time; with no ``channel='sms'`` row the send goes out empty
(maintainer review on #384). This seeds one system row (clinic_id NULL,
is_system) per notification type and locale (es/en) so SMS works out of
the box; clinics can override per key/locale with their own rows, which
take precedence and are never touched here.

Downgrade removes exactly the seeded rows (matched by the description
marker), leaving clinic-authored SMS templates alone.
Uninstall-roundtrip clean by construction.

Revision ID: smg_0002
Revises: smg_0001
Create Date: 2026-09-06
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "smg_0002"
down_revision: str | None = "smg_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MARKER = "Seeded by sms_gateway smg_0002 (system SMS templates)"

# (template_key, es_body, en_body). Literal text only: the dispatch path
# uses body_text verbatim (no placeholder substitution on SMS).
ROWS: tuple[tuple[str, str, str], ...] = (
    (
        "appointment_confirmation",
        "Su cita ha quedado confirmada. Le esperamos en la clínica.",
        "Your appointment is confirmed. We look forward to seeing you.",
    ),
    (
        "appointment_reminder",
        "Recordatorio: tiene cita mañana en su clínica dental.",
        "Reminder: you have an appointment tomorrow at your dental clinic.",
    ),
    (
        "appointment_cancelled",
        "Su cita ha sido cancelada. Llámenos para pedir una nueva.",
        "Your appointment has been cancelled. Call us to reschedule.",
    ),
    (
        "budget_sent",
        "Tiene un nuevo presupuesto disponible en su clínica dental.",
        "A new treatment estimate is available at your dental clinic.",
    ),
    (
        "budget_accepted",
        "Gracias, hemos registrado la aceptación de su presupuesto.",
        "Thank you, your treatment estimate acceptance is recorded.",
    ),
    (
        "budget_reminder",
        "Le recordamos que tiene un presupuesto pendiente de respuesta.",
        "Reminder: you have a treatment estimate awaiting your reply.",
    ),
    (
        "invoice_sent",
        "Tiene una nueva factura disponible en su clínica dental.",
        "A new invoice is available at your dental clinic.",
    ),
    (
        "welcome",
        "Bienvenido/a a su clínica dental. Este es nuestro canal de avisos.",
        "Welcome to your dental clinic. This is our notifications channel.",
    ),
    (
        "recall_reminder",
        "Le recordamos su próxima revisión dental. Llámenos para confirmar.",
        "Reminder about your upcoming dental check-up. Call us to confirm.",
    ),
)

_INSERT = sa.text(
    """
INSERT INTO notification_templates
    (id, clinic_id, channel, template_key, locale, body_text,
     is_system, is_active, description, created_at, updated_at)
SELECT gen_random_uuid(), NULL, 'sms', :key, :locale, :body,
       TRUE, TRUE, :marker, now(), now()
WHERE NOT EXISTS (
    SELECT 1 FROM notification_templates
    WHERE clinic_id IS NULL
      AND channel = 'sms'
      AND template_key = :key
      AND locale = :locale
)
"""
)

_DELETE = sa.text(
    """
DELETE FROM notification_templates
WHERE clinic_id IS NULL
  AND channel = 'sms'
  AND description = :marker
"""
)


def upgrade() -> None:
    conn = op.get_bind()
    for key, es_body, en_body in ROWS:
        for locale, body in (("es", es_body), ("en", en_body)):
            conn.execute(_INSERT, {"key": key, "locale": locale, "body": body, "marker": MARKER})


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(_DELETE, {"marker": MARKER})
