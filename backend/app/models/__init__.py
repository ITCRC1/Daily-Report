"""Modelos ORM de DAILY-OPS (mapean el esquema de db/schema.sql).

La creación de tablas la hace la migración 0001 (ejecuta schema.sql), esta capa
es para consultar/escribir desde la app. Mantener en sync con schema.sql.
"""
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

UUIDpk = lambda: mapped_column(  # noqa: E731
    PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
)


def prop_fk() -> Mapped[uuid.UUID]:
    return mapped_column(PGUUID(as_uuid=True), ForeignKey("dim_property.id"), nullable=False, index=True)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------------- propiedad / usuarios ----------------
class Property(Base, TimestampMixin):
    __tablename__ = "dim_property"
    id: Mapped[uuid.UUID] = UUIDpk()
    code: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    hotel_code: Mapped[str | None] = mapped_column(Text)
    activa: Mapped[bool] = mapped_column(Boolean, server_default="true")


class Role(Base):
    __tablename__ = "role"
    id: Mapped[uuid.UUID] = UUIDpk()
    code: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)


class AppUser(Base, TimestampMixin):
    __tablename__ = "app_user"
    id: Mapped[uuid.UUID] = UUIDpk()
    email: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str | None] = mapped_column(Text)
    role_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("role.id"))
    password_hash: Mapped[str | None] = mapped_column(Text)
    activo: Mapped[bool] = mapped_column(Boolean, server_default="true")


# ---------------- dimensiones ----------------
class Department(Base, TimestampMixin):
    __tablename__ = "dim_department"
    __table_args__ = (UniqueConstraint("property_id", "cuenta_nature", "cost_center"),)
    id: Mapped[uuid.UUID] = UUIDpk()
    property_id: Mapped[uuid.UUID] = prop_fk()
    cuenta_nature: Mapped[str | None] = mapped_column(Text)
    cost_center: Mapped[str | None] = mapped_column(Text)
    outlet_name: Mapped[str | None] = mapped_column(Text)
    output_column: Mapped[str] = mapped_column(Text)


class RoomCategory(Base, TimestampMixin):
    __tablename__ = "dim_room_category"
    __table_args__ = (UniqueConstraint("property_id", "code2"),)
    id: Mapped[uuid.UUID] = UUIDpk()
    property_id: Mapped[uuid.UUID] = prop_fk()
    code2: Mapped[str] = mapped_column(Text)
    report_name: Mapped[str] = mapped_column(Text)
    opera_short_desc: Mapped[str | None] = mapped_column(Text)
    # room_class del XML STATISTICS (fact_occupancy_stat) -- FVR/FVR2/FVR3/FVR4/
    # OVR/OVR2, distinto de code2 (01-06). Ata la categoría a la ingesta oficial
    # (Tab 3.1 Opera Daily vs History, §5.2). CONFIRMADO por Bismark (no inferido).
    room_class: Mapped[str | None] = mapped_column(Text)
    # String de cuenta Integrity de referencia (ej. "4000-0110-003-001-001-15-01")
    # -- solo INFORMATIVO (Tab 6.7 Rooms Mapping). El string real de Integrity
    # varía por segmento de mercado (003/004/005/006/020…) y no matchea 1:1 con
    # este patrón simplificado -- no se usa para clasificar revenue por
    # categoría automáticamente, sería frágil (§10, no inventar un parser que
    # no es confiable).
    integrity_string: Mapped[str | None] = mapped_column(Text)
    units: Mapped[int | None] = mapped_column(Integer)


class PaymentMap(Base, TimestampMixin):
    __tablename__ = "dim_payment_map"
    __table_args__ = (UniqueConstraint("property_id", "transaction_code"),)
    id: Mapped[uuid.UUID] = UUIDpk()
    property_id: Mapped[uuid.UUID] = prop_fk()
    transaction_code: Mapped[str] = mapped_column(Text, index=True)
    code: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    banco_codigo: Mapped[str | None] = mapped_column(Text)
    banco_nombre: Mapped[str | None] = mapped_column(Text)
    moneda: Mapped[str | None] = mapped_column(Text)
    tipo_pago: Mapped[str | None] = mapped_column(Text)
    marca_metodo: Mapped[str | None] = mapped_column(Text)
    grupo: Mapped[str | None] = mapped_column(Text)
    cash_flow: Mapped[str | None] = mapped_column(Text)
    canal: Mapped[str | None] = mapped_column(Text)
    report_bucket: Mapped[str | None] = mapped_column(Text)


