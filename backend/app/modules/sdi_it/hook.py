"""SDI implementation of ``BillingComplianceHook`` (country ``IT``).

Registered from ``SdiItModule.on_activate``; billing finds it by the
clinic's country. The gate of ADR 0025 lives here: only invoices whose
recipient is a *soggetto passivo IVA* (a valid partita IVA in
``billing_tax_id``) become FPR12 files. Invoices to natural persons —
the healthcare B2C case art. 10-bis DL 119/2018 keeps out of the SDI —
return a ``not_applicable`` marker and nothing is queued.

``on_invoice_issued`` builds the XML into a ``pending`` record (no
network in the request); the manual transport (this PR) hands the file
to the admin, the PEC transport (later) sends it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.billing.hooks import BillingComplianceHook

from .models import SdiItRecord, SdiItSettings
from .services.tax_ids import PartitaIva, is_business_recipient
from .services.xml_builder import Party, SdiBuildError, build_fattura, progressivo_invio

if TYPE_CHECKING:
    from app.modules.billing.models import Invoice

NOT_APPLICABLE_REASON = "b2c_healthcare_art_10bis"


async def get_settings(db: AsyncSession, clinic_id) -> SdiItSettings | None:
    return (
        await db.execute(select(SdiItSettings).where(SdiItSettings.clinic_id == clinic_id))
    ).scalar_one_or_none()


async def _clinic(db: AsyncSession, clinic_id) -> Clinic | None:
    return (await db.execute(select(Clinic).where(Clinic.id == clinic_id))).scalar_one_or_none()


def cedente_from_clinic(clinic: Clinic) -> Party:
    return Party.from_clinic(
        tax_id=clinic.tax_id,
        name=(clinic.legal_name or clinic.name or "").strip(),
        address=clinic.address,
    )


async def build_record(
    db: AsyncSession,
    invoice: Invoice,
    settings: SdiItSettings,
    *,
    original: Invoice | None = None,
) -> SdiItRecord:
    """Render the FPR12 file for ``invoice`` and add a ``pending`` record.

    Bumps the clinic's ``progressivo_invio`` counter; raises
    ``SdiBuildError`` when the schema cannot be satisfied.
    """
    clinic = await _clinic(db, invoice.clinic_id)
    if clinic is None:
        raise SdiBuildError("Clinica non trovata.")
    cedente = cedente_from_clinic(clinic)
    cessionario = Party.from_recipient(
        tax_id=invoice.billing_tax_id, name=invoice.billing_name, address=invoice.billing_address
    )
    settings.progressivo_invio = (settings.progressivo_invio or 0) + 1
    result = build_fattura(
        invoice,
        cedente=cedente,
        cessionario=cessionario,
        progressivo=progressivo_invio(settings.progressivo_invio),
        regime_fiscale=settings.regime_fiscale,
        riferimento_normativo=settings.riferimento_normativo,
        bollo_virtuale=settings.bollo_virtuale,
        original_invoice_number=original.invoice_number if original else None,
        original_invoice_date=(
            original.issue_date.isoformat() if original and original.issue_date else None
        ),
    )
    record = SdiItRecord(
        clinic_id=invoice.clinic_id,
        invoice_id=invoice.id,
        tipo_documento=result.tipo_documento,
        invoice_number=result.invoice_number,
        issue_date=invoice.issue_date,
        gross_amount=result.gross_amount,
        recipient_name=invoice.billing_name,
        recipient_tax_id=invoice.billing_tax_id,
        codice_destinatario=result.codice_destinatario,
        progressivo=progressivo_invio(settings.progressivo_invio),
        file_name=result.file_name,
        xml_payload=result.xml,
        state="pending",
        created_at=datetime.now(UTC),
    )
    db.add(record)
    await db.flush()
    return record


class SdiItHook(BillingComplianceHook):
    @property
    def country_code(self) -> str:
        return "IT"

    @property
    def name(self) -> str:
        return "FatturaPA / SDI (IT)"

    def get_required_fields(self) -> list[str]:
        return []  # patients need nothing; B2B recipients need a partita IVA (validated below)

    async def validate_before_issue(self, invoice, db) -> tuple[bool, str | None]:
        settings = await get_settings(db, invoice.clinic_id)
        if settings is None or not settings.enabled:
            return True, None
        if not is_business_recipient(invoice.billing_tax_id):
            return True, None  # analogue invoice; the SDI is not involved
        clinic = await _clinic(db, invoice.clinic_id)
        if clinic is None or PartitaIva.parse(clinic.tax_id) is None:
            return (
                False,
                "Imposta la partita IVA della clinica (11 cifre) per la fatturazione elettronica.",
            )
        if (clinic.currency or "EUR") != "EUR":
            return False, "La fatturazione elettronica SDI richiede fatture in EUR."
        return True, None

    async def on_invoice_issued(self, invoice, db) -> dict[str, Any]:
        return await self._queue(invoice, db, original=None)

    async def on_credit_note_issued(self, credit_note, original_invoice, db) -> dict[str, Any]:
        return await self._queue(credit_note, db, original=original_invoice)

    async def _queue(
        self, invoice: Invoice, db: AsyncSession, *, original: Invoice | None
    ) -> dict[str, Any]:
        settings = await get_settings(db, invoice.clinic_id)
        if settings is None or not settings.enabled:
            return {}
        if not is_business_recipient(invoice.billing_tax_id):
            return {"IT": {"sdi": "not_applicable", "reason": NOT_APPLICABLE_REASON}}
        try:
            record = await build_record(db, invoice, settings, original=original)
        except SdiBuildError as exc:
            settings.last_error = str(exc)[:500]
            return {"IT": {"sdi": "error", "error": str(exc)}}
        return {
            "IT": {
                "sdi": "queued",
                "record_id": str(record.id),
                "tipo_documento": record.tipo_documento,
                "file_name": record.file_name,
                "state": record.state,
            }
        }
