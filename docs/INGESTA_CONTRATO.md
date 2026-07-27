# Contrato de ingesta — formatos REALES (derivado de `auditoria.py` + goldens)

> Reemplaza al `BITACORA_INSUMOS_AUDITORIA.md` (no entregado). Documenta qué archivo
> es qué y su estructura exacta, según los insumos del día **2026-06-08** y el script
> `backend/reference/auditoria.py`. Diferencias con el spec marcadas con ⚠️.

## 1. Opera (XML) — clasificar por contenido, no por nombre
Todos traen `hotel_code="COWLCR"` y `date="YYYY-MM-DD"` en la raíz → de ahí sale `business_date` (no del filename).

| Archivo (patrón) | Raíz | Contenido | Destino |
|---|---|---|---|
| `*REVENUE*.xml` | `<revenue>` | `transaction_total[@transaction_type]` con `transaction_code`, `description`, `total_amount`, `total_guest_ledger`, `total_package_ledger`, `total_ar_ledger`, `total_deposit_ledger`; + `transaction_details/transaction` con `market_code`, `room_class`, `trx_amount`, `trx_guest_ledger`, `trx_package_ledger` | ✅ `fact_opera_txn` (header) + `fact_opera_txn_detail` (mig 0002). Cargado por `ingest_service.ingest_day`. |
| `*STATISTICS*.xml` | `<statistics>` | `statistic_record` con `market_code`, `room_class`, `room_type`, `rooms`, `persons`, `noshow_rooms`, `cancel_rooms` | ⬜ Archivo presente y parseado por `ingest/opera.py::parse_statistics`, pero **sin loader a la DB todavía** — falta para el sub-tab 2.4 |
| `statroomtype_*.XML` | (Oracle Reports) | room revenue por tipo (`InputsSTATS`) | ⬜ archivo presente, **sin parser ni loader** — pendiente etapa 5 (`fact_room_stat`, RN/PAX/room_revenue) |
| `history_forecast_FULL.XML` + `..._ROOMS ONLY.XML` | `<HISTORY_FORECAST>` | `G_CONSIDERED_DATE` con `REVENUE`, `NO_ROOMS`, `NO_PERSONS`, `INVENTORY_ROOMS`, `CF_AVERAGE_ROOM_RATE`, `CF_OCCUPANCY` | ⬜ Parseado por `ingest/opera.py::parse_history_forecast` (con test), pero **sin loader a la DB** — falta para el sub-tab 2.5 (OTB vs Revenue). El de **mayor** REVENUE = Total, el **menor** = Rooms Only |
| `*BILLS.xml` + `*CUSTOMER.xml` | `<bills>`/`<customers>` | folios con detalle de transacciones + nombres de huésped | ✅ `fact_bill` + `fact_bill_line` (mig 0004). Cargado por `ingest_service`; consumido en el detalle auxiliar del Guest Ledger (sub-tab 2.3) |
| `*CITY_LEDGER.xml` | `<city_ledger>` | AR — vacío el 2026-06-08 | ⬜ sin parser (no hubo datos que forzaran construirlo) |

## 2. Integrity (Excel) — ✅ PRESENTE (2026-06-08)
- Archivo real: **`DAILY REVENUE REPORT 2026-06-08.xlsx`** (nombre engañoso; se detecta por
  **contenido**: hoja única `Datos` — §2.8). Reconciliación 06-08 corrida: 33 OK, 2 discrepancias, 0 faltantes.
- Archivo `.xlsx`, hoja **`Datos`**, `header=8` (skip 8 filas).
- Columnas: `Referencia` (→ TCode), `Créditos Dol`, `Débitos Dol`, `Cuenta`, `Nombre cuenta`, `T.C.`
  ⚠️ El spec decía `Créditos Col/Débitos Col`; el real es **`Dol`** (USD). Nombres de columna con acento.
- **TCode** = regex `TCode(?:\s+CXC)?:\s*(\d+)` sobre `Referencia` (⚠️ no es "todos los dígitos"; es el número tras `TCode:` / `TCode CXC:`).
- Se agrupa por `tcode`: `int_cr=sum(Créditos Dol)`, `int_db=sum(Débitos Dol)`.
- Destino: `stg_integrity_line` + reconciliación.

## 3. POS / Simphony — formato validado, falta el archivo del día correcto
Dos formatos posibles:
- **Excel de Ventas** con hojas `Resumen Ejecutivo`, `Mapeo Simphony → Opera`, `Detalle de Checks`.
  Parser hecho y testeado en `ingest/pos.py::parse_pos_excel` contra `Ventas_2026-06-28_FINAL.xlsx`
  (formato confirmado: calza exacto con lo que espera `auditoria.py`, cero ajustes).
- **`.evt`** (log Simphony): regex sobre `<PostRequest .../>`; montos en CRC / TC=460.18. No hubo un
  ejemplo real para testear este camino.