class MarketCode(Base, TimestampMixin):
    __tablename__ = "dim_market_code"
    __table_args__ = (UniqueConstraint("property_id", "code"),)
    id: Mapped[uuid.UUID] = UUIDpk()
    property_id: Mapped[uuid.UUID] = prop_fk()
    code: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    # Canal de negocio (§3.2 KPI, Tab 6.8) -- Travel Agent/Direct Client/
    # Website/OTA/INHOUSE. Editable; un código sin grupo cae en "Unmapped"
    # en el rollup (visible, §10 no se pierde en silencio).
    kpi_group: Mapped[str | None] = mapped_column(Text)


class OperaRevenueCat(Base, TimestampMixin):
    __tablename__ = "dim_opera_revenue_cat"
    __table_args__ = (UniqueConstraint("property_id", "tcode", "categoria"),)
    id: Mapped[uuid.UUID] = UUIDpk()
    property_id: Mapped[uuid.UUID] = prop_fk()
    tcode: Mapped[str] = mapped_column(Text, index=True)
    categoria: Mapped[str] = mapped_column(Text)


class Calendar(Base):
    __tablename__ = "dim_calendar"
    id: Mapped[uuid.UUID] = UUIDpk()
    date: Mapped[date] = mapped_column(Date, unique=True)
    iso_week: Mapped[int] = mapped_column(Integer)
    week_start: Mapped[date] = mapped_column(Date)
    week_end: Mapped[date] = mapped_column(Date)
    week_label: Mapped[str] = mapped_column(Text)
    month: Mapped[int] = mapped_column(Integer)
    year: Mapped[int] = mapped_column(Integer)


class WeekCalendar(Base, TimestampMixin):
    """Tab 6.10 -- cortes semanales EDITABLES, un registro por semana. Fuente de
    los rangos que usa Tab 4 (Weekly Revenue): resuelve la semana de una fecha
    por RANGO (week_start <= d <= week_end). Es una tabla APARTE de dim_calendar
    (por día) -- ambas coexisten (variantes de reporting, pedido del owner).
    `week_start`/`week_end` se editan a mano; `week_label` se re-deriva solo."""
    __tablename__ = "dim_week_calendar"
    __table_args__ = (UniqueConstraint("property_id", "week_start"),)
    id: Mapped[uuid.UUID] = UUIDpk()
    property_id: Mapped[uuid.UUID] = prop_fk()
    week_num: Mapped[int] = mapped_column(Integer)
    week_start: Mapped[date] = mapped_column(Date)
    week_end: Mapped[date] = mapped_column(Date)
    week_label: Mapped[str] = mapped_column(Text)


# ---------------- ingesta / control ----------------
class IngestBatch(Base):
    __tablename__ = "ingest_batch"
    id: Mapped[uuid.UUID] = UUIDpk()
    property_id: Mapped[uuid.UUID] = prop_fk()
    business_date: Mapped[date] = mapped_column(Date, index=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("app_user.id"))


class IngestDayStatus(Base):
    __tablename__ = "ingest_day_status"
    __table_args__ = (UniqueConstraint("property_id", "business_date", "sistema"),)
    id: Mapped[uuid.UUID] = UUIDpk()
    property_id: Mapped[uuid.UUID] = prop_fk()
    business_date: Mapped[date] = mapped_column(Date, index=True)
    sistema: Mapped[str] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(Text, server_default="Incompleto")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AppConfig(Base, TimestampMixin):
    __tablename__ = "app_config"
    __table_args__ = (UniqueConstraint("property_id", "key"),)
    id: Mapped[uuid.UUID] = UUIDpk()
    property_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("dim_property.id"))
    key: Mapped[str] = mapped_column(Text)
    value: Mapped[str] = mapped_column(Text)


# ---------------- staging ----------------
class IntegrityLine(Base):
    __tablename__ = "stg_integrity_line"
    id: Mapped[uuid.UUID] = UUIDpk()
    property_id: Mapped[uuid.UUID] = prop_fk()
    business_date: Mapped[date] = mapped_column(Date, index=True)
    source_file: Mapped[str | None] = mapped_column(Text)
    ingest_batch_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("ingest_batch.id"), index=True
    )
    cuenta: Mapped[str | None] = mapped_column(Text)
    nombre_cuenta: Mapped[str | None] = mapped_column(Text)
    centro_costo: Mapped[str | None] = mapped_column(Text)
    referencia: Mapped[str | None] = mapped_column(Text)
    detalle: Mapped[str | None] = mapped_column(Text)
    moneda_fuente: Mapped[str | None] = mapped_column(Text)
    tc: Mapped[Decimal | None] = mapped_column(Numeric(15, 6))
    deb_col: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    cred_col: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    deb_usd: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    cred_usd: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    tcode: Mapped[str | None] = mapped_column(Text, index=True)


