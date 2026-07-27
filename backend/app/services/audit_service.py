"""Auditoría: reconcilia lo persistido (Opera vs Integrity) y guarda audit_run/findings."""
from __future__ import annotations

import uuid as uuid_mod
from datetime import date as date_cls
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.gate import evaluate_gate
from app.engine.pos_recon import pos_internal_checks, pos_vs_pms_check
from app.engine.reconcile import TOL, recon_kpis, reconcile
from app.engine.revenue import FB_NATURE, daily_revenue, lines_from_integrity
from app.engine.room_stats import NON_REVENUE_MARKET_CODES
from app.ingest.integrity import aggregate_lines
from app.ingest.opera import OperaHeader
from app.models import (
    AppConfig,
    AuditFinding,
    AuditRun,
    IntegrityLine,
    MarketCode,
    OccupancyStat,
    OperaTxn,
    OperaTxnDetail,
    Otb,
    PosCheck,
    PosSummary,
    Property,
    RoomCategory,
    RoomStat,
    TrialBalanceLine,
)


async def _property_id(session: AsyncSession, code: str):
    pid = (await session.execute(
        select(Property.id).where(Property.code == code)
    )).scalar_one_or_none()
    if pid is None:
        raise ValueError(f"Propiedad '{code}' no existe.")
    return pid


async def _load_from_db(session: AsyncSession, pid, bdate):
    """Reconstruye headers de Opera y agregado de Integrity desde la base."""
    op_rows = (await session.execute(
        select(OperaTxn).where(OperaTxn.property_id == pid, OperaTxn.business_date == bdate)
    )).scalars().all()
    headers = [OperaHeader(
        tcode=o.tcode, description=o.description or "", type=o.type,
        total=float(o.total), guest_ledger=float(o.guest_ledger),
        package_ledger=float(o.package_ledger), ar_ledger=float(o.ar_ledger),
        deposit_ledger=float(o.deposit_ledger),
    ) for o in op_rows]

    lines = (await session.execute(
        select(IntegrityLine).where(
            IntegrityLine.property_id == pid, IntegrityLine.business_date == bdate
        )
    )).scalars().all()
    integ = aggregate_lines([{
        "tcode": ln.tcode,
        "cred_usd": float(ln.cred_usd), "deb_usd": float(ln.deb_usd),
        "cuenta": ln.cuenta, "nombre_cuenta": ln.nombre_cuenta, "tc": ln.tc,
    } for ln in lines])
    return headers, integ


def _rows_payload(rows) -> list[dict]:
    return [{
        "tcode": r.tcode, "description": r.description, "type": r.type,
        "categoria": r.categoria, "opera": r.opera, "integrity": r.integrity,
        "diferencia": r.diferencia, "estado": r.estado,
        "cuenta": r.cuenta, "nombre": r.nombre,
    } for r in rows]


async def _upsert_finding(session, pid, business_date, *, source_view, area, tcode=None,
                          monto, tipo_desviacion, comentario, generated_keys: set[str] | None = None) -> None:
    """Upsert por (property, día, dedupe_key) -- NUNCA pisa `estado`/`resolved_note`/
    `resolved_at` de un hallazgo ya existente (§10: re-correr "Ingerir + Auditar" no
    puede borrar una decisión ya tomada por el usuario en 2.10).

    `generated_keys`: si se pasa, acumula el dedupe_key acá -- lo usa `run_audit`
    para despues borrar hallazgos de ese día/vista que YA NO se reproducen (ej. un
    bug de cálculo que se corrigió) -- de lo contrario quedan huérfanos para
    siempre, nunca se limpian solos (§ hallazgo real 2026-07-02: OTB post-fix)."""
    dedupe_key = f"{source_view or ''}|{area or ''}|{tcode or ''}|{tipo_desviacion or ''}"
    if generated_keys is not None:
        generated_keys.add(dedupe_key)
    await session.execute(
        pg_insert(AuditFinding)
        .values(
            property_id=pid, business_date=business_date, source_view=source_view,
            area=area, tcode=tcode, monto=monto, tipo_desviacion=tipo_desviacion,
            estado="abierto", comentario=comentario, dedupe_key=dedupe_key,
        )
        .on_conflict_do_update(
            index_elements=["property_id", "business_date", "dedupe_key"],
            set_={"monto": monto, "comentario": comentario, "tipo_desviacion": tipo_desviacion},
        )
    )


async def _cleanup_stale_findings(session, pid, business_date, managed_views: set[str],
                                  generated_keys: set[str]) -> None:
    """Borra hallazgos de `business_date` en las vistas de `managed_views` que NO
    se generaron en esta corrida -- ya no se reproducen (bug corregido, dato
    cambió), no tiene sentido dejarlos abiertos para siempre. Solo se incluyen acá
    las vistas cuyo insumo del día SÍ está disponible en esta corrida (si el
    insumo falta, la ausencia de hallazgos no significa que se haya arreglado)."""
    if not managed_views:
        return
    existing = (await session.execute(
        select(AuditFinding).where(
            AuditFinding.property_id == pid, AuditFinding.business_date == business_date,
            AuditFinding.source_view.in_(managed_views),
        )
    )).scalars().all()
    for f in existing:
        if f.dedupe_key not in generated_keys:
            await session.delete(f)