- **Falta el archivo `Ventas_2026-06-08...xlsx`** (el 06-28 es de otro día, no cruza con la reconciliación
  del 06-08). Sin él: el parser existe pero **no está conectado a `ingest_service`** (no hay loader a
  `fact_pos_check`, y el sub-tab 2.9 sigue en placeholder).

## 4. Reconciliación (núcleo, §5.4 confirmado en `auditoria.py`)
- Merge `opera_hdr` ⋈ `integrity` por `tcode` (outer).
- `diferencia`: si `type==PAYMENT` → `integ = -int_db`; si no → `integ = int_cr`. `dif = integ - opera.total`.
- Estados: `left_only` → `INTERNO` si type∈{INTERNAL,PACKAGE} si no `FALTA EN INTEGRITY`; `right_only` → `FALTA EN OPERA`; resto → `OK` si `|dif|<0.01` si no `DISCREPANCIA`.
- Nota del script: TCodes `9910/9990` son internos Opera (sin asiento Integrity).

## 5. Master data embebida en los goldens (ya sembrada)
- **`DEPT_MAP`** (hojas en `DAILY REV REP AS OF DAY 31.xlsm` y Weekly): outlets 4-díg → OutputColumn → `dim_department` (17 filas). Header en fila con `DeptCode | DeptName | OutputColumn`.
- **`Mapping`** (en `DAILY CASH POSITION MASTER FILE.xlsx`): 12 columnas → `dim_payment_map` (66 TCodes cargados).
  ⚠️ **10 TCodes duplicados** en la hoja (`3717,3724,3726,3737,3738,3740,3752,3753,3755,3756`): se conserva la 1ª fila y se avisa. **TODO(bismark): confirmar el mapeo correcto de esos 10.**
- **Budget**: hojas `Budget` / `12 months Budget 06` → `budget_monthly`. ⚠️ Layout transpuesto con Actual 2024 + FORECAST; **pendiente confirmar qué columnas son el presupuesto del año vigente** antes de cargar. TODO(bismark).

## 7. Ledgers / auxiliares (2.3) — no viene de un solo archivo, se calcula
Los 4 ledgers (`guest`, `package`, `ar`, `deposit`) NO tienen un export dedicado de Opera; su saldo se
**deriva** de `fact_opera_txn` (columnas `guest_ledger`, `package_ledger`, `ar_ledger`, `deposit_ledger`
del REVENUE.xml) más un anclaje manual editable (`ledger_opening`, mig 0003):
- `apertura(d) = anclaje.amount + Σ movimientos entre anclaje.fecha y d-1` (o `Σ` desde el origen si no hay anclaje)
- `movimiento(d) = Σ columna del ledger en fact_opera_txn ese día`
- `cierre(d) = apertura(d) + movimiento(d)`, y `apertura(d+1) = cierre(d)` (arrastre automático)
- Editar la apertura de una fecha ("re-anclar") reinicia la acumulación desde ahí — es la forma de
  corregir un saldo que se rompió, sin tocar código.
- El **detalle de movimiento por TCode** (qué transacciones movieron el ledger ese día) ata exacto al
  número — a diferencia de los **folios** del Guest Ledger (`fact_bill`, desde BILLS.xml), que atan a
  las cuentas **liquidadas/facturadas** del día, no al movimiento bruto (incluye huéspedes in-house).
  Esta distinción está explicada en la propia UI del sub-tab 2.3.

## Estado de insumos para cerrar tests $0.01
| Insumo | ¿Presente? | ¿Cargado a la DB? |
|---|---|---|
| Opera REVENUE + BILLS + CUSTOMER 2026-06-08 | ✅ | ✅ |
| Opera STATISTICS + history_forecast 2026-06-08 | ✅ | ⬜ falta loader |
| `statroomtype_*.XML` 2026-06-08 | ✅ | ⬜ falta parser+loader (etapa 5) |
| Goldens (Weekly, Cash, Day31, Daily Rev) | ✅ | n/a (son de validación, no de carga) |
| **Integrity `.xlsx` (mayor, hoja Datos) 2026-06-08** | ✅ (`DAILY REVENUE REPORT 2026-06-08.xlsx`) | ✅ |
| POS / Simphony del **06-08** | ❌ **falta** (hay uno del 06-28 que solo validó el formato) | — |

## 6. Observación de auditoría (2026-06-08)
TCodes **6480 / 6485** ("Adjust Deep Con…"): revenue **negativo** en Opera (−120 / −90) que
en Integrity aparece como **débito**. Con la regla §5.4 (revenue usa `int_cr`) surgen como
**DISCREPANCIA** — excepción visible para el auditor, no se netea en silencio. `auditoria.py`
hace lo mismo. **TODO(bismark): confirmar si los ajustes negativos deben netearse contra el débito.**