# ---------------- hechos ----------------
class RoomStat(Base):
    __tablename__ = "fact_room_stat"
    id: Mapped[uuid.UUID] = UUIDpk()
    property_id: Mapped[uuid.UUID] = prop_fk()
    business_date: Mapped[date] = mapped_column(Date, index=True)
    room_category: Mapped[str | None] = mapped_column(Text)
    room_revenue: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    stay_rooms: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    stay_persons: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    physical_rooms: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")


class OccupancyStat(Base):
    """Registro del XML STATISTICS de Opera (ocupación por market/clase/tipo) — sub-tab 2.4."""
    __tablename__ = "fact_occupancy_stat"
    id: Mapped[uuid.UUID] = UUIDpk()
    property_id: Mapped[uuid.UUID] = prop_fk()
    business_date: Mapped[date] = mapped_column(Date, index=True)
    market_code: Mapped[str | None] = mapped_column(Text)
    room_class: Mapped[str | None] = mapped_column(Text)
    room_type: Mapped[str | None] = mapped_column(Text)
    rooms: Mapped[int] = mapped_column(Integer, server_default="0")
    persons: Mapped[int] = mapped_column(Integer, server_default="0")
    noshow_rooms: Mapped[int] = mapped_column(Integer, server_default="0")
    cancel_rooms: Mapped[int] = mapped_column(Integer, server_default="0")


class Otb(Base):
    """Snapshot history_forecast: scope='total' (HF full) vs 'rooms' (Rooms Only) — sub-tab 2.5 (§5.6)."""
    __tablename__ = "fact_otb"
    __table_args__ = (UniqueConstraint("property_id", "business_date", "scope"),)
    id: Mapped[uuid.UUID] = UUIDpk()
    property_id: Mapped[uuid.UUID] = prop_fk()
    business_date: Mapped[date] = mapped_column(Date, index=True)
    scope: Mapped[str] = mapped_column(Text)
    source_file: Mapped[str | None] = mapped_column(Text)
    revenue: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    no_rooms: Mapped[int] = mapped_column(Integer, server_default="0")
    no_persons: Mapped[int] = mapped_column(Integer, server_default="0")
    inventory_rooms: Mapped[int] = mapped_column(Integer, server_default="0")
    adr: Mapped[Decimal] = mapped_column(Numeric(15, 4), server_default="0")
    occupancy: Mapped[Decimal] = mapped_column(Numeric(9, 4), server_default="0")


class OtbMonthly(Base):
    """Agregado MENSUAL del history_forecast (año completo) por snapshot — On The
    Books (Tab 8). Cada ingesta guarda 12 filas (una por mes) con el OTB de ese
    día como corte. El reporte usa el snapshot más reciente; guardar por fecha
    permite el pacing semana-a-semana a futuro."""
    __tablename__ = "fact_otb_monthly"
    __table_args__ = (UniqueConstraint("property_id", "snapshot_date", "year", "month"),)
    id: Mapped[uuid.UUID] = UUIDpk()
    property_id: Mapped[uuid.UUID] = prop_fk()
    snapshot_date: Mapped[date] = mapped_column(Date, index=True)
    # Año calendario al que pertenece el mes (el history_forecast puede abarcar
    # >1 año: ej. un snapshot de jul-2026 con forecast hasta 2027). Sin esto, los
    # meses de 2026 y 2027 colapsarían en el mismo bucket 1-12.
    year: Mapped[int] = mapped_column(Integer, server_default="2026")
    month: Mapped[int] = mapped_column(Integer)
    total_revenue: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    rooms_only_revenue: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    rooms_only_history: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    rooms_only_forecast: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    rooms_occ: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    guests: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    rooms_avail: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")


class OtbDaily(Base):
    """Ocupación DIARIA del OTB por snapshot — heatmap (Tab 8.3). Rooms vendidas
    y disponibles por día del año, del history_forecast del snapshot."""
    __tablename__ = "fact_otb_daily"
    __table_args__ = (UniqueConstraint("property_id", "snapshot_date", "the_date"),)
    id: Mapped[uuid.UUID] = UUIDpk()
    property_id: Mapped[uuid.UUID] = prop_fk()
    snapshot_date: Mapped[date] = mapped_column(Date, index=True)
    the_date: Mapped[date] = mapped_column(Date)
    rooms_sold: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    rooms_avail: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")


