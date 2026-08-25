-- =====================================================================
-- DAILY-OPS · Esquema canónico (CLAUDE.md §3)
-- PostgreSQL 15 · base 'daily_ops'
-- Fuente de verdad del DDL; la migración 0001 lo ejecuta.
-- Convenciones: PK UUID (gen_random_uuid), montos NUMERIC(15,2),
-- created_at/updated_at en tablas editables (trigger), property_id en todo.
-- Tablas ordenadas por dependencia (FKs solo hacia tablas ya creadas).
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid()

CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------
-- 1) PROPIEDAD (todo cuelga de aquí) + USUARIOS/ROLES
-- ---------------------------------------------------------------------
CREATE TABLE dim_property (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  code        TEXT NOT NULL UNIQUE,          -- 'COWLCR'
  name        TEXT NOT NULL,                 -- 'Corcovado Wilderness Lodge'
  hotel_code  TEXT,
  activa      BOOLEAN NOT NULL DEFAULT true,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE role (
  id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  code TEXT NOT NULL UNIQUE,      -- admin, income_auditor, viewer
  name TEXT NOT NULL
);

CREATE TABLE app_user (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email         TEXT NOT NULL UNIQUE,
  name          TEXT,
  role_id       UUID REFERENCES role(id),
  password_hash TEXT,
  activo        BOOLEAN NOT NULL DEFAULT true,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- 2) DIMENSIONES / MASTER DATA
-- ---------------------------------------------------------------------

-- DOS dimensiones (§5.1): naturaleza (9-char) + outlet (4-díg)
CREATE TABLE dim_department (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  property_id    UUID NOT NULL REFERENCES dim_property(id),
  -- §5.1: DOS dimensiones. Una fila puede ser un OUTLET (cost_center + output_column,
  -- del DEPT_MAP) o una NATURALEZA 9-char (cuenta_nature). Por eso ambas son nullable.
  -- TODO(bismark): confirmar si conviene separar en dos tablas (dim_outlet / dim_nature).
  cuenta_nature  TEXT,               -- patrón 9-char, ej '4000-0110' (nature map)
  cost_center    TEXT,               -- outlet 4-díg, ej '0123' (DEPT_MAP)
  outlet_name    TEXT,               -- ej 'Vitrales'
  output_column  TEXT NOT NULL,      -- una de las 12 columnas canónicas o 'F&B'
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (property_id, cuenta_nature, cost_center)
);

CREATE TABLE dim_room_category (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  property_id      UUID NOT NULL REFERENCES dim_property(id),
  code2            TEXT NOT NULL,    -- últimos 2 díg: '01'..'06','00'
  report_name      TEXT NOT NULL,   -- 'Corcovado Deluxe Villas'
  opera_short_desc TEXT,            -- 'Corcovado Deluxe' (join a Opera)
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (property_id, code2)
);

CREATE TABLE dim_payment_map (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  property_id      UUID NOT NULL REFERENCES dim_property(id),
  transaction_code TEXT NOT NULL,   -- TCode
  code             TEXT,
  description      TEXT,
  banco_codigo     TEXT,            -- BAC,BCR,BNCR,LAF,CASH,SINPE,ROOM,HOUSE,AR
  banco_nombre     TEXT,
  moneda           TEXT,
  tipo_pago        TEXT,            -- Tarjeta,Transferencia,Efectivo,...
  marca_metodo     TEXT,            -- Visa/MC/Amex...
  grupo            TEXT,
  cash_flow        TEXT,            -- 'Real Cash' | 'Non-Cash'
  canal            TEXT,
  report_bucket    TEXT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (property_id, transaction_code)
);

CREATE TABLE dim_market_code (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  property_id UUID NOT NULL REFERENCES dim_property(id),
  code        TEXT NOT NULL,        -- TAFIT,WEB,DIR,COM,CORP,GRP
  name        TEXT NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (property_id, code)
);

CREATE TABLE dim_opera_revenue_cat (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  property_id UUID NOT NULL REFERENCES dim_property(id),
  tcode       TEXT NOT NULL,        -- '1000','2320',...
  categoria   TEXT NOT NULL,        -- Accommodation,Retail,Tours,...
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (property_id, tcode, categoria)
);

-- GLOBAL (§3 no le pone property_id). Lun–Dom, generado por código.
CREATE TABLE dim_calendar (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  date        DATE NOT NULL UNIQUE,
  iso_week    INT NOT NULL,
  week_start  DATE NOT NULL,        -- lunes
  week_end    DATE NOT NULL,        -- domingo
  week_label  TEXT NOT NULL,        -- 'W26 | 22-Jun-2026 to 28-Jun-2026'
  month       INT NOT NULL,
  year        INT NOT NULL
);

-- ---------------------------------------------------------------------
-- 3) INGESTA / CONTROL OPERATIVO
-- ---------------------------------------------------------------------
CREATE TABLE ingest_batch (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  property_id   UUID NOT NULL REFERENCES dim_property(id),
  business_date DATE NOT NULL,
  uploaded_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  uploaded_by   UUID REFERENCES app_user(id)
);