async def run_audit(session: AsyncSession, business_date: date_cls,
                    property_code: str = "COWLCR") -> dict:
    """Corre la reconciliación, persiste audit_run (KPIs) y audit_findings (excepciones)."""
    pid = await _property_id(session, property_code)
    headers, integ = await _load_from_db(session, pid, business_date)
    rows = reconcile(headers, integ)
    kpis = recon_kpis(rows)
    now = datetime.now(timezone.utc)

    await session.execute(
        pg_insert(AuditRun)
        .values(
            property_id=pid, business_date=business_date, status="abierto",
            kpi_ok=kpis["ok"], kpi_discrepancia=kpis["discrepancia"],
            kpi_faltante=kpis["faltante"], generated_at=now,
        )
        .on_conflict_do_update(
            index_elements=["property_id", "business_date"],
            set_={"kpi_ok": kpis["ok"], "kpi_discrepancia": kpis["discrepancia"],
                  "kpi_faltante": kpis["faltante"], "generated_at": now},
        )
    )

    # generated_keys acumula todo dedupe_key producido en esta corrida -- al
    # final se usa para borrar hallazgos de estas mismas vistas que YA NO
    # aparecen (ver `_cleanup_stale_findings`), así un bug corregido o un dato
    # que cambió no deja hallazgos huérfanos para siempre.
    generated_keys: set[str] = set()

    # findings = excepciones (discrepancia / faltante). Upsert por dedupe_key --
    # preserva estado/resolved_note si el usuario ya lo cambió en 2.10 (§10).
    for r in rows:
        if r.estado in ("DISCREPANCIA", "FALTA EN INTEGRITY", "FALTA EN OPERA"):
            await _upsert_finding(
                session, pid, business_date, source_view="Reconciliacion",
                area=r.categoria, tcode=r.tcode, monto=r.diferencia or 0,
                tipo_desviacion=r.estado,
                comentario=f"{r.description} | Opera={r.opera} Integrity={r.integrity}",
                generated_keys=generated_keys,
            )

    # 2.5 OTB vs Revenue: todo lo que no cuadre (✓) también es un hallazgo (§10 — nunca
    # queda una excepción visible solo en una pantalla, tiene que estar en 2.10).
    otb = await _otb_vs_revenue(session, pid, business_date)
    for label, recon in (("Full Revenue (OTB)", otb["full_revenue_recon"]),
                        ("Rooms Only (OTB)", otb["rooms_only_recon"])):
        if recon and recon["estado"] != "OK":
            await _upsert_finding(
                session, pid, business_date, source_view="OTB vs Revenue",
                area=label, tipo_desviacion=recon["estado"], monto=recon["diferencia"],
                comentario=f"OTB={recon['otb']} Integrity={recon['actual_integrity']}",
                generated_keys=generated_keys,
            )
    for f in _otb_concept_findings(otb["rooms"], otb["actual_stats"]):
        await _upsert_finding(
            session, pid, business_date, source_view="OTB vs Revenue",
            area=f["concepto"], tipo_desviacion="DIF_OPERATIVA", monto=f["diferencia"],
            comentario=f"OTB={f['otb']} Real={f['real']}",
            generated_keys=generated_keys,
        )

    # Inventario disponible: el hotel SIEMPRE tiene 30 habitaciones (§Bismark,
    # confirmado) -- si Opera reporta menos ese día (fact_room_stat con menos
    # categorías activas), NO se ajusta el número reportado (Occupancy%/ADR
    # siguen usando 30), pero la diferencia real queda como hallazgo a revisar.
    actual_stats = otb.get("actual_stats") or {}
    real_opera = actual_stats.get("available_real_opera")
    total_rooms = await _total_rooms_config(session, pid)
    if real_opera is not None and real_opera != total_rooms:
        await _upsert_finding(
            session, pid, business_date, source_view="Inventario Disponible",
            area="Habitaciones físicas reportadas por Opera", tipo_desviacion="DIF_OPERATIVA",
            monto=round(real_opera - total_rooms, 2),
            comentario=f"Opera reportó {real_opera} habitaciones activas ese día, "
                      f"pero los reportes siempre usan {total_rooms} (fijo, confirmado por el owner).",
            generated_keys=generated_keys,
        )

    # 2.9 Simphony POS: consistencia interna + control de cajeros vs Opera/Integrity.
    # None si no hay POS cargado ese día (no aplica, no es una excepción).
    pos = await _pos_audit(session, pid, business_date)
    if pos:
        for chk in pos["internal_checks"]:
            if chk["estado"] != "OK":
                await _upsert_finding(
                    session, pid, business_date, source_view="Simphony POS",
                    area=chk["concepto"], tipo_desviacion=chk["estado"], monto=chk["diferencia"],
                    comentario=f"A={chk['a']} B={chk['b']}",
                    generated_keys=generated_keys,
                )
        pms = pos["pms_check"] or {}
        for label, recon in (("POS vs Opera F&B", pms.get("opera_recon")),
                            ("POS vs Integrity F&B", pms.get("integrity_recon"))):
            if recon and recon["estado"] != "OK":
                await _upsert_finding(
                    session, pid, business_date, source_view="Simphony POS",
                    area=label, tipo_desviacion=recon["estado"], monto=recon["diferencia"],
                    comentario=f"POS={recon['a']} PMS={recon['b']}",
                    generated_keys=generated_keys,
                )

    # Opera Daily (Integrity + STATISTICS) vs Opera History (statroomtype), por
    # categoría de habitación (Tab 3.1). Integrity/STATISTICS es SIEMPRE la
    # fuente correcta (confirmado) -- cualquier diferencia contra statroomtype
    # es un hallazgo a revisar, nunca se descarta en silencio (§10).
    from app.services import revenue_service
    opera_val = await revenue_service.opera_validation_report(session, business_date, property_code=property_code)
    for row in (opera_val["rows"] if opera_val["has_history_data"] else []):
        if row["rn_diff"] != 0:
            await _upsert_finding(
                session, pid, business_date, source_view="Opera Daily vs History",
                area=f"{row['category']} — RN", tipo_desviacion="DISCREPANCIA", monto=row["rn_diff"],
                comentario=f"Daily (Integrity/STATISTICS, oficial)={row['rn_daily']} vs History (statroomtype)={row['rn_history']}",
                generated_keys=generated_keys,
            )
        if row["pax_diff"] != 0:
            await _upsert_finding(
                session, pid, business_date, source_view="Opera Daily vs History",
                area=f"{row['category']} — Pax", tipo_desviacion="DISCREPANCIA", monto=row["pax_diff"],
                comentario=f"Daily (Integrity/STATISTICS, oficial)={row['pax_daily']} vs History (statroomtype)={row['pax_history']}",
                generated_keys=generated_keys,
            )
        if row["revenue_diff"] != 0:
            await _upsert_finding(
                session, pid, business_date, source_view="Opera Daily vs History",
                area=f"{row['category']} — Revenue", tipo_desviacion="DISCREPANCIA", monto=row["revenue_diff"],
                comentario=f"Daily (Integrity, oficial)={row['revenue_daily']} vs History (statroomtype)={row['revenue_history']}",
                generated_keys=generated_keys,
            )

    # Limpieza de hallazgos que ya no se reproducen -- solo en las vistas cuyo
    # insumo del día SÍ estuvo disponible en esta corrida (si el insumo falta,
    # la ausencia de hallazgos no significa "se arregló", significa "no hay dato").
    managed_views = {"Reconciliacion", "OTB vs Revenue", "Inventario Disponible"}
    if pos:
        managed_views.add("Simphony POS")
    if opera_val["has_history_data"]:
        managed_views.add("Opera Daily vs History")
    await _cleanup_stale_findings(session, pid, business_date, managed_views, generated_keys)

    await session.commit()

    return {"business_date": business_date.isoformat(), "property": property_code,
            "kpis": kpis, "rows": _rows_payload(rows)}


