"""sms_gateway round-trip uninstall test.

Install -> uninstall -> reinstall must drop ONLY the
sms_gateway_settings table. The module owns a single revision
(smg_0001), so the branch-scoped downgrade target is
``sms_gateway@-1``. Marked ``alembic_roundtrip``.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

import asyncpg
import pytest

from app.config import settings
from tests.modules._roundtrip_depends import dependent_tables

pytestmark = pytest.mark.alembic_roundtrip

BACKEND_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"

SMS_TABLES = {"sms_gateway_settings"}
SMS_HEAD = "smg_0001"


def _alembic(*args: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(ALEMBIC_INI), *args],
        cwd=BACKEND_ROOT,
        check=True,
    )


def _dsn() -> str:
    return settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


async def _list_tables_async() -> set[str]:
    conn = await asyncpg.connect(_dsn())
    try:
        rows = await conn.fetch(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name != 'alembic_version'"
        )
        return {row["table_name"] for row in rows}
    finally:
        await conn.close()


def _list_tables() -> set[str]:
    return asyncio.run(_list_tables_async())


def test_sms_gateway_uninstall_roundtrip_is_branch_scoped() -> None:
    _alembic("upgrade", "heads")
    before = _list_tables()
    assert SMS_TABLES.issubset(before), "sms_gateway tables missing after upgrade"

    _alembic("downgrade", "sms_gateway@-1")
    after_down = _list_tables()
    assert SMS_TABLES.isdisjoint(after_down), "sms_gateway tables still present after downgrade"

    expected_gone = SMS_TABLES | dependent_tables(SMS_HEAD)
    baseline = before - expected_gone
    assert baseline <= after_down, (
        f"downgrade leaked beyond sms_gateway branch (missing: {baseline - after_down})"
    )

    _alembic("upgrade", "heads")
    after_up = _list_tables()
    assert SMS_TABLES.issubset(after_up), "sms_gateway tables missing after re-upgrade"
    assert before == after_up, "round-trip left schema in a different state"