CREATE TABLE ingest_day_status (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  property_id   UUID NOT NULL REFERENCES dim_property(id),
  business_date DATE NOT NULL,
  sistema       TEXT NOT NULL CHECK (sistema IN ('opera','integrity','pos')),
  estado        TEXT NOT NULL DEFAULT 'Incompleto'
                 CHECK (estado IN ('Incompleto','Listo','Auditado','Cerrado')),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (property_id, business_date, sistema)
);

CREATE TABLE app_config (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  property_id UUID REFERENCES dim_property(id),   -- NULL = global
  key         TEXT NOT NULL,      -- recon_tolerance, gate_min_set, gate_hard
  value       TEXT NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (property_id, key)
);

-- ---------------------------------------------------------------------
-- 4) STAGING (revenue y cash derivan de aquí; no se re-ingiere)
-- ---------------------------------------------------------------------
CREATE TABLE stg_integrity_line (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  property_id     UUID NOT NULL REFERENCES dim_property(id),
  business_date   DATE NOT NULL,
  source_file     TEXT,
  ingest_batch_id UUID NOT NULL REFERENCES ingest_batch(id),
  cuenta          TEXT,
  nombre_cuenta   TEXT,
  centro_costo    TEXT,
  referencia      TEXT,
  detalle         TEXT,
  moneda_fuente   TEXT,
  tc              NUMERIC(15,6),
  deb_col         NUMERIC(15,2) NOT NULL DEFAULT 0,   -- débitos colones
  cred_col        NUMERIC(15,2) NOT NULL DEFAULT 0,   -- créditos colones
  deb_usd         NUMERIC(15,2) NOT NULL DEFAULT 0,
  cred_usd        NUMERIC(15,2) NOT NULL DEFAULT 0,
  tcode           TEXT                                -- dígitos de Referencia
);

-- ---------------------------------------------------------------------
-- 5) HECHOS (todos con property_id)
-- ---------------------------------------------------------------------
CREATE TABLE fact_room_stat (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  property_id    UUID NOT NULL REFERENCES dim_property(id),
  business_date  DATE NOT NULL,
  room_category  TEXT,
  room_revenue   NUMERIC(15,2) NOT NULL DEFAULT 0,
  stay_rooms     NUMERIC(15,2) NOT NULL DEFAULT 0,   -- RN / occupied
  stay_persons   NUMERIC(15,2) NOT NULL DEFAULT 0,   -- PAX
  physical_rooms NUMERIC(15,2) NOT NULL DEFAULT 0    -- available
);

