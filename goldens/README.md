# /goldens — fixtures de validación (§8)

Estos archivos son el **criterio de "done"**: cada vista de la app debe reproducir su golden a **tolerancia $0.01**.
Se guardan aquí pero **no se versionan** (ver `.gitignore`) por peso/confidencialidad — solo existen en el
filesystem local de esta máquina/repo.

## Estado real (no confiar en versiones viejas de este archivo)

| Archivo | Valida (vista) | ¿Presente? |
|---|---|---|
| `DAILY REV REP AS OF DAY 31.xlsm` → hoja `Summary` | Tab 3 · Daily Revenue | ✅ |
| ídem → hoja `Room Statistics` | Sub-tab 2.4 / Room stats · ADR / Occ / Yield | ✅ (archivo sí, loader a DB no) |
| `WEEKLY REVENUE REPORT MASTER FILE.xlsx` → hoja `Weekly` | Tab 4 · Weekly / YTD | ✅ |
| `DAILY CASH POSITION MASTER FILE.xlsx` → Flash/Recon/Bank/Brand | Tab 5 · Cash | ✅ |
| Set de auditoría del **2026-06-08** (Integrity, Opera XMLs, Bills/Customer) | Tab 2 · Reconciliación + KPIs | ✅ en `/inputs/2026-06-08/` — **usado y verificado** |
| POS/Simphony del 2026-06-08 | Sub-tab 2.9 · control de cajeros | ❌ **falta** (hay uno del 06-28 que solo valida formato) |

## `/inputs/2026-06-08/` — insumos crudos ya recibidos y usados
```
COWLCR_20260608_REVENUE.xml         -> fact_opera_txn + fact_opera_txn_detail
COWLCR_20260608_STATISTICS.xml      -> pendiente loader (sub-tab 2.4)
history_forecast_FULL.XML           -> pendiente loader (sub-tab 2.5, "Total")
history_forecast_ROOMS ONLY.XML     -> pendiente loader (sub-tab 2.5, "Rooms Only")
statroomtype_22961647.XML           -> sin usar aún (etapa 5, room stats)
COWLCR_20260608_BILLS.xml           -> fact_bill + fact_bill_line (folios, sub-tab 2.3)
COWLCR_20260608_CUSTOMER.xml        -> nombres de huésped para los folios
COWLCR_20260608_CITY_LEDGER.xml     -> vacío este día (AR); sin uso todavía
DAILY REVENUE REPORT 2026-06-08.xlsx -> ES EL INTEGRITY (nombre engañoso; se detecta
                                         por contenido: hoja única "Datos" — §2.8)
Trial_08.PDF                        -> referencia visual, no parseado
```

## `/inputs/2026-06-28/` — POS de referencia (día distinto, no cruza con el 06-08)
```
Ventas_2026-06-28_FINAL.xlsx        -> validó el formato del parser POS (hojas
                                        'Resumen Ejecutivo', 'Detalle de Checks',
                                        'Mapeo Simphony → Opera'). Falta el del 06-08
                                        para completar la auditoría de ese día.
```

## Cómo se usan
La ingesta (`POST /ingest/{fecha}`) lee `goldens/inputs/<business_date>/`, clasifica los archivos
**por contenido** (no por nombre — ver `docs/INGESTA_CONTRATO.md` §2.8) y carga a la base. Repetir el
POST reemplaza el día completo (§2.5), no duplica.