def _as_uuid(value) -> uuid_mod.UUID | None:
    """Auth de usuarios aún no está wireada (sin login) — acepta un UUID de
    app_user si viene, o None. Un string no-UUID se ignora en vez de romper."""
    if not value:
        return None
    try:
        return uuid_mod.UUID(str(value))
    except ValueError:
        return None


async def _gate_hard(session: AsyncSession, pid) -> bool:
    row = (await session.execute(
        select(AppConfig).where(AppConfig.property_id == pid, AppConfig.key == "gate_hard")
    )).scalar_one_or_none()
    return (row.value if row else "false").strip().lower() == "true"


async def release_day(session: AsyncSession, business_date: date_cls, property_code: str = "COWLCR",
                      released_by=None, override_flag: bool = False, override_note: str | None = None) -> dict:
    """Libera el daily a dueños (§2.6/§2.7). Bloquea según gate_hard salvo override."""
    pid = await _property_id(session, property_code)
    run = (await session.execute(
        select(AuditRun).where(AuditRun.property_id == pid, AuditRun.business_date == business_date)
    )).scalar_one_or_none()
    if run is None:
        raise ValueError(f"No hay auditoría para '{business_date}' — corré la ingesta primero.")
    if override_flag and not (override_note or "").strip():
        raise ValueError("override_flag requiere override_note (no puede estar vacío).")

    gate_hard = await _gate_hard(session, pid)
    gate = evaluate_gate(run.kpi_discrepancia, run.kpi_faltante, gate_hard, override_flag)
    if not gate.allowed:
        raise ValueError(gate.reason)

    now = datetime.now(timezone.utc)
    run.status = "cerrado"
    run.released_at = now
    run.released_by = _as_uuid(released_by)
    run.override_flag = override_flag
    run.override_note = override_note
    await session.commit()

    return {"business_date": business_date.isoformat(), "status": run.status,
            "released_at": run.released_at.isoformat(), "gate": {"gate_hard": gate_hard,
            "allowed": gate.allowed, "reason": gate.reason, "open_issues": gate.open_issues}}


async def reopen_day(session: AsyncSession, business_date: date_cls, property_code: str = "COWLCR",
                     reopen_note: str | None = None) -> dict:
    """Reabre un daily ya liberado (vuelve a 'abierto') -- antes no existía
    ninguna forma de deshacer 'Liberar a dueños' desde la UI (§ reportado por
    el usuario). No border a los datos ya cargados/auditados, solo el estado
    de liberación -- para corregir algo hay que volver a 'Ingerir + Auditar'
    después de reabrir."""
    pid = await _property_id(session, property_code)
    run = (await session.execute(
        select(AuditRun).where(AuditRun.property_id == pid, AuditRun.business_date == business_date)
    )).scalar_one_or_none()
    if run is None:
        raise ValueError(f"No hay auditoría para '{business_date}'.")
    if run.status != "cerrado":
        raise ValueError(f"'{business_date}' no está liberado (status='{run.status}') -- nada que reabrir.")

    run.status = "abierto"
    run.released_at = None
    run.released_by = None
    run.override_flag = False
    run.override_note = (f"Reabierto: {reopen_note}" if reopen_note else "Reabierto sin nota.")
    await session.commit()

    return {"business_date": business_date.isoformat(), "status": run.status}


