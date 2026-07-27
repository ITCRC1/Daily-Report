"""Motor de auditoría Simphony POS (sub-tab 2.9) — portado de reference/auditoria.py.

Dos tipos de chequeo:
(a) Consistencia INTERNA del propio Excel de Ventas (entre sus hojas) — no
    depende de Opera/Integrity, así que se puede validar con cualquier día.
(b) Comparación contra Opera/Integrity (calculada en el service, con DB) —
    control de cajeros: lo que Simphony vendió en F&B debe terminar posteado
    en el PMS/contabilidad.

Todo lo que no cuadre (fuera de tolerancia) es un hallazgo (§10 — nunca queda
una excepción visible solo en una pantalla).
"""
from __future__ import annotations

TOL = 0.01


def _check(label: str, a: float, b: float, tol: float = TOL) -> dict:
    dif = round(a - b, 2)
    return {"concepto": label, "a": round(a, 2), "b": round(b, 2),
            "diferencia": dif, "estado": "OK" if abs(dif) < tol else "DISCREPANCIA"}


def pos_internal_checks(summary: dict, checks: list[dict]) -> list[dict]:
    """Consistencia entre las hojas del propio Excel de Ventas:
    - Ventas Netas + Cargos de Servicio == Total Ventas del Día (Resumen Ejecutivo).
    - Suma del Detalle de Checks == Total Ventas del Día.
    - Room Charge (forma de pago, Detalle de Checks) == Room Charge confirmado
      (hoja Mapeo Simphony → Opera).
    """
    ventas_netas = float(summary.get("ventas_netas", 0))
    sc = float(summary.get("cargos_servicio", 0))
    total_ventas = float(summary.get("total_ventas", 0))
    room_charge_confirmado = float(summary.get("room_charge_confirmado", 0))

    detalle_total = round(sum(c["monto"] for c in checks), 2)
    room_charge_pago = round(sum(c["monto"] for c in checks if c["is_room_charge"]), 2)

    return [
        _check("Ventas Netas + Cargos Servicio vs Total Ventas", ventas_netas + sc, total_ventas),
        _check("Suma Detalle de Checks vs Total Ventas", detalle_total, total_ventas),
        _check("Room Charge (forma de pago) vs Mapeo Simphony→Opera",
               room_charge_pago, room_charge_confirmado),
    ]


def pos_vs_pms_check(total_ventas: float, opera_fb: float, integrity_fb: float) -> dict:
    """Control de cajeros (§5.6): lo vendido en Simphony debe reflejarse en el
    F&B posteado en Opera/Integrity. `opera_fb`/`integrity_fb` se derivan de la
    MISMA clasificación por naturaleza ya usada en engine/revenue.py (§5.1a) —
    no es una regla nueva."""
    return {
        "pos_total_ventas": round(total_ventas, 2),
        "opera_recon": _check("POS Total Ventas vs Opera F&B", total_ventas, opera_fb),
        "integrity_recon": _check("POS Total Ventas vs Integrity F&B", total_ventas, integrity_fb),
    }