class BudgetMonthly(Base, TimestampMixin):
    __tablename__ = "budget_monthly"
    __table_args__ = (CheckConstraint("month BETWEEN 1 AND 12"),)
    id: Mapped[uuid.UUID] = UUIDpk()
    property_id: Mapped[uuid.UUID] = prop_fk()
    year: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)
    dept_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("dim_department.id"))
    amount_usd: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    available_rooms: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    rooms_occupied: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    guests: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    occupancy_pct: Mapped[Decimal | None] = mapped_column(Numeric(9, 4))
    adr: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    food: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    beverage: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    misc: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")


class Budget(Base):
    __tablename__ = "fact_budget"
    id: Mapped[uuid.UUID] = UUIDpk()
    property_id: Mapped[uuid.UUID] = prop_fk()
    date: Mapped[date] = mapped_column(Date, index=True)
    dept_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("dim_department.id"))
    amount_usd: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")


class RoomStatOpening(Base, TimestampMixin):
    """Anclaje MANUAL editable del acumulado YTD por categoría de habitación
    (mismo patrón que LedgerOpening) -- Tab 6.6. `room_category` usa el mismo
    valor que `RoomStat.room_category` (short_description del XML statroomtype,
    ej. "Corcovado Deluxe"). YTD a cualquier día = este ancla (en `anchor_date`)
    + los días reales acumulados en fact_room_stat DESPUÉS de `anchor_date`.
    Un solo ancla vigente por categoría (no historial de re-anclajes, a
    diferencia de ledger_opening) -- se edita in place cuando Bismark corrige."""
    __tablename__ = "room_stat_opening"
    __table_args__ = (UniqueConstraint("property_id", "room_category"),)
    id: Mapped[uuid.UUID] = UUIDpk()
    property_id: Mapped[uuid.UUID] = prop_fk()
    room_category: Mapped[str] = mapped_column(Text)
    anchor_date: Mapped[date] = mapped_column(Date, index=True)
    revenue: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    stay_rooms: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    stay_persons: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    physical_rooms: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")


class CompStatMonthly(Base, TimestampMixin):
    """Comps/In-House HISTÓRICOS por (año, mes, categoría) -- Tab 7.8 "YTD June 30
    2026 Comps". Cargados del Excel del owner (STATISTIC DATA FOR ROOMS, tablas
    Complimentary por Room Nights y Pax-Nights). El acumulado Ene-Jun por tipo
    reconcilia con la línea Comps del ancla de Tab 6.6 (243 RN / 346 Pax) y sirve
    de SALDO DE ARRANQUE del daily de comps (Tab 7.9). `room_category` = mismo
    valor que RoomStat.room_category ("Corcovado Deluxe", etc.)."""
    __tablename__ = "comp_stat_monthly"
    __table_args__ = (UniqueConstraint("property_id", "year", "month", "room_category"),)
    id: Mapped[uuid.UUID] = UUIDpk()
    property_id: Mapped[uuid.UUID] = prop_fk()
    year: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)
    room_category: Mapped[str] = mapped_column(Text)
    rn: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    pax: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")


class MonthlyCashPosition(Base, TimestampMixin):
    """Tab 5.2 — Monthly Cash Position. Todas las líneas son EDITABLES (input
    manual del owner) EXCEPTO "MTD Cash collected from the Operation", que se
    calcula en vivo = Real Cash MTD del Tab 5 (cash_flow='Real Cash', no AR ni
    Non-Cash). Una fila por (property, year, month). Month Balance = opening +
    MTD real cash + other collections − Σ pagos (se computa, no se guarda)."""
    __tablename__ = "cash_monthly_position"
    __table_args__ = (UniqueConstraint("property_id", "year", "month"),)
    id: Mapped[uuid.UUID] = UUIDpk()
    property_id: Mapped[uuid.UUID] = prop_fk()
    year: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)
    opening: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    other_collections: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    pay_vendors: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    pay_capital: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    pay_payroll: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    pay_social_security: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    pay_ins: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    pay_hacienda: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    other_pay_1: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    other_pay_2: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    other_pay_3: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    other_pay_4: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    # Tasas de tarjeta para netear el "MTD Cash collected" (bruto -> neto).
    # En PORCENTAJE (2.5 = 2.5%). Aplican a los canales POS y Ecommerce.
    pos_commission_pct: Mapped[Decimal] = mapped_column(Numeric(6, 4), server_default="0")
    pos_retention_pct: Mapped[Decimal] = mapped_column(Numeric(6, 4), server_default="0")
    ecom_commission_pct: Mapped[Decimal] = mapped_column(Numeric(6, 4), server_default="0")
    ecom_retention_pct: Mapped[Decimal] = mapped_column(Numeric(6, 4), server_default="0")