async def refresh_day(session: AsyncSession, business_date: date_cls, property_code: str = "COWLCR",
                      refreshed_by=None) -> dict:
    """REFRESH (§2.6): re-lee los insumos vigentes y recalcula (ingesta + auditoría),
    dejando traza. No cambia `status` — un 'cerrado' sigue cerrado tras refrescar."""
    from app.services import ingest_service

    pid = await _property_id(session, property_code)
    # Bug real corregido (2026-07-02): sin pasar `inputs_dir`, ingest_day() caía
    # al default de goldens/inputs (fixtures de test) en vez de uploads/inputs
    # (donde realmente quedan los archivos subidos por Tab 1) -- un refresh sobre
    # un día sin fixture de test hacía un "reemplazo total por 0 archivos", es
    # decir BORRABA los datos reales del día sin volver a cargar nada.
    uploads_dir = ingest_service.uploads_root() / business_date.isoformat()
    ingest_result = await ingest_service.ingest_day(
        session, business_date, property_code=property_code, inputs_dir=uploads_dir,
    )
    audit_result = await run_audit(session, business_date, property_code=property_code)

    run = (await session.execute(
        select(AuditRun).where(AuditRun.property_id == pid, AuditRun.business_date == business_date)
    )).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    run.refreshed_at = now
    run.refreshed_by = _as_uuid(refreshed_by)
    await session.commit()

    return {"business_date": business_date.isoformat(), "status": run.status,
            "refreshed_at": run.refreshed_at.isoformat(),
            "ingest_counts": ingest_result["counts"], "kpis": audit_result["kpis"]}


TYPE_ORDER = ["REVENUE", "NON REVENUE", "PAYMENT", "INTERNAL", "PACKAGE"]


def _category_summary(rows) -> list[dict]:
    """2.1 -- Opera vs Integrity by category (Revenue / Non-Revenue / Payments)."""
    out = []
    for cat in ("Revenue", "Non-Revenue", "Payments"):
        sub = [r for r in rows if r.categoria == cat]
        op = round(sum(r.opera or 0 for r in sub), 2)
        it = round(sum(r.integrity or 0 for r in sub), 2)
        out.append({"categoria": cat, "opera": op, "integrity": it,
                    "diferencia": round(it - op, 2)})
    return out


async def _trial_balance(session, pid, bdate) -> tuple[list[dict], dict, str]:
    """2.2/2.3 — trial balance por TCode con desglose de ledgers + totales.

    Fuente OFICIAL = fact_trial_balance (archivo OPERA_TrialBalance del día, más
    completo: incluye pagos/ajustes de todos los TRX_TYPE). Si ese archivo no se
    ingestó, cae al trial balance DERIVADO de fact_opera_txn (solo revenue)."""
    tb = (await session.execute(
        select(TrialBalanceLine).where(
            TrialBalanceLine.property_id == pid, TrialBalanceLine.business_date == bdate)
    )).scalars().all()
    if tb:
        rows = [{
            "tcode": t.tcode, "description": t.description, "type": t.trx_type,
            "total": float(t.tb_amount), "guest_ledger": float(t.guest_ledger),
            "package_ledger": float(t.package_ledger), "ar_ledger": float(t.ar_ledger),
            "deposit_ledger": float(t.deposit_ledger),
        } for t in tb]
        source = "Opera Trial Balance (official)"
    else:
        ops = (await session.execute(
            select(OperaTxn).where(OperaTxn.property_id == pid, OperaTxn.business_date == bdate)
        )).scalars().all()
        rows = [{
            "tcode": o.tcode, "description": o.description, "type": o.type,
            "total": float(o.total), "guest_ledger": float(o.guest_ledger),
            "package_ledger": float(o.package_ledger), "ar_ledger": float(o.ar_ledger),
            "deposit_ledger": float(o.deposit_ledger),
        } for o in ops]
        source = "Calculated from Opera transactions"
    rows.sort(key=lambda r: (TYPE_ORDER.index(r["type"]) if r["type"] in TYPE_ORDER else 99,
                             r["tcode"] or ""))
    ledgers = {
        "guest_ledger": round(sum(r["guest_ledger"] for r in rows), 2),
        "package_ledger": round(sum(r["package_ledger"] for r in rows), 2),
        "ar_ledger": round(sum(r["ar_ledger"] for r in rows), 2),
        "deposit_ledger": round(sum(r["deposit_ledger"] for r in rows), 2),
    }
    return rows, ledgers, source


