"""Parámetros del sistema editables por propiedad (Tab 6.9).

Externaliza constantes que antes vivían hardcodeadas en el código de los
servicios de reporte (nombres de cuenta de Integrity, porcentajes, etc.). El
riesgo que resuelve: si Bismark renombra una cuenta en el GL de Integrity, el
reporte dejaba de encontrarla y devolvía 0 en silencio -- ahora se corrige
desde la UI sin re-deploy.

Modelo "override-only": la fila en `app_config` SOLO existe si alguien cambió
el valor. Si no existe, `get_param` devuelve el `default` (= el valor histórico
hardcodeado) -> el comportamiento es idéntico al de antes hasta que alguien lo
edite. `reset` borra la fila y vuelve al default.

Allowlist estricta (`PARAM_DEFS`): solo estas keys se pueden leer/escribir por
acá. `gate_hard`/`gate_min_set` NO están (son decisiones de flujo, no
parámetros de cuenta -- se dejan fuera a propósito).
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AppConfig, Property

# type: "text" (string no vacío) | "number" (float) | "int" (entero)
PARAM_DEFS: list[dict] = [
    {
        "key": "iva_account_name", "type": "text",
        "default": "VAT - CREDITS (IVA DEVENGADO - INGRESOS) - 13%",
        "label": "Cuenta IVA 13% (Integrity)", "group": "Cuentas Integrity",
        "affects": "Tab 7.7 IVA",
        "help": "Nombre EXACTO de la cuenta de IVA devengado en Integrity. Si Bismark la renombra, cambiarlo aqui.",
    },
    {
        "key": "deposit_suspense_account_name", "type": "text",
        "default": "ADELANTO HPDS LODGING",
        "label": "Cuenta Adelantos/Depositos (Integrity)", "group": "Cuentas Integrity",
        "affects": "Tab 7.5 Deposit Ledger",
        "help": "Cuenta puente de adelantos de huespedes en Integrity.",
    },
    {
        "key": "tips_service_charge_account_name", "type": "text",
        "default": "10% SERVICE CHARGE",
        "label": "Cuenta Cargo Servicio 10% (Integrity)", "group": "Cuentas Integrity",
        "affects": "Tab 7.6.1 Tip 10%",
        "help": "Cuenta del cargo por servicio obligatorio 10% en Integrity.",
    },
    {
        "key": "tips_extra_account_name", "type": "text",
        "default": "TIPS - PAYABLE",
        "label": "Cuenta Propinas Extra (Integrity)", "group": "Cuentas Integrity",
        "affects": "Tab 7.6.2 Extra Tips",
        "help": "Cuenta de propinas por pagar (extra) en Integrity.",
    },
    {
        "key": "ontb_sales_on_property_pct", "type": "number",
        "default": "0.126",
        "label": "Sales on Property % (On The Books)", "group": "On The Books",
        "affects": "Tab 8 NET GAP",
        "help": "Fraccion del Forecast Rooms Only estimada como gasto en propiedad (formula F31 del Excel: 0.126 = 12.6%).",
    },
    {
        "key": "ontb_rooms_cost_center", "type": "text",
        "default": "0110",
        "label": "Cost center de Rooms", "group": "On The Books",
        "affects": "Tab 8 (linea Rooms)",
        "help": "Codigo del departamento Rooms (0110). Cambiar solo si el catalogo de departamentos cambia.",
    },
    {
        "key": "total_rooms", "type": "int",
        "default": "30",
        "label": "Habitaciones fisicas del hotel", "group": "Operacion",
        "affects": "Occupancy% / ADR (Tabs 3/4/8)",
        "help": "Los reportes SIEMPRE usan este numero, sin importar la disponibilidad que reporte Opera ese dia.",
    },
    {
        "key": "recon_tolerance", "type": "number",
        "default": "0.01",
        "label": "Tolerancia de reconciliacion ($)", "group": "Operacion",
        "affects": "Tab 2 Daily Audit",
        "help": "Diferencia maxima en dolares para considerar dos montos como iguales al reconciliar.",
    },
]

_BY_KEY = {p["key"]: p for p in PARAM_DEFS}


async def _property_id(session: AsyncSession, code: str):
    pid = (await session.execute(
        select(Property.id).where(Property.code == code)
    )).scalar_one_or_none()
    if pid is None:
        raise ValueError(f"Propiedad '{code}' no existe.")
    return pid


def _validate(defn: dict, value: str) -> str:
    """Valida/normaliza el valor segun el tipo. Devuelve el string a guardar."""
    v = (value or "").strip()
    if defn["type"] in ("number", "int"):
        try:
            num = float(v)
        except ValueError:
            raise ValueError(f"'{defn['label']}' debe ser numerico (recibido: '{value}').")
        if defn["type"] == "int":
            if num != int(num):
                raise ValueError(f"'{defn['label']}' debe ser un entero.")
            return str(int(num))
        return v
    # text
    if not v:
        raise ValueError(f"'{defn['label']}' no puede quedar vacio.")
    return v


async def get_param(session: AsyncSession, pid, key: str) -> str:
    """Valor efectivo del parametro: fila de app_config si existe, si no el default."""
    defn = _BY_KEY.get(key)
    if defn is None:
        raise ValueError(f"Parametro desconocido '{key}'.")
    row = (await session.execute(
        select(AppConfig).where(AppConfig.property_id == pid, AppConfig.key == key)
    )).scalar_one_or_none()
    return row.value if row is not None else defn["default"]


async def get_float(session: AsyncSession, pid, key: str) -> float:
    return float(await get_param(session, pid, key))


async def list_params(session: AsyncSession, property_code: str = "COWLCR") -> list[dict]:
    pid = await _property_id(session, property_code)
    rows = (await session.execute(
        select(AppConfig).where(AppConfig.property_id == pid)
    )).scalars().all()
    overrides = {r.key: r.value for r in rows}
    out = []
    for defn in PARAM_DEFS:
        k = defn["key"]
        is_override = k in overrides
        out.append({
            "key": k,
            "label": defn["label"],
            "group": defn["group"],
            "affects": defn["affects"],
            "help": defn["help"],
            "type": defn["type"],
            "default": defn["default"],
            "value": overrides[k] if is_override else defn["default"],
            "is_default": not is_override,
        })
    return out


async def set_param(session: AsyncSession, key: str, value: str,
                    property_code: str = "COWLCR") -> dict:
    defn = _BY_KEY.get(key)
    if defn is None:
        raise ValueError(f"Parametro desconocido '{key}'.")
    clean = _validate(defn, value)
    pid = await _property_id(session, property_code)
    row = (await session.execute(
        select(AppConfig).where(AppConfig.property_id == pid, AppConfig.key == key)
    )).scalar_one_or_none()
    if row is None:
        row = AppConfig(property_id=pid, key=key, value=clean)
        session.add(row)
    else:
        row.value = clean
    await session.commit()
    return {"key": key, "value": clean, "is_default": clean == defn["default"]}


async def reset_param(session: AsyncSession, key: str,
                      property_code: str = "COWLCR") -> dict:
    """Borra el override -> vuelve al default (valor historico hardcodeado)."""
    defn = _BY_KEY.get(key)
    if defn is None:
        raise ValueError(f"Parametro desconocido '{key}'.")
    pid = await _property_id(session, property_code)
    row = (await session.execute(
        select(AppConfig).where(AppConfig.property_id == pid, AppConfig.key == key)
    )).scalar_one_or_none()
    if row is not None:
        await session.delete(row)
        await session.commit()
    return {"key": key, "value": defn["default"], "is_default": True}