class CashFlowForecast(Base, TimestampMixin):
    """Tab 5.2 (panel derecho) — Full Year Cash Flow Forecast por escenario
    (Current / April 2026 / Budget). Editable: `opening` = saldo al cierre de
    Dic del año anterior + `n1..n12` = Net Change in Cash de cada mes. Beginning
    y Ending Cash se derivan con roll-forward (no se guardan). Una fila por
    (property, year, scenario)."""
    __tablename__ = "cash_flow_forecast"
    __table_args__ = (UniqueConstraint("property_id", "year", "scenario"),)
    id: Mapped[uuid.UUID] = UUIDpk()
    property_id: Mapped[uuid.UUID] = prop_fk()
    year: Mapped[int] = mapped_column(Integer)
    scenario: Mapped[str] = mapped_column(Text)  # 'current' | 'april' | 'budget'
    opening: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    n1: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    n2: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    n3: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    n4: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    n5: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    n6: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    n7: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    n8: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    n9: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    n10: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    n11: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    n12: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    # Override editable del Beginning Cash de cada mes. NULL = usar roll-forward
    # (Ending del mes anterior). Si tiene valor, sobreescribe.
    b1: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    b2: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    b3: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    b4: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    b5: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    b6: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    b7: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    b8: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    b9: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    b10: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    b11: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    b12: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)


class DepositLedgerEntry(Base):
    """Tab 7.5 -- Deposit Ledger (Bank): un registro MANUAL por día de cuánto
    entra en depósito (banco) y cuánto se aplica ese día, para que el owner
    arme su propio cash flow. Sin relación con `OperaTxn.deposit_ledger`
    (ese es el ledger PMS de anticipos/depósitos de huéspedes, Tab 2.3 --
    concepto de negocio distinto). Ningún insumo de Daily-Ops trae este dato
    (decisión 2026-07-03: no va a haber feed bancario automático) -- 100%
    carga manual, un registro por fecha."""
    __tablename__ = "fact_deposit_ledger_daily"
    __table_args__ = (UniqueConstraint("property_id", "date"),)
    id: Mapped[uuid.UUID] = UUIDpk()
    property_id: Mapped[uuid.UUID] = prop_fk()
    date: Mapped[date] = mapped_column(Date, index=True)
    deposited_usd: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    applied_usd: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    note: Mapped[str | None] = mapped_column(Text)


class DepositLedgerOpening(Base, TimestampMixin):
    """Ancla MANUAL editable del saldo pendiente de aplicar a una fecha de
    corte (mismo patrón que RoomStatOpening/LedgerOpening) -- Tab 7.5. Saldo
    a cualquier fecha = este ancla (en `anchor_date`) + Σ(deposited-applied)
    de DepositLedgerEntry DESPUÉS de `anchor_date`. Un solo ancla por
    propiedad; queda sin fila hasta que el owner cargue el corte YTD-junio
    cuando pueda -- sin ancla, el saldo arranca en $0 desde la primera
    entrada real (julio 2026 en adelante)."""
    __tablename__ = "deposit_ledger_opening"
    __table_args__ = (UniqueConstraint("property_id"),)
    id: Mapped[uuid.UUID] = UUIDpk()
    property_id: Mapped[uuid.UUID] = prop_fk()
    anchor_date: Mapped[date] = mapped_column(Date, index=True)
    balance_usd: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    note: Mapped[str | None] = mapped_column(Text)