async def _market_code_pivot(session, pid, bdate) -> dict:
    """2.6 — pivote Revenue × Market Code desde fact_opera_txn_detail."""
    dets = (await session.execute(
        select(OperaTxnDetail).where(
            OperaTxnDetail.property_id == pid, OperaTxnDetail.business_date == bdate,
            OperaTxnDetail.type == "REVENUE",
        )
    )).scalars().all()
    codes = sorted({d.market_code for d in dets if d.market_code})
    by_tc: dict[str, dict] = {}
    for d in dets:
        rec = by_tc.setdefault(d.tcode, {"tcode": d.tcode, "description": d.description,
                                         "values": {c: 0.0 for c in codes}})
        if d.market_code:
            rec["values"][d.market_code] += float(d.trx_amount)
    rows = []
    for rec in by_tc.values():
        rec["values"] = {c: round(v, 2) for c, v in rec["values"].items()}
        rec["total"] = round(sum(rec["values"].values()), 2)
        rows.append(rec)
    rows.sort(key=lambda r: r["tcode"])
    totals = {c: round(sum(r["values"][c] for r in rows), 2) for c in codes}
    return {"codes": codes, "rows": rows, "totals": totals}


async def _market_code_names(session, pid) -> dict[str, str]:
    rows = (await session.execute(
        select(MarketCode.code, MarketCode.name).where(MarketCode.property_id == pid)
    )).all()
    return {code: name for code, name in rows}


async def _room_class_names(session, pid) -> dict[str, str]:
    """room_class (FVR/FVR2/OVR/...) -> report_name (Corcovado Deluxe/...), vía dim_room_category."""
    rows = (await session.execute(
        select(RoomCategory.room_class, RoomCategory.report_name)
        .where(RoomCategory.property_id == pid, RoomCategory.room_class.is_not(None))
    )).all()
    return {room_class: report_name for room_class, report_name in rows}


async def _occupancy_stats(session, pid, bdate) -> dict:
    """2.4 — ocupación por market code / room class (fact_occupancy_stat, XML STATISTICS)."""
    recs = (await session.execute(
        select(OccupancyStat).where(
            OccupancyStat.property_id == pid, OccupancyStat.business_date == bdate
        ).order_by(OccupancyStat.market_code, OccupancyStat.room_class, OccupancyStat.room_type)
    )).scalars().all()

    market_names = await _market_code_names(session, pid)
    room_class_names = await _room_class_names(session, pid)

    records = [{
        "market_code": r.market_code, "market_name": market_names.get(r.market_code),
        "room_class": r.room_class, "room_class_name": room_class_names.get(r.room_class),
        "room_type": r.room_type,
        "rooms": r.rooms, "persons": r.persons,
        "noshow_rooms": r.noshow_rooms, "cancel_rooms": r.cancel_rooms,
    } for r in recs]

    name_lookup = {"market_code": market_names, "room_class": room_class_names}

    def _pivot(key: str) -> list[dict]:
        agg: dict[str, dict] = {}
        names = name_lookup[key]
        for r in records:
            k = r[key] or "—"
            a = agg.setdefault(k, {key: k, "name": names.get(k), "rooms": 0, "persons": 0,
                                   "noshow_rooms": 0, "cancel_rooms": 0})
            a["rooms"] += r["rooms"]; a["persons"] += r["persons"]
            a["noshow_rooms"] += r["noshow_rooms"]; a["cancel_rooms"] += r["cancel_rooms"]
        return sorted(agg.values(), key=lambda x: x[key])

    return {
        "records": records,
        "by_market": _pivot("market_code"),
        "by_room_class": _pivot("room_class"),
        "totals": {
            "rooms": sum(r["rooms"] for r in records),
            "persons": sum(r["persons"] for r in records),
            "noshow_rooms": sum(r["noshow_rooms"] for r in records),
            "cancel_rooms": sum(r["cancel_rooms"] for r in records),
        },
    }


async def _actual_revenue_pivot(session, pid, bdate) -> dict:
    """Revenue real del día desde Integrity (motor de la etapa 2), para reconciliar
    contra cada reporte OTB por separado — NO es el mismo cálculo que el OTB
    (que sale de Opera/history_forecast), son dos fuentes distintas (§5.6)."""
    rows = (await session.execute(
        select(IntegrityLine).where(
            IntegrityLine.property_id == pid, IntegrityLine.business_date == bdate,
        )
    )).scalars().all()
    lines = lines_from_integrity([{
        "cuenta": r.cuenta, "nombre_cuenta": r.nombre_cuenta,
        "cred_usd": r.cred_usd, "deb_usd": r.deb_usd,
    } for r in rows])
    p = daily_revenue(lines)
    return {
        "total_revenue": round(sum(p["columns"].values()) + p["otros_total"], 2),
        "room_revenue": p["columns"]["Rooms"],
    }


async def _total_rooms_config(session, pid) -> int:
    """Habitaciones físicas del hotel (app_config.total_rooms, default 30) --
    §Bismark confirmado: los reportes SIEMPRE usan este número, sin importar
    la disponibilidad que reporte Opera ese día (la diferencia real se
    documenta como hallazgo, no se esconde ni mueve el número reportado)."""
    row = (await session.execute(
        select(AppConfig).where(AppConfig.property_id == pid, AppConfig.key == "total_rooms")
    )).scalar_one_or_none()
    try:
        return int(row.value) if row else 30
    except (TypeError, ValueError):
        return 30