-- input manual. Check F&B: food+beverage+misc = total F&B (se valida en app/ingesta)
CREATE TABLE budget_monthly (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  property_id     UUID NOT NULL REFERENCES dim_property(id),
  year            INT NOT NULL,
  month           INT NOT NULL CHECK (month BETWEEN 1 AND 12),
  dept_id         UUID REFERENCES dim_department(id),
  amount_usd      NUMERIC(15,2) NOT NULL DEFAULT 0,
  available_rooms NUMERIC(15,2),
  rooms_occupied  NUMERIC(15,2),
  guests          NUMERIC(15,2),
  occupancy_pct   NUMERIC(9,4),
  adr             NUMERIC(15,2),
  food            NUMERIC(15,2) NOT NULL DEFAULT 0,
  beverage        NUMERIC(15,2) NOT NULL DEFAULT 0,
  misc            NUMERIC(15,2) NOT NULL DEFAULT 0,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- derivado = budget_monthly / días_del_mes; residual → último día (largest-remainder)
CREATE TABLE fact_budget (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  property_id UUID NOT NULL REFERENCES dim_property(id),
  date        DATE NOT NULL,
  dept_id     UUID REFERENCES dim_department(id),
  amount_usd  NUMERIC(15,2) NOT NULL DEFAULT 0
);

-- Tab 6.1.1 Forecast -- gemelo de budget_monthly / fact_budget (tablas propias
-- para que el reemplazo anual de uno no pise al otro).
CREATE TABLE forecast_monthly (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  property_id     UUID NOT NULL REFERENCES dim_property(id),
  year            INT NOT NULL,
  month           INT NOT NULL CHECK (month BETWEEN 1 AND 12),
  dept_id         UUID REFERENCES dim_department(id),
  amount_usd      NUMERIC(15,2) NOT NULL DEFAULT 0,
  available_rooms NUMERIC(15,2),
  rooms_occupied  NUMERIC(15,2),
  guests          NUMERIC(15,2),
  occupancy_pct   NUMERIC(9,4),
  adr             NUMERIC(15,2),
  food            NUMERIC(15,2) NOT NULL DEFAULT 0,
  beverage        NUMERIC(15,2) NOT NULL DEFAULT 0,
  misc            NUMERIC(15,2) NOT NULL DEFAULT 0,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- derivado = forecast_monthly / dias_del_mes; residual -> ultimo dia
CREATE TABLE fact_forecast (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  property_id UUID NOT NULL REFERENCES dim_property(id),
  date        DATE NOT NULL,
  dept_id     UUID REFERENCES dim_department(id),
  amount_usd  NUMERIC(15,2) NOT NULL DEFAULT 0
);

CREATE TABLE fact_opera_txn (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  property_id    UUID NOT NULL REFERENCES dim_property(id),
  business_date  DATE NOT NULL,
  tcode          TEXT,
  description    TEXT,
  type           TEXT,             -- PAYMENT, REVENUE, INTERNAL, PACKAGE...
  total          NUMERIC(15,2) NOT NULL DEFAULT 0,
  guest_ledger   NUMERIC(15,2) NOT NULL DEFAULT 0,
  package_ledger NUMERIC(15,2) NOT NULL DEFAULT 0,
  ar_ledger      NUMERIC(15,2) NOT NULL DEFAULT 0,
  deposit_ledger NUMERIC(15,2) NOT NULL DEFAULT 0
);

CREATE TABLE fact_pos_check (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  property_id    UUID NOT NULL REFERENCES dim_property(id),
  business_date  DATE NOT NULL,
  restaurant     TEXT,
  employee       TEXT,
  check_num      TEXT,
  hora           TEXT,
  forma_pago     TEXT,
  monto          NUMERIC(15,2) NOT NULL DEFAULT 0,
  is_room_charge BOOLEAN NOT NULL DEFAULT false
);

-- ---------------------------------------------------------------------
-- 6) DOMINIO DE AUDITORÍA
-- ---------------------------------------------------------------------
CREATE TABLE audit_run (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  property_id      UUID NOT NULL REFERENCES dim_property(id),
  business_date    DATE NOT NULL,
  status           TEXT NOT NULL DEFAULT 'abierto' CHECK (status IN ('abierto','cerrado')),
  kpi_ok           INT NOT NULL DEFAULT 0,
  kpi_discrepancia INT NOT NULL DEFAULT 0,
  kpi_faltante     INT NOT NULL DEFAULT 0,
  generated_at     TIMESTAMPTZ,
  released_at      TIMESTAMPTZ,
  released_by      UUID REFERENCES app_user(id),
  refreshed_at     TIMESTAMPTZ,
  refreshed_by     UUID REFERENCES app_user(id),
  override_flag    BOOLEAN NOT NULL DEFAULT false,
  override_note    TEXT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (property_id, business_date)
);

CREATE TABLE audit_finding (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  property_id     UUID NOT NULL REFERENCES dim_property(id),
  business_date   DATE NOT NULL,
  source_view     TEXT,
  area            TEXT,
  persona         TEXT,
  tcode           TEXT,
  monto           NUMERIC(15,2) NOT NULL DEFAULT 0,
  tipo_desviacion TEXT,
  cobrar_empleado BOOLEAN NOT NULL DEFAULT false,
  charged_by      UUID REFERENCES app_user(id),
  estado          TEXT NOT NULL DEFAULT 'abierto' CHECK (estado IN ('abierto','cerrado')),
  comentario      TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =====================================================================
-- ÍNDICES (§3)
-- =====================================================================
CREATE INDEX ix_stg_int_bdate   ON stg_integrity_line (business_date);
CREATE INDEX ix_stg_int_prop    ON stg_integrity_line (property_id);
CREATE INDEX ix_stg_int_tcode   ON stg_integrity_line (tcode);
CREATE INDEX ix_stg_int_batch   ON stg_integrity_line (ingest_batch_id);

CREATE INDEX ix_roomstat_bdate  ON fact_room_stat (business_date);
CREATE INDEX ix_roomstat_prop   ON fact_room_stat (property_id);

CREATE INDEX ix_budmon_prop     ON budget_monthly (property_id);
CREATE INDEX ix_budmon_dept     ON budget_monthly (dept_id);

CREATE INDEX ix_factbud_date    ON fact_budget (date);
CREATE INDEX ix_factbud_prop    ON fact_budget (property_id);
CREATE INDEX ix_factbud_dept    ON fact_budget (dept_id);

CREATE INDEX ix_fcstmon_prop    ON forecast_monthly (property_id);
CREATE INDEX ix_fcstmon_dept    ON forecast_monthly (dept_id);

CREATE INDEX ix_factfcst_date   ON fact_forecast (date);
CREATE INDEX ix_factfcst_prop   ON fact_forecast (property_id);
CREATE INDEX ix_factfcst_dept   ON fact_forecast (dept_id);

CREATE INDEX ix_operatxn_bdate  ON fact_opera_txn (business_date);
CREATE INDEX ix_operatxn_prop   ON fact_opera_txn (property_id);
CREATE INDEX ix_operatxn_tcode  ON fact_opera_txn (tcode);

CREATE INDEX ix_pos_bdate       ON fact_pos_check (business_date);
CREATE INDEX ix_pos_prop        ON fact_pos_check (property_id);

CREATE INDEX ix_paymap_prop     ON dim_payment_map (property_id);
CREATE INDEX ix_paymap_tcode    ON dim_payment_map (transaction_code);
CREATE INDEX ix_operacat_prop   ON dim_opera_revenue_cat (property_id);
CREATE INDEX ix_operacat_tcode  ON dim_opera_revenue_cat (tcode);
CREATE INDEX ix_dept_prop       ON dim_department (property_id);
CREATE INDEX ix_roomcat_prop    ON dim_room_category (property_id);
CREATE INDEX ix_mktcode_prop    ON dim_market_code (property_id);

CREATE INDEX ix_auditrun_bdate  ON audit_run (business_date);
CREATE INDEX ix_auditrun_prop   ON audit_run (property_id);
CREATE INDEX ix_finding_bdate   ON audit_finding (business_date);
CREATE INDEX ix_finding_prop    ON audit_finding (property_id);
CREATE INDEX ix_finding_estado  ON audit_finding (estado);

CREATE INDEX ix_batch_bdate     ON ingest_batch (business_date);
CREATE INDEX ix_batch_prop      ON ingest_batch (property_id);
CREATE INDEX ix_daystatus_bdate ON ingest_day_status (business_date);

-- =====================================================================
-- TRIGGERS updated_at (tablas editables)
-- =====================================================================
CREATE TRIGGER t_property_upd  BEFORE UPDATE ON dim_property          FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER t_appuser_upd   BEFORE UPDATE ON app_user             FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER t_dept_upd      BEFORE UPDATE ON dim_department       FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER t_roomcat_upd   BEFORE UPDATE ON dim_room_category    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER t_paymap_upd    BEFORE UPDATE ON dim_payment_map      FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER t_mktcode_upd   BEFORE UPDATE ON dim_market_code      FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER t_operacat_upd  BEFORE UPDATE ON dim_opera_revenue_cat FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER t_budmon_upd    BEFORE UPDATE ON budget_monthly       FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER t_auditrun_upd  BEFORE UPDATE ON audit_run            FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER t_finding_upd   BEFORE UPDATE ON audit_finding        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER t_daystatus_upd BEFORE UPDATE ON ingest_day_status    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER t_appconfig_upd BEFORE UPDATE ON app_config           FOR EACH ROW EXECUTE FUNCTION set_updated_at();