class TipsPayoutEntry(Base):
    """Tabs 7.6.1 (Tip 10%) y 7.6.2 (Extra Tips) -- cuánto se les PAGÓ a los
    empleados en gratuidades ese día, por tipo (`kind`). Carga MANUAL siempre
    -- el pago a empleados se hace en efectivo, fuera de cualquier sistema,
    así que nunca va a aparecer un débito en Integrity para esto (a
    diferencia de `DepositLedgerEntry`, donde el "aplicado" SÍ puede venir de
    Integrity). Lo COBRADO (créditos a la cuenta real de cada `kind`, ver
    `tips_service.GRATUITY_KINDS`) sí es 100% real -- solo lo pagado se carga
    acá. Un mismo día puede tener un pago de cada `kind` (constraint incluye
    `kind`, mig 79cf14911f74)."""
    __tablename__ = "fact_tips_payout_daily"
    __table_args__ = (UniqueConstraint("property_id", "kind", "date"),)
    id: Mapped[uuid.UUID] = UUIDpk()
    property_id: Mapped[uuid.UUID] = prop_fk()
    kind: Mapped[str] = mapped_column(Text, server_default="extra_tips")
    date: Mapped[date] = mapped_column(Date, index=True)
    paid_usd: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    note: Mapped[str | None] = mapped_column(Text)


class RevenueActualDaily(Base):
    """Tab 6.4 -- revenue real diario por depto, cargado en bloque desde una
    grilla diaria ya agregada (hoja 'Actual' del workbook Weekly, §5.1a
    naturaleza) en vez de reconstruirse día por día desde Opera/Integrity."""
    __tablename__ = "fact_revenue_actual_daily"
    id: Mapped[uuid.UUID] = UUIDpk()
    property_id: Mapped[uuid.UUID] = prop_fk()
    date: Mapped[date] = mapped_column(Date, index=True)
    dept_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("dim_department.id"))
    amount_usd: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    rooms_sold: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    total_pax: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    available_rooms: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))