async def _actual_operational_stats(session, pid, bdate, room_revenue_integrity: float) -> dict:
    """Habitaciones/Pax/Disponibles reales del día. RN/Pax de fact_room_stat
    (única fuente posible, Integrity no tiene datos de habitaciones/ocupación).
    Disponibilidad = total_rooms fijo (§Bismark) si hubo ingesta ese día --
    NO la Σ physical_rooms real (esa diferencia se documenta como hallazgo
    aparte, ver `_upsert_finding` en run_audit, no afecta este número).

    El ADR SÍ usa el revenue de habitaciones que viene de Integrity
    (`room_revenue_integrity`, el mismo número ya reconciliado en rooms_only_recon),
    no el revenue del XML de Opera — a pedido del usuario, para que el ADR de esta
    fila sea consistente con la reconciliación de arriba."""
    rows = (await session.execute(
        select(RoomStat).where(RoomStat.property_id == pid, RoomStat.business_date == bdate)
    )).scalars().all()
    rn_gross = int(sum(r.stay_rooms for r in rows))
    pax_gross = int(sum(r.stay_persons for r in rows))
    available = await _total_rooms_config(session, pid) if rows else 0
    # Comps/in-house del día (market_code COM/INHOUSE del XML STATISTICS): se
    # RESTAN del RN/Pax para que el ADR y la ocupación mostrados sean de las
    # habitaciones que PAGAN (mismo criterio que §5.2 / Tab 6.6 / 7.3). Se
    # conservan las cifras BRUTAS (rn_gross/adr_gross) para la comparación OTB
    # vs Actual (2.5), que se compara contra el forecast de Opera que es bruto.
    comp_rows = (await session.execute(
        select(OccupancyStat).where(
            OccupancyStat.property_id == pid, OccupancyStat.business_date == bdate,
            OccupancyStat.market_code.in_(NON_REVENUE_MARKET_CODES),
        )
    )).scalars().all()
    comp_rn = int(sum(r.rooms or 0 for r in comp_rows))
    comp_pax = int(sum(r.persons or 0 for r in comp_rows))
    rn = max(rn_gross - comp_rn, 0)
    pax = max(pax_gross - comp_pax, 0)
    adr = round(room_revenue_integrity / rn, 2) if rn else 0.0
    occ = round(rn / available, 4) if available else 0.0
    adr_gross = round(room_revenue_integrity / rn_gross, 2) if rn_gross else 0.0
    occ_gross = round(rn_gross / available, 4) if available else 0.0
    return {"rn": rn, "pax": pax, "available": available, "adr": adr, "occupancy_pct": occ,
            "available_real_opera": int(sum(r.physical_rooms for r in rows)),
            "rn_gross": rn_gross, "pax_gross": pax_gross, "adr_gross": adr_gross,
            "occupancy_pct_gross": occ_gross}


def _otb_concept_findings(otb_rooms: dict | None, actual_stats: dict | None) -> list[dict]:
    """Compara OTB Rooms Only vs Real concepto por concepto (mismos 5 que la UI de 2.5) y
    devuelve solo los que NO cuadran — insumo para 2.10 Hallazgos."""
    if not otb_rooms or not actual_stats:
        return []
    # Compara contra las cifras BRUTAS del actual (el forecast OTB de Opera
    # incluye comps/house, no trae market_code para netear) -- apples-to-apples.
    checks = [
        ("Habitaciones (RN)", otb_rooms["no_rooms"], actual_stats.get("rn_gross", actual_stats["rn"]), 0.5),
        ("Personas (Pax)", otb_rooms["no_persons"], actual_stats.get("pax_gross", actual_stats["pax"]), 0.5),
        ("Inventario disponible", otb_rooms["inventory_rooms"], actual_stats["available"], 0.5),
        ("ADR", otb_rooms["adr"], actual_stats.get("adr_gross", actual_stats["adr"]), 0.01),
        ("Ocupación %", otb_rooms["occupancy"], actual_stats.get("occupancy_pct_gross", actual_stats["occupancy_pct"]) * 100, 0.05),
    ]
    out = []
    for concepto, otb_val, real_val, tol in checks:
        dif = round(real_val - otb_val, 2)
        if abs(dif) >= tol:
            out.append({"concepto": concepto, "otb": round(otb_val, 2),
                       "real": round(real_val, 2), "diferencia": dif})
    return out


def _otb_recon(otb_revenue: float | None, actual_revenue: float) -> dict | None:
    """Opera (OTB) vs Integrity (actual), mismo criterio de tolerancia que §5.4."""
    if otb_revenue is None:
        return None
    dif = round(actual_revenue - otb_revenue, 2)
    return {
        "otb": round(otb_revenue, 2), "actual_integrity": actual_revenue,
        "diferencia": dif, "estado": "OK" if abs(dif) < TOL else "DISCREPANCIA",
    }


