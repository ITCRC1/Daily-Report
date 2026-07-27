"""Helpers compartidos para leer una cuenta puente/suspensa de Integrity por
NOMBRE exacto, agrupada por día -- créditos y débitos por separado.

Reusado por deposit_ledger_service (cuenta "ADELANTO HPDS LODGING"),
tips_service (cuenta "TIPS - PAYABLE") e iva_service (cuenta "VAT - CREDITS
(IVA DEVENGADO - INGRESOS) - 13%") -- mismo patrón en los tres: una cuenta
única identificada por su nombre real, verificada contra producción, sin
inventar categorías. Extraído a un módulo propio para no repetir la misma
consulta tres veces (la lección del refactor de `uploads_root()`: cuando el
mismo cálculo se copia a mano en varios servicios, tarde o temprano se
desincroniza)."""
from __future__ import annotations

from datetime import date as date_cls

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import IntegrityLine


async def ingested_dates(session: AsyncSession, pid, start: date_cls, end: date_cls) -> set[date_cls]:
    """Días con CUALQUIER renglón de Integrity en el rango (ya auditados)."""
    rows = (await session.execute(
        select(IntegrityLine.business_date).where(
            IntegrityLine.property_id == pid,
            IntegrityLine.business_date >= start, IntegrityLine.business_date <= end,
        ).distinct()
    )).scalars().all()
    return set(rows)


async def account_by_date(session: AsyncSession, pid, account_name: str, start: date_cls,
                          end: date_cls) -> dict[date_cls, tuple[float, float, float, float]]:
    """{fecha: (credito_usd, debito_usd, credito_crc, debito_crc)} para una
    cuenta por nombre exacto, agrupado por día en un solo query."""
    rows = (await session.execute(
        select(
            IntegrityLine.business_date,
            func.coalesce(func.sum(IntegrityLine.cred_usd), 0),
            func.coalesce(func.sum(IntegrityLine.deb_usd), 0),
            func.coalesce(func.sum(IntegrityLine.cred_col), 0),
            func.coalesce(func.sum(IntegrityLine.deb_col), 0),
        ).where(
            IntegrityLine.property_id == pid,
            IntegrityLine.business_date >= start, IntegrityLine.business_date <= end,
            IntegrityLine.nombre_cuenta == account_name,
        ).group_by(IntegrityLine.business_date)
    )).all()
    return {r[0]: (float(r[1]), float(r[2]), float(r[3]), float(r[4])) for r in rows}