class OperaTxn(Base):
    __tablename__ = "fact_opera_txn"
    id: Mapped[uuid.UUID] = UUIDpk()
    property_id: Mapped[uuid.UUID] = prop_fk()
    business_date: Mapped[date] = mapped_column(Date, index=True)
    tcode: Mapped[str | None] = mapped_column(Text, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    type: Mapped[str | None] = mapped_column(Text)
    total: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    guest_ledger: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    package_ledger: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    ar_ledger: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    deposit_ledger: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")


class OperaTxnDetail(Base):
    """Detalle de transacción Opera (trx por market_code / room_class) — mig 0002.
    Necesario para el pivote 'Ingresos x Market Code' y el desglose por room class."""
    __tablename__ = "fact_opera_txn_detail"
    id: Mapped[uuid.UUID] = UUIDpk()
    property_id: Mapped[uuid.UUID] = prop_fk()
    business_date: Mapped[date] = mapped_column(Date, index=True)
    tcode: Mapped[str | None] = mapped_column(Text, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    type: Mapped[str | None] = mapped_column(Text)
    market_code: Mapped[str | None] = mapped_column(Text)
    room_class: Mapped[str | None] = mapped_column(Text)
    trx_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    trx_guest_ledger: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    trx_package_ledger: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")


class TrialBalanceLine(Base):
    """Línea por TCode del Trial Balance OFICIAL de Opera (OPERA_TrialBalance_*.XML)
    — Tab 2.2. Reemplaza el trial balance que la app derivaba de fact_opera_txn:
    el archivo de Opera es más completo (incluye pagos/ajustes, todos los TRX_TYPE,
    no solo revenue). Débitos/créditos por ledger tal cual los reporta Opera."""
    __tablename__ = "fact_trial_balance"
    id: Mapped[uuid.UUID] = UUIDpk()
    property_id: Mapped[uuid.UUID] = prop_fk()
    business_date: Mapped[date] = mapped_column(Date, index=True)
    trx_type: Mapped[str | None] = mapped_column(Text, index=True)
    trx_type_desc: Mapped[str | None] = mapped_column(Text)
    tcode: Mapped[str | None] = mapped_column(Text, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    tb_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    net_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    guest_ledger: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    package_ledger: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    ar_ledger: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    deposit_ledger: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")


class LedgerBalance(Base):
    """Saldo OFICIAL por ledger y día, extraído de los totales del Trial Balance
    (CF_*_YEST=apertura, CS_*_DEBIT/CREDIT_REP=movimiento, CF_*_REP=cierre) — Tab 2.3.
    Elimina el anclaje manual cuando el archivo existe (queda como respaldo)."""
    __tablename__ = "fact_ledger_balance"
    __table_args__ = (UniqueConstraint("property_id", "business_date", "ledger"),)
    id: Mapped[uuid.UUID] = UUIDpk()
    property_id: Mapped[uuid.UUID] = prop_fk()
    business_date: Mapped[date] = mapped_column(Date, index=True)
    ledger: Mapped[str] = mapped_column(Text)  # guest | package | ar | deposit
    opening: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    debit: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    credit: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    closing: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")


class CityLedgerInvoice(Base):
    """Factura del City Ledger (OPERA_GEN_XMLBO_CITYLEDGER_*.xml) — detalle del
    movimiento del AR Ledger (Tab 2.3): a quién se le facturó (empresa/agencia),
    N° factura, monto y reserva. La suma del día ata al movimiento del AR Ledger."""
    __tablename__ = "fact_city_ledger"
    id: Mapped[uuid.UUID] = UUIDpk()
    property_id: Mapped[uuid.UUID] = prop_fk()
    business_date: Mapped[date] = mapped_column(Date, index=True)
    trx_code: Mapped[str | None] = mapped_column(Text)
    transaction_type: Mapped[str | None] = mapped_column(Text)
    bill_no: Mapped[str | None] = mapped_column(Text)
    invoice_no: Mapped[str | None] = mapped_column(Text)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    customer_internal_id: Mapped[str | None] = mapped_column(Text)
    account_name: Mapped[str | None] = mapped_column(Text)
    account_number: Mapped[str | None] = mapped_column(Text)
    confirmation_no: Mapped[str | None] = mapped_column(Text)
    arrival_date: Mapped[str | None] = mapped_column(Text)
    departure_date: Mapped[str | None] = mapped_column(Text)
    guest_name: Mapped[str | None] = mapped_column(Text)


class PosCheck(Base):
    __tablename__ = "fact_pos_check"
    id: Mapped[uuid.UUID] = UUIDpk()
    property_id: Mapped[uuid.UUID] = prop_fk()
    business_date: Mapped[date] = mapped_column(Date, index=True)
    restaurant: Mapped[str | None] = mapped_column(Text)
    employee: Mapped[str | None] = mapped_column(Text)
    check_num: Mapped[str | None] = mapped_column(Text)
    hora: Mapped[str | None] = mapped_column(Text)
    forma_pago: Mapped[str | None] = mapped_column(Text)
    monto: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    is_room_charge: Mapped[bool] = mapped_column(Boolean, server_default="false")


class PosSummary(Base):
    """Agregados del Excel de Ventas Simphony — hojas 'Resumen Ejecutivo' y
    'Mapeo Simphony → Opera' (etapa/sub-tab 2.9), no re-derivables de fact_pos_check."""
    __tablename__ = "fact_pos_summary"
    __table_args__ = (UniqueConstraint("property_id", "business_date"),)
    id: Mapped[uuid.UUID] = UUIDpk()
    property_id: Mapped[uuid.UUID] = prop_fk()
    business_date: Mapped[date] = mapped_column(Date, index=True)
    source_file: Mapped[str | None] = mapped_column(Text)
    ventas_netas: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    cargos_servicio: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    total_ventas: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    voids: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    room_charge_confirmado: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")


class FbCovers(Base):
    """Cubiertos (comensales) por outlet F&B x meal period x día — Tab 9.5.

    Capturado a mano (grilla editable o carga masiva): ni Integrity (mayor
    contable) ni Simphony POS (`fact_pos_check` = una fila por CHECK, sin
    comensales) tienen este dato. Divisor del Cheque Promedio = Revenue/cubiertos.
    """
    __tablename__ = "fact_fb_covers"
    __table_args__ = (UniqueConstraint("property_id", "business_date", "outlet", "meal_period",
                                       name="uq_fb_covers_cell"),)
    id: Mapped[uuid.UUID] = UUIDpk()
    property_id: Mapped[uuid.UUID] = prop_fk()
    business_date: Mapped[date] = mapped_column(Date, index=True)
    outlet: Mapped[str] = mapped_column(Text)           # cost center F&B: 0123..0130
    meal_period: Mapped[str] = mapped_column(Text)      # Breakfast|Lunch|Dinner|All Day|Other
    covers: Mapped[int] = mapped_column(Integer, server_default="0")


# ---------------- auditoría ----------------
class Bill(Base):
    """Folio/factura de Opera (BILLS.xml) — mig 0004. Detalle auxiliar del Guest Ledger."""
    __tablename__ = "fact_bill"
    id: Mapped[uuid.UUID] = UUIDpk()
    property_id: Mapped[uuid.UUID] = prop_fk()
    business_date: Mapped[date] = mapped_column(Date, index=True)
    bill_no: Mapped[str | None] = mapped_column(Text, index=True)
    bill_type: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(Text)
    guest_internal_id: Mapped[str | None] = mapped_column(Text)
    guest_name: Mapped[str | None] = mapped_column(Text)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")


class BillLine(Base):
    """Transacción dentro de un folio (bill_detail/transaction) — mig 0004."""
    __tablename__ = "fact_bill_line"
    id: Mapped[uuid.UUID] = UUIDpk()
    property_id: Mapped[uuid.UUID] = prop_fk()
    business_date: Mapped[date] = mapped_column(Date, index=True)
    bill_no: Mapped[str | None] = mapped_column(Text, index=True)
    trx_code: Mapped[str | None] = mapped_column(Text)
    trx_date: Mapped[str | None] = mapped_column(Text)
    net_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    debit_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    credit_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")


class LedgerOpening(Base, TimestampMixin):
    """Anclaje MANUAL de saldo de apertura de un ledger (auxiliar) — mig 0003.

    Los ledgers (guest/package/ar/deposit) llevan saldo corriente: cierre = apertura +
    movimiento del día; apertura = cierre del día anterior. Cuando el saldo se desvía,
    el usuario fija un anclaje en una fecha para 'empezar bien'; la acumulación se reinicia
    desde ahí. `amount` es la APERTURA en `effective_date`.
    """
    __tablename__ = "ledger_opening"
    __table_args__ = (UniqueConstraint("property_id", "ledger", "effective_date"),)
    id: Mapped[uuid.UUID] = UUIDpk()
    property_id: Mapped[uuid.UUID] = prop_fk()
    ledger: Mapped[str] = mapped_column(Text)           # guest|package|ar|deposit
    effective_date: Mapped[date] = mapped_column(Date, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    note: Mapped[str | None] = mapped_column(Text)


class AuditRun(Base, TimestampMixin):
    __tablename__ = "audit_run"
    __table_args__ = (UniqueConstraint("property_id", "business_date"),)
    id: Mapped[uuid.UUID] = UUIDpk()
    property_id: Mapped[uuid.UUID] = prop_fk()
    business_date: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(Text, server_default="abierto")
    kpi_ok: Mapped[int] = mapped_column(Integer, server_default="0")
    kpi_discrepancia: Mapped[int] = mapped_column(Integer, server_default="0")
    kpi_faltante: Mapped[int] = mapped_column(Integer, server_default="0")
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    released_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("app_user.id"))
    refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refreshed_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("app_user.id"))
    override_flag: Mapped[bool] = mapped_column(Boolean, server_default="false")
    override_note: Mapped[str | None] = mapped_column(Text)


class AuditFinding(Base, TimestampMixin):
    __tablename__ = "audit_finding"
    __table_args__ = (UniqueConstraint("property_id", "business_date", "dedupe_key"),)
    id: Mapped[uuid.UUID] = UUIDpk()
    property_id: Mapped[uuid.UUID] = prop_fk()
    business_date: Mapped[date] = mapped_column(Date, index=True)
    source_view: Mapped[str | None] = mapped_column(Text)
    area: Mapped[str | None] = mapped_column(Text)
    persona: Mapped[str | None] = mapped_column(Text)
    tcode: Mapped[str | None] = mapped_column(Text)
    monto: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default="0")
    tipo_desviacion: Mapped[str | None] = mapped_column(Text)
    cobrar_empleado: Mapped[bool] = mapped_column(Boolean, server_default="false")
    charged_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("app_user.id"))
    estado: Mapped[str] = mapped_column(Text, server_default="abierto", index=True)
    comentario: Mapped[str | None] = mapped_column(Text)
    # identidad estable del hallazgo dentro de (property, día) -- para poder
    # hacer upsert en cada re-auditoría sin pisar estado/resolved_note (§10:
    # nunca perder una decisión ya tomada por re-correr "Ingerir + Auditar").
    dedupe_key: Mapped[str | None] = mapped_column(Text)
    resolved_note: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


__all__ = [
    "Property", "Role", "AppUser", "Department", "RoomCategory", "PaymentMap",
    "MarketCode", "OperaRevenueCat", "Calendar", "WeekCalendar", "IngestBatch", "IngestDayStatus",
    "AppConfig", "IntegrityLine", "RoomStat", "BudgetMonthly", "Budget",
    "OperaTxn", "OperaTxnDetail", "PosCheck", "Bill", "BillLine",
    "LedgerOpening", "AuditRun", "AuditFinding", "RevenueActualDaily",
    "RoomStatOpening", "CompStatMonthly", "MonthlyCashPosition", "CashFlowForecast",
]