async def _otb_vs_revenue(session, pid, bdate) -> dict:
    """2.5 — cada reporte OTB (Full Revenue y Rooms Only) es de naturaleza distinta y se
    reconcilia POR SEPARADO contra Integrity (Opera vs Integrity, §5.4) — no uno contra
    el otro. 'non_room_revenue' queda solo como dato informativo secundario."""
    rows = (await session.execute(
        select(Otb).where(Otb.property_id == pid, Otb.business_date == bdate)
    )).scalars().all()
    by_scope = {r.scope: {
        "revenue": float(r.revenue), "no_rooms": r.no_rooms, "no_persons": r.no_persons,
        "inventory_rooms": r.inventory_rooms, "adr": float(r.adr),
        "occupancy": float(r.occupancy), "source_file": r.source_file,
    } for r in rows}
    total, rooms = by_scope.get("total"), by_scope.get("rooms")
    non_room = (round(total["revenue"] - rooms["revenue"], 2)
                if total and rooms else None)

    actual = await _actual_revenue_pivot(session, pid, bdate)
    full_revenue_recon = _otb_recon(total["revenue"] if total else None, actual["total_revenue"])
    rooms_only_recon = _otb_recon(rooms["revenue"] if rooms else None, actual["room_revenue"])
    actual_stats = await _actual_operational_stats(session, pid, bdate, actual["room_revenue"])

    return {
        "total": total, "rooms": rooms, "non_room_revenue": non_room,
        "full_revenue_recon": full_revenue_recon,
        "rooms_only_recon": rooms_only_recon,
        "actual_stats": actual_stats,
    }


async def _opera_integrity_fb_totals(session, pid, bdate) -> dict:
    """F&B total desde Opera y desde Integrity, para comparar contra Simphony POS
    (control de cajeros, §5.6). El set de tcodes F&B se DERIVA de la clasificación
    por naturaleza 9-char ya usada en engine/revenue.py (§5.1a, FB_NATURE) — no es
    una regla nueva, es la misma que abre F&B en Food/Beverage/Misc en Tabs 3/4."""
    lines = (await session.execute(
        select(IntegrityLine).where(
            IntegrityLine.property_id == pid, IntegrityLine.business_date == bdate,
        )
    )).scalars().all()
    fb_natures = set(FB_NATURE.keys())
    fb_tcodes = {ln.tcode for ln in lines if ln.tcode and (ln.cuenta or "")[:4] in fb_natures}
    integrity_fb = round(sum(
        float(ln.cred_usd) - float(ln.deb_usd) for ln in lines if ln.tcode in fb_tcodes
    ), 2)

    opera_fb = 0.0
    if fb_tcodes:
        opera_rows = (await session.execute(
            select(OperaTxn).where(
                OperaTxn.property_id == pid, OperaTxn.business_date == bdate,
                OperaTxn.tcode.in_(fb_tcodes),
            )
        )).scalars().all()
        opera_fb = round(sum(float(o.total) for o in opera_rows), 2)

    return {"opera_fb": opera_fb, "integrity_fb": integrity_fb, "has_integrity_data": len(lines) > 0}


async def _pos_audit(session, pid, bdate) -> dict | None:
    """2.9 — Simphony POS: consistencia interna del Excel de Ventas + control de
    cajeros contra Opera/Integrity (§5.6). None si no hay POS cargado ese día."""
    summary_row = (await session.execute(
        select(PosSummary).where(PosSummary.property_id == pid, PosSummary.business_date == bdate)
    )).scalar_one_or_none()
    if summary_row is None:
        return None

    checks_rows = (await session.execute(
        select(PosCheck).where(PosCheck.property_id == pid, PosCheck.business_date == bdate)
    )).scalars().all()
    summary = {
        "ventas_netas": float(summary_row.ventas_netas), "cargos_servicio": float(summary_row.cargos_servicio),
        "total_ventas": float(summary_row.total_ventas), "voids": float(summary_row.voids),
        "room_charge_confirmado": float(summary_row.room_charge_confirmado),
        "source_file": summary_row.source_file,
    }
    checks = [{"monto": float(c.monto), "is_room_charge": c.is_room_charge} for c in checks_rows]

    internal_checks = pos_internal_checks(summary, checks)

    fb = await _opera_integrity_fb_totals(session, pid, bdate)
    # Sin datos de Integrity ese día, el "control de cajeros" no es aplicable —
    # comparar contra $0 daría una discrepancia falsa (no hay contra qué reconciliar).
    pms_check = (pos_vs_pms_check(summary["total_ventas"], fb["opera_fb"], fb["integrity_fb"])
                if fb["has_integrity_data"] else None)

    by_payment: dict[str, dict] = {}
    by_employee: dict[str, dict] = {}
    for c in checks_rows:
        key = c.forma_pago or "—"
        a = by_payment.setdefault(key, {"count": 0, "total": 0.0})
        a["count"] += 1; a["total"] += float(c.monto)
        key2 = c.employee or "—"
        b = by_employee.setdefault(key2, {"count": 0, "total": 0.0})
        b["count"] += 1; b["total"] += float(c.monto)

    room_charges = [{
        "restaurant": c.restaurant, "employee": c.employee, "check_num": c.check_num,
        "hora": c.hora, "monto": float(c.monto),
    } for c in checks_rows if c.is_room_charge]

    return {
        "summary": summary,
        "internal_checks": internal_checks,
        "pms_check": pms_check,
        "by_payment": [{"forma": k, **v} for k, v in sorted(by_payment.items(), key=lambda kv: -kv[1]["total"])],
        "by_employee": [{"empleado": k, **v} for k, v in sorted(by_employee.items(), key=lambda kv: -kv[1]["total"])],
        "room_charges": room_charges,
        "total_checks": len(checks_rows),
    }


def _finding_payload(f: AuditFinding) -> dict:
    return {
        "id": str(f.id), "business_date": f.business_date.isoformat(),
        "tcode": f.tcode, "area": f.area, "tipo_desviacion": f.tipo_desviacion,
        "monto": float(f.monto), "estado": f.estado, "comentario": f.comentario,
        "resolved_note": f.resolved_note,
        "resolved_at": f.resolved_at.isoformat() if f.resolved_at else None,
        "cobrar_empleado": f.cobrar_empleado, "persona": f.persona,
        "source_view": f.source_view,
    }


async def _findings(session, pid, bdate) -> list[dict]:
    """2.10 — hallazgos persistidos (audit_finding) de un día puntual."""
    fs = (await session.execute(
        select(AuditFinding).where(
            AuditFinding.property_id == pid, AuditFinding.business_date == bdate
        ).order_by(AuditFinding.tcode)
    )).scalars().all()
    return [_finding_payload(f) for f in fs]


async def list_findings(session: AsyncSession, property_code: str = "COWLCR",
                        estado: str | None = "abierto",
                        date_from: date_cls | None = None,
                        date_to: date_cls | None = None) -> list[dict]:
    """2.10 — acumulado Year to Date de hallazgos (no limitado a un solo día).

    Default: todos los hallazgos con estado='abierto' desde el 1-ene del año de
    `date_to` (o de hoy si no se especifica) hasta `date_to` — "year to date"
    de lo que sigue sin resolver. `estado=None` trae todos los estados."""
    pid = await _property_id(session, property_code)
    if date_to is None:
        date_to = date_cls.today()
    if date_from is None:
        date_from = date_to.replace(month=1, day=1)
    q = select(AuditFinding).where(
        AuditFinding.property_id == pid,
        AuditFinding.business_date >= date_from,
        AuditFinding.business_date <= date_to,
    )
    if estado:
        q = q.where(AuditFinding.estado == estado)
    fs = (await session.execute(
        q.order_by(AuditFinding.business_date.desc(), AuditFinding.tcode)
    )).scalars().all()
    return [_finding_payload(f) for f in fs]


async def update_finding(session: AsyncSession, finding_id: uuid_mod.UUID,
                         estado: str, resolved_note: str | None) -> dict:
    """Cambia estado + deja un comentario amplio (2.10) -- nunca se pisa con un
    re-run de auditoría, ver `_upsert_finding`."""
    if estado not in ("abierto", "cerrado"):
        raise ValueError(f"Estado inválido '{estado}' (debe ser 'abierto' o 'cerrado').")
    f = (await session.execute(
        select(AuditFinding).where(AuditFinding.id == finding_id)
    )).scalar_one_or_none()
    if f is None:
        raise ValueError(f"Hallazgo '{finding_id}' no existe.")
    f.estado = estado
    f.resolved_note = resolved_note
    f.resolved_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(f)
    return _finding_payload(f)


async def get_audit(session: AsyncSession, business_date: date_cls,
                    property_code: str = "COWLCR") -> dict:
    """Vista completa del Tab 2 (recomputa reconciliación + secciones por sub-tab)."""
    pid = await _property_id(session, property_code)
    run = (await session.execute(
        select(AuditRun).where(AuditRun.property_id == pid, AuditRun.business_date == business_date)
    )).scalar_one_or_none()
    headers, integ = await _load_from_db(session, pid, business_date)
    rows = reconcile(headers, integ)

    from app.services import ledger_service
    trial, _, trial_source = await _trial_balance(session, pid, business_date)
    ledgers = await ledger_service.balances_for_day(session, business_date, property_code)
    kpis = recon_kpis(rows)
    gate_hard = await _gate_hard(session, pid)
    gate_preview = evaluate_gate(kpis["discrepancia"], kpis["faltante"], gate_hard)
    return {
        "business_date": business_date.isoformat(),
        "property": property_code,
        "status": run.status if run else None,
        "generated_at": run.generated_at.isoformat() if run and run.generated_at else None,
        "released_at": run.released_at.isoformat() if run and run.released_at else None,
        "refreshed_at": run.refreshed_at.isoformat() if run and run.refreshed_at else None,
        "override_flag": run.override_flag if run else False,
        "override_note": run.override_note if run else None,
        "gate": {"gate_hard": gate_hard, "allowed": gate_preview.allowed,
                "reason": gate_preview.reason, "open_issues": gate_preview.open_issues},
        "kpis": kpis,
        "rows": _rows_payload(rows),                       # 2.7 / 2.8
        "category_summary": _category_summary(rows),        # 2.1
        "revenue_total": round(sum(h.total for h in headers if h.type == "REVENUE"), 2),
        "nonrev_total": round(sum(h.total for h in headers if h.type == "NON REVENUE"), 2),
        "payment_total": round(sum(h.total for h in headers if h.type == "PAYMENT"), 2),
        "trial_balance": trial,                             # 2.2
        "trial_balance_source": trial_source,               # 2.2
        "ledgers": ledgers,                                 # 2.3
        "occupancy": await _occupancy_stats(session, pid, business_date),      # 2.4
        "otb": await _otb_vs_revenue(session, pid, business_date),             # 2.5
        "market_code": await _market_code_pivot(session, pid, business_date),  # 2.6
        "pos": await _pos_audit(session, pid, business_date),                  # 2.9
        "findings": await _findings(session, pid, business_date),              # 2.10
    }
