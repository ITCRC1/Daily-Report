# DAILY-OPS

App web que unifica **Revenue diario, Revenue semanal, Posición de efectivo y Auditoría diaria de ingresos**
para SCP **Corcovado Wilderness Lodge** (`COWLCR`).

> Spec completo y decisiones de negocio: [`CLAUDE.md`](./CLAUDE.md) · Arranque original: [`START_HERE.md`](./START_HERE.md)
> Contrato de ingesta REAL (derivado de `auditoria.py` + inspección de los archivos, difiere del spec en detalles): [`docs/INGESTA_CONTRATO.md`](./docs/INGESTA_CONTRATO.md)
> **Principio rector:** la app *absorbe* los Excel actuales. Cada vista reproduce su golden file a **tolerancia $0.01**.

---

## ⏭️ Si estás retomando esto en una sesión nueva, leé esto primero

Este README es la fuente de verdad del estado del proyecto — no asumas que hay memoria de sesiones previas.
Antes de escribir código: correr `git log --oneline -15` para ver el historial real, y `pytest` en `/backend`
para confirmar que todo sigue verde.

**Próximo paso sugerido (sin bloqueo, se puede arrancar directo):**
- Completar **Cash MTD/semana/YTD por bucket + weekly/monthly trend** (hoy Tab 5 solo tiene Today+MTD
  simple) y decidir con Bismark de dónde sale el insumo de depósitos bancarios (bloqueante abajo).
- **Tab 1 (Data Input) completo**: upload real + malla de 365 días × sistema (ver detalle abajo).
- **Tab 6 (Master Data)**: 6.1 (Monthly Budget, descarga plantilla/sube/reset anual) + 6.2 + 6.3 +
  6.5 (Daily derivado) completos. 6.4/6.6 siguen sin construir — no dependen de Budget, son features
  distintas (ver detalle abajo).
- **Cash (Tab 5) ya tiene Weekly + YTD**, no solo Today/MTD (ver detalle abajo).
- El export hoy es del día individual (Revenue+Cash+Auditoría). Si hace falta un export semanal/YTD
  o multi-día, es una extensión directa sobre `app/export/` + `export_service.py`.

**Tab 1 · Data Input — upload real (2026-07-01):**
- `POST /ingest/{fecha}/upload` (multipart, `files: UploadFile[]`): guarda los archivos en
  `uploads/inputs/<fecha>/` (raíz separada de `goldens/inputs`, que son fixtures de validación —
  `uploads/` está en `.gitignore`, no se versiona), reemplazo total por día (borra lo subido antes,
  §2.5), y reusa `ingest_service.ingest_day` + `audit_service.run_audit` tal cual — cero lógica
  duplicada.
- Frontend: drag & drop + selector de archivos, lista de pendientes con quitar individual, resultado
  post-ingesta (qué se clasificó como qué, filas cargadas por tabla, KPIs de auditoría).
- Verificado end-to-end con un upload multipart real (no simulado): mismos 4 archivos del golden
  06-08 subidos a un día nuevo (2026-06-15) → mismo resultado exacto (33 OK, 2 discrepancias,
  9,560.02 de revenue) → datos de prueba limpiados después de verificar.

**Cash (Tab 5) — Weekly + YTD (2026-07-01):**
- `cash_service.weekly_cash`: mismo patrón que `revenue_service.weekly_report` — semana Lun-Dom vía
  `dim_calendar` + YTD parcial (solo días efectivamente cargados desde el 1-ene, no fabrica datos).
  Reusa `_cash_for_day`/`_merge_pivots` sin duplicar el motor de buckets (§5.5).
- `GET /cash/weekly/{fecha}` nuevo; `GET /cash/{fecha}` (Today/MTD) sin cambios de contrato.
- Frontend: el Tab 5 pasó de 2 a 4 pestañas (Today/MTD/Weekly/YTD), un solo fetch en paralelo a
  ambos endpoints. Verificado: 06-08 da el mismo total ($317.87) en las 4 vistas (un solo día
  cargado en total), consistente con lo ya validado en Revenue/Room Stats para ese mismo día.

**Tab 6 · Master Data — 6.2 Cash Mapping + 6.3 Integrity Mapping (2026-07-01):**
- CRUD real (crear/editar/borrar) sobre `dim_payment_map` (66 TCodes) y `dim_department` (17
  outlets), las dos tablas de mapeo que hoy determinan cómo se clasifica cada transacción en
  Cash (§5.5) y Revenue (§5.1b). Antes solo se podían corregir a mano en la base.
- Frontend: tabla editable genérica (`EditableTable`) — click en "Editar" abre inputs inline, "+
  Agregar" da de alta una fila nueva, "Borrar" con confirmación. Reusable para ambos catálogos.
- Valida en el backend: TCode/naturaleza+centro-de-costo duplicados devuelven 400 con mensaje claro
  (constraint UNIQUE de la tabla), `output_column` es obligatorio en departamentos.
- Verificado con un ciclo CRUD completo contra la API real (create → duplicado rechazado → update →
  delete) en ambos catálogos; el conteo de filas vuelve exacto al valor sembrado después de probar.
- 6.4/6.6 siguen sin construir (features distintas, no dependen de Budget).

**Tab 6.1 Monthly Budget + 6.5 Daily derivado (2026-07-02):**
- El bloqueante de `budget_monthly` **no era el layout viejo** — el usuario aclaró que quiere el flujo
  ya definido en §2 decisión cerrada #2: descargar una plantilla propia de la app (bloqueada, no el
  Excel legado transpuesto), llenarla offline en Excel, subirla de vuelta, reemplazo total del año
  ("reset anual"). No hizo falta ningún archivo nuevo ni adoptar el layout ambiguo del golden.
- `engine/budget.py::derive_daily_amounts`: reparte el monto mensual entre los días del mes, con el
  residual de redondeo cayendo en el último día (§3) — **validado exacto contra el ejemplo del propio
  spec**: $121,219.07 / 31 días → $3,910.29/día, último día $3,910.37, suma exacta al centavo.
- `budget_service.py`: `build_template` (Excel de 204 filas = 17 deptos × 12 meses, prellenado con lo
  ya cargado), `upload_and_replace` (reemplazo total del año en `budget_monthly` + deriva
  `fact_budget` día por día automáticamente), `monthly_summary`/`daily_summary` para las vistas.
- `GET/POST /master-data/budget/template` y `/upload`, `GET /master-data/budget` (6.1) y
  `/master-data/budget/daily` (6.5).
- Frontend: 6.1 con selector de año, botones de descarga/subida, y pivote Depto × Mes de lo cargado.
  6.5 con selector de año/mes y pivote Día × Depto de lo derivado (solo lectura, se genera solo).
- Verificado con un ciclo real (descargar → llenar con el ejemplo del spec → subir → confirmar
  derivación exacta vía API) y limpiado después — no queda presupuesto de prueba en la base. 4 tests
  nuevos (motor puro de derivación). 61/61 verdes.

**Tab 1 · Malla de 365 días × sistema (2026-07-01):**
- `GET /ingest/status?year=&prop=` (`ingest_service.day_status_grid`): por cada día con algún rastro
  (no manda 365 filas en blanco), calcula el estado **Incompleto → Listo → Auditado → Cerrado**
  cruzando `ingest_day_status` (por sistema: opera/integrity/pos) contra `app_config.gate_min_set`
  (mínimo requerido para "Listo") y `audit_run.status` (Auditado si existe corrida, Cerrado si
  `status='cerrado'`).
- **POS se detecta** en la clasificación por contenido (hojas `Resumen Ejecutivo` +
  `Detalle de Checks` del Excel de Simphony) y marca `ingest_day_status`. El loader completo a
  `fact_pos_check`/`fact_pos_summary` se construyó después (ver sub-tab 2.9 más abajo, ya no está
  bloqueado — solo el cruce con un día que tenga Opera/Integrity real, por falta de un POS del
  06-08 puntual).
- Frontend: calendario de 12 meses (Lun–Dom) con color por estado, click en un día lo selecciona
  globalmente (mismo selector que el resto de los tabs), panel de detalle por sistema + KPIs de
  auditoría del día elegido, navegación por año.

**Etapa 8 · Gate + REFRESH — completa (§2.6/§2.7):**
- `engine/gate.py::evaluate_gate`: gate suave (siempre libera, excepciones quedan visibles) vs gate
  duro (`app_config.gate_hard`, bloquea si hay discrepancia/faltante abiertos, salvo `override_flag`
  + `override_note` obligatoria). Default sigue en `false` (suave) — `TODO(bismark)` confirmar.
- `POST /audit/{fecha}/release`: libera el daily a dueños (`audit_run.status` abierto→cerrado,
  `released_at`/`released_by`); 400 si el gate bloquea sin override.
- `POST /audit/{fecha}/refresh`: re-ingesta + re-audita (mismos datos vigentes en
  `goldens/inputs/`), deja traza en `refreshed_at`/`refreshed_by`, **no cambia el `status`** — un
  día "cerrado" sigue cerrado tras refrescar (§2.6: "un daily... no se auto-recalcula").
- `GET /audit/{fecha}` ahora incluye `gate` (preview de si se podría liberar ahora mismo),
  `released_at`, `refreshed_at`, `override_flag/note`.
- Frontend (Tab 2): badge de estado (🔓 Abierto / 🔒 Cerrado), botón "Liberar a dueños" o "🔄
  REFRESH" según el estado, y flujo de override inline (nota obligatoria) cuando el gate duro bloquea.
- Probado end-to-end contra la API real: gate suave libera con 2 discrepancias visibles; gate duro
  bloquea (400) sin override y libera con override+nota; refresh preserva `status=cerrado`. Estado de
  dev restaurado a `abierto`/gate suave después de probar. 5 tests nuevos (motor puro), 43/43 verdes.

**Export — Excel + PDF del día:**
- `app/export/excel.py::build_daily_excel` (openpyxl, función pura): 3 hojas —
  **Revenue** (KPIs + centros Today/MTD + Room Stats por categoría + Otros), **Cash** (KPIs + los 4
  desgloses de bucket/banco/marca/canal + UNMAPPED), **Auditoria** (KPIs + estado/gate + detalle de
  reconciliación línea por línea).
- `app/export/pdf.py::build_daily_pdf` (fpdf2, función pura): una página — encabezado + estado/gate +
  6 KPIs principales + tabla de revenue por centro + tabla de cash por bucket. **Nota técnica:** la
  fuente core de fpdf2 no soporta acentos/ñ de forma confiable → se sanitiza con `_safe()`
  (`unicodedata` NFKD) cualquier texto dinámico (nombres de centro, el `reason` del gate, etc.) antes
  de renderizarlo; los literales del PDF están en ASCII puro a propósito.
- `export_service.py` orquesta: llama a los mismos `revenue_service`/`cash_service`/`audit_service`
  que usan las páginas (una sola fuente de verdad, no se recalcula nada aparte).
- `GET /export/{fecha}/excel` y `GET /export/{fecha}/pdf` (StreamingResponse, descarga directa).
  Botones "📊 Excel" / "📄 PDF" en el header del Tab 2.
- 2 tests de humo que cubren los dos bugs reales que salieron al probar contra el 06-08: un valor
  `None` en una fila de reconciliación rompía `number_format` en Excel, y el `reason` del gate (con
  tildes) rompía fpdf2 por el problema de fuente — ambos corregidos y ahora cubiertos por test.
  45/45 verdes en total.

**Etapa 5 · Room Stats (ADR/Occ/Yield) — completa:**
- `parse_statroomtype()` en `app/ingest/opera.py` (portado del XML `statroomtype*.XML` de Opera, que
  trae el año completo — la ingesta filtra al día del batch, §2.5/§2.8) → `fact_room_stat`.
- `engine/room_stats.py::room_stats_rollup`: agrupa por categoría (join por `SHORT_DESCRIPTION` exacto
  contra `dim_room_category.opera_short_desc`, §5.2) — ADR, Occupancy %, y **Yield Index** (ADR
  categoría / ADR overall, §5.3). Categoría fuera del catálogo → 'Otros' visible (§10), nunca se cae.
- **Reemplaza la disponibilidad de habitaciones** en los KPIs de Tabs 3 y 4: antes usaban el
  `inventory_rooms` del OTB (30, fijo) como proxy; ahora usan Σ `physical_rooms` real de
  `fact_room_stat` (§3: "nunca una constante hardcodeada") — en 2026-06-08 da **22**, no 30, porque
  Corcovado Deluxe y Carate Deluxe (8 habitaciones) no reportaron inventario ese día. Esto corrigió
  la ocupación de 43.3% a **59.1%**, el número real.
- Tabla "Room Statistics por categoría" agregada a `app/revenue-daily` y `app/revenue-weekly`.
- 5 tests nuevos (parser + motor), 38/38 verdes.

**Etapa 3 · Cash (Tab 5) — Daily completo:**
- `engine/cash.py`: buckets de dos niveles (§5.5) — cash-relevant amplio (`banco_codigo ∈ {BAC,BCR,
  BNCR,LAF,CASH,SINPE,ROOM,HOUSE,AR}`) vs bank-only estricto (`tipo_pago ∈ {Tarjeta,Transferencia}` y
  banco real); pivotes por bucket/banco/marca/canal; `cash_flow` Real Cash vs Non-Cash.
- Universo de pagos = headers Opera `type='PAYMENT'` (mismo criterio que la auditoría §5.4), resueltos
  contra `dim_payment_map`; sin entrada → **UNMAPPED visible** (§5.5, nunca se descarta en silencio).
- Monto real desde `stg_integrity_line` (deb−cred, §5.3 — opuesto a revenue), no desde Opera.
- `GET /cash/{fecha}` (Today + MTD) → `app/cash`. **Validado por reconciliación**: 06-08 total
  cash=$317.87 = \|payment_total\| de Opera (CASH $7.91 + BAC MasterCard $309.96).
- **BLOQUEADO** (TODO bismark): depósitos entrados vs aplicados y balance corriendo real — no hay
  insumo de banco/depósitos cargado todavía; falta definir la fuente con Bismark.

**Etapa 2 (Daily + Weekly) — completa, ambos Tabs 3 y 4:**
- **Daily** (`engine/revenue.py::daily_revenue`, outlet/DEPT_MAP §5.1b, F&B colapsado) → `GET
  /revenue/{fecha}` → `app/revenue-daily`.
- **Weekly** (`engine/revenue.py::weekly_pivot`, naturaleza 9-char §5.1a — abre Rooms/Rooms Others y
  Sustainable Fee/Misc. Rev Others, la clasificación "ESTA es la canónica" según el spec) → `GET
  /revenue/weekly/{fecha}` (semana Lun–Dom vía `dim_calendar`, ya sembrado) → `app/revenue-weekly`
  (Weekly + YTD, parcial y honesto: solo suma días efectivamente cargados).
- **Validación real, no solo reconciliación**: la hoja `Actual` del golden Weekly trae una grilla
  diaria para todo 2026, incluyendo el 2026-06-08 — se comparó columna por columna (Rooms 5023.96,
  F&B 2005.32, Food 1531.32, Beverage 474, SPA 390, Tours 1745.28, Retail 27, Transportation 81,
  Sustainable Fee 287.46, Rooms Others=0, Misc. Rev Others=0, Total 9560.02) y cuadra exacto.
- **Budget en Tabs 3/4 CONECTADO** (2026-07-02): la columna "Budget" de Daily/Weekly ya no está fija
  en 0 — sale de `fact_budget` (Tab 6.1) agrupado por `dim_department.output_column` (§5.1b), la
  misma clasificación que usa Daily. Weekly (que abre por naturaleza, §5.1a) remapea el budget del
  outlet completo a la columna "madre" (Rooms, Sustainable Fee); las columnas *Others* no tienen
  contraparte en el budget por departamento y quedan en 0 (no se inventa un reparto). Si no hay
  presupuesto cargado para el período, `budget_status` lo dice explícitamente y todo sigue en 0 —
  ya no es un bloqueante, es simplemente falta de datos.
  **Verificado con un presupuesto de prueba real** (Rooms $6,000/junio, Sustainable Fee $400/junio):
  Today $200.00 exacto (6000/30 días), MTD (8 días) $1,600.00 exacto, Weekly (7 días) $1,400.00
  exacto, YTD (14 días) $2,800.00 exacto — mismo patrón para Sustainable Fee. Datos de prueba
  limpiados después de verificar; la base queda vacía para cuando Bismark cargue el presupuesto real.

**Bloqueantes que necesitan un archivo o una decisión del owner (Bismark) — no inventar, ver §10 de CLAUDE.md:**
1. ~~Falta el POS/Simphony del 2026-06-08~~ — **RESUELTO 2026-07-01**: Bismark entregó
   `Ventas_08_Junio_2026_FINAL.xlsx` (mismo formato ya validado). Ingestado y auditado de punta a
   punta — ver hallazgos reales en la sección de 2.9 más abajo. Sigue habiendo una discrepancia real
   (POS vs Opera/Integrity F&B, $528.12) que sí es una pregunta abierta para Bismark, pero ya no es
   un bloqueante técnico.
2. TCodes **6480/6485** ("Adjust Deep Connection/Rainforest Delight"): hoy quedan como `DISCREPANCIA`
   porque Opera los registra en negativo y en Integrity aparecen como débito (regla §5.4). Confirmar si
   ese es el comportamiento correcto o si deben netearse.
3. ~~`budget_monthly` bloqueado por layout~~ — **RESUELTO 2026-07-02**: se construyó un flujo propio
   (Tab 6.1: descargar plantilla → llenar → subir → reset anual, §2 decisión cerrada #2) que no
   depende del layout viejo de `12 months Budget 06`. Falta solo que Bismark cargue números reales
   (hoy la base está vacía, se limpiaron los datos de prueba) y conectar Tabs 3/4 a esa fuente.
4. **10 TCodes duplicados** en la hoja `Mapping` del Cash Position
   (`3717,3724,3726,3737,3738,3740,3752,3753,3755,3756`): hoy se conserva la 1ª fila y se descarta el resto
   con un warning — confirmar el mapeo correcto.
5. **Simphony POS del 06-08 vs Opera/Integrity F&B**: el POS vendió $1,477.20 pero Opera/Integrity
   tienen $2,005.32 posteado en F&B ese día (diferencia $528.12). Y la suma del Detalle de Checks del
   propio POS ($1,622.92) tampoco cuadra con su Total Ventas ($1,477.20, diferencia $145.72). Ambas
   son discrepancias reales — confirmar con Bismark el porqué (¿cargos manuales en Opera que no
   pasan por Simphony? ¿checks anulados que quedaron en el detalle?).

---

## Estado del proyecto (actualizado, no confiar en versiones viejas de esta tabla)

| Etapa (CLAUDE.md §9) | Estado |
|---|---|
| 0 · Scaffold (repo, DB `daily_ops`, migraciones, seed, goldens) | ✅ hecho y verificado |
| 1 · Ingesta (Opera + Integrity) | ✅ backend completo — `POST /ingest/{fecha}`, reemplazo total por día, clasifica por contenido |
| 2 · Revenue daily/weekly | ✅ **Daily y Weekly completos** — motor §5.1 (Daily: outlet/DEPT_MAP; Weekly: naturaleza 9-char §5.1a, abre Rooms/Rooms Others y Sustainable Fee/Misc. Rev Others), `GET /revenue/{fecha}` + `GET /revenue/weekly/{fecha}`, Tabs 3 y 4. Validado **al centavo, columna por columna**, contra la fila 2026-06-08 de la hoja `Actual` del golden Weekly. **Budget conectado** a `fact_budget` (Tab 6.1) — en 0 solo si no hay presupuesto cargado |
| 3 · Cash | ✅ **Daily + Weekly + YTD completos** (motor buckets de dos niveles §5.5, `GET /cash/{fecha}` + `GET /cash/weekly/{fecha}`, Tab 5 con 4 pestañas Today/MTD/Weekly/YTD, reconcilia con `payment_total` de Opera al centavo). Depósitos/balance corriendo BLOQUEADO (sin insumo bancario) |
| 4 · Auditoría (portado de `auditoria.py`) | ✅ backend completo — reconciliación real Opera↔Integrity, `audit_run`/`audit_finding` |
| 5 · Room stats + ADR/Occ/Yield | ✅ **completo** — loader de `statroomtype*.XML` → `fact_room_stat`, motor de rollup por categoría (§5.2) con ADR/Occ/Yield Index, integrado a los KPIs de Tabs 3/4 (disponibilidad real, ya no el inventory del OTB) y tabla de categorías en ambos |
| 6 · Frontend — **Tab 2 (Daily Audit)** | 🟢 **completo**, 10/10 sub-tabs con lógica real y datos reales del 06-08, incluido 2.9 (POS real recibido 2026-07-01) |
| 6 · Frontend — **Tab 1 (Data Input)** | 🟢 **completo** — upload real (drag&drop + multipart) → clasifica por contenido (incluye POS) → ingesta → auditoría automática + malla de 365 días × sistema (Incompleto/Listo/Auditado/Cerrado) |
| 6 · Frontend — Tabs 3/4/5 | 🟢 **completos** — Daily/Weekly Revenue, Cash, con datos reales |
| 6 · Frontend — **Tab 6 (Master Data)** | 🟢 **6.1/6.2/6.3/6.5 completos** (CRUD real de mapeos + descarga/carga de Budget con reset anual + diario derivado). 6.4/6.6 sin construir (no bloqueados, features distintas) |
| 7 · Hallazgos (2.10) | ✅ hecho — ahora también captura lo que no cuadra en 2.5 OTB vs Revenue (antes solo tcodes de la reconciliación §5.4), persistido en `audit_finding` |
| 8 · Orquestación + gate + export | ✅ **completo** — Gate + REFRESH (§2.6/§2.7) + Export Excel (Revenue/Cash/Auditoria) y PDF ejecutivo de una página, botones en el Tab 2 |

### Tab 2 · Daily Audit — detalle de lo construido
Los 10 sub-tabs (§4) están navegables en `http://localhost:3000/audit`:
- **2.1 Resumen** · **2.2 Trial Balance** · **2.6 Market Code** (pivote real) · **2.7 Detalle ReCon** ·
  **2.8 Discrepancias** · **2.10 Hallazgos** → con datos reales, verificados en navegador.
- **2.3 Ledgers** → feature completo: saldo corriente día-a-día (`apertura + movimiento = cierre`,
  arrastra automático), **apertura editable** para re-anclar cuando se rompe (tabla `ledger_opening`),
  detalle de **movimiento por TCode** (ata exacto al número, los 4 ledgers), y **folios** del Guest
  Ledger (`fact_bill`, desde `BILLS.xml`+`CUSTOMER.xml` — atan a los pagos liquidados del día, no al
  movimiento bruto; esto está aclarado en la propia UI).
- **2.4 Estadísticas** → completo: KPIs + pivotes por market code y room class + detalle
  (`fact_occupancy_stat`, del XML STATISTICS, migración 0005).
- **2.5 OTB vs Revenue** → completo. Rediseñado (2026-07-01): Full Revenue y Rooms Only son
  reportes de naturaleza distinta (uno es el total del hotel, el otro solo habitaciones) — cada uno
  se reconcilia POR SEPARADO contra el revenue real de Integrity (Opera vs Integrity, §5.4, misma
  tolerancia $0.01), en vez de comparar un OTB contra el otro. La resta Full−Rooms (no-alojamiento)
  queda como dato informativo aparte, no como la reconciliación principal. Golden 06-08: ambas
  reconciliaciones dan OK, diferencia $0.00 (Full Revenue $9,560.02, Rooms Only $5,023.96, ambos
  exactos contra Integrity); no-alojamiento informativo = $4,536.06.
  **Además**, comparación concepto por concepto (Habitaciones/Pax/Inventario/ADR/Ocupación%) contra
  lo real — RN/Pax/Inventario de `fact_room_stat` (Opera, único origen posible: Integrity no tiene
  datos de habitaciones/ocupación) y **Revenue/ADR calculados con el monto que viene de Integrity**
  (el mismo ya reconciliado en `rooms_only_recon`, no el revenue del XML de Opera). Encontró una
  discrepancia genuina: el OTB asume 30 habitaciones disponibles, la realidad ese día fue 22 (2
  categorías sin inventario), lo que hace que la ocupación reportada por el OTB (43.3%) no coincida
  con la real (59.1%). Evidencia visible en la UI, no se oculta.
- **Hallazgos (2.10) ahora también nace de 2.5** (2026-07-01, a pedido del usuario: "todo lo que no
  lleva check debe estar en los hallazgos"): `run_audit()` corre `_otb_vs_revenue` y, además de los
  tcodes de la reconciliación §5.4, agrega un hallazgo por cada reconciliación OTB en DISCREPANCIA
  y por cada concepto operativo (RN/Pax/Inventario/ADR/Ocupación) que no cuadre contra lo real —
  mismas tolerancias que ya usa la UI de 2.5. Golden 06-08: 4 hallazgos (2 tcodes 6480/6485 + 2
  operativos: Inventario -8, Ocupación +15.76pp). 4 tests nuevos.
- **2.8 Discrepancias consolidada con 2.5** (2026-07-01): además de las discrepancias de tcode,
  ahora también lista los hallazgos operativos de OTB (Inventario/Ocupación/etc., sin tcode propio) —
  una sola vista con TODO lo que no cuadra, no solo la reconciliación por tcode. 2.7 (Detalle ReCon,
  todas las filas) no cambió.
- **2.9 Simphony POS** → completo (2026-07-01). Loader real (Excel de Ventas → `fact_pos_check` +
  `fact_pos_summary`, migración 0006) + motor `engine/pos_recon.py` portado de `reference/
  auditoria.py`: (a) consistencia INTERNA del propio Excel (Ventas Netas+Cargos vs Total, Detalle
  de Checks vs Total, Room Charge por forma de pago vs hoja "Mapeo Simphony → Opera") — no depende
  de que el día tenga Opera/Integrity; (b) control de cajeros: POS Total Ventas vs F&B de Opera y de
  Integrity, con el set de tcodes F&B DERIVADO de la misma clasificación por naturaleza de
  `engine/revenue.py` (§5.1a) — no es una regla nueva. Si no hay Opera/Integrity ese día, el control
  de cajeros queda en `null` (no fabrica una discrepancia falsa contra $0). Todo lo que no cuadra
  también genera hallazgo (2.10) y aparece en 2.8, igual que 2.5.
  **Validado primero con el POS del 06-28** (no cruzaba con Opera/Integrity de ese día): Ventas
  Netas+SC=Total ✓, Room Charge por forma de pago=Mapeo ✓, pero la suma del Detalle de Checks no
  coincidía con el Total ($144.02 de diferencia). 5 tests.
  **2026-07-01 — Bismark entregó el POS real del 06-08** (`Ventas_08_Junio_2026_FINAL.xlsx`):
  ingestado y auditado de punta a punta, con Opera/Integrity reales del mismo día. Resultado: Ventas
  Netas+SC=Total ✓ ($1,477.20), Room Charge por forma de pago=Mapeo ✓ ($964.12, 14 checks), **pero
  dos discrepancias reales** — (1) suma del Detalle de Checks ($1,622.92) vs Total Ventas ($1,477.20),
  diferencia $145.72; (2) POS Total Ventas ($1,477.20) vs F&B de Opera/Integrity ($2,005.32),
  diferencia -$528.12 (Opera/Integrity tienen MÁS F&B posteado que lo que Simphony vendió ese día).
  Ambas quedaron como hallazgo en 2.10 y en 2.8 automáticamente. 3 tests nuevos con el golden real
  (8 en total para el motor).

### Insumos ya recibidos y organizados
- `auditoria.py` (script original, 1235 líneas) → copiado en `backend/reference/auditoria.py`, LEÍDO y
  portado a stdlib puro (sin pandas) en `backend/app/ingest/` + `backend/app/engine/reconcile.py`.
- Goldens: `DAILY REV REP AS OF DAY 31.xlsm`, `WEEKLY REVENUE REPORT MASTER FILE.xlsx`,
  `DAILY CASH POSITION MASTER FILE.xlsx` → en `/goldens`.
- Insumos crudos del **2026-06-08** (Opera XMLs REVENUE/STATISTICS/history_forecast×2/BILLS/CUSTOMER/
  CITY_LEDGER + Trial PDF + el Integrity real, mal nombrado `DAILY REVENUE REPORT 2026-06-08.xlsx`
  + **el POS real, `Ventas_08_Junio_2026_FINAL.xlsx`, recibido 2026-07-01**) → en
  `/goldens/inputs/2026-06-08/`. **Día completo: los 4 sistemas (Opera/Integrity/Room Stats/POS)
  ingestados y auditados juntos.**
- POS de un día distinto (**2026-06-28**, `Ventas_2026-06-28_FINAL.xlsx`) → en
  `/goldens/inputs/2026-06-28/`. Sirvió para validar el formato del parser antes de tener el del 06-08.

Ver [`goldens/README.md`](./goldens/README.md) para el detalle de qué falta.

---

## Entorno ya montado en esta máquina
- **PostgreSQL 16** instalado nativo (servicio Windows `postgresql-x64-16`), escucha en **localhost:5433**.
  Superusuario `postgres` / `postgres`. Rol de la app `daily_ops` / `daily_ops`, base `daily_ops`
  (owner `daily_ops`), extensión `pgcrypto` creada. **Startup type = Automatic** → el servicio arranca
  solo si se reinicia Windows, no hace falta levantarlo a mano. Los datos persisten en disco
  (`C:\Program Files\PostgreSQL\16\data`), no se pierden entre sesiones.
- **Python 3.12** (venv en `backend/.venv`) — **3.14 (posible default del sistema) NO compila**
  asyncpg/psycopg2-binary/lxml/pydantic-core. Si el venv no existe, recrear con Python 3.12 explícito.
- `docker-compose.yml` queda como alternativa si se prefiere Docker (mismo puerto 5433); no se usó porque
  Docker no estaba instalado.
- ⚠️ **No correr `npm run build` con el dev server (`npm run dev`) corriendo a la vez** — ambos comparten
  la carpeta `.next` del frontend y se pisan, produciendo errores 500 `MODULE_NOT_FOUND`. Si pasa: matar
  el proceso en :3000, `rm -rf frontend/.next`, y volver a levantar `npm run dev`.
- **`backend/.env`** existe en disco (git-ignorado, pero viaja si se comparte el folder completo) con los
  mismos valores dev de `backend/.env.example` — no son secretos productivos, es Postgres local. Si el
  archivo no está, copiar `.env.example` a `.env` alcanza.
- **No hay git remote configurado** — este repo vive solo local/en el folder compartido. Si se necesita
  un remoto (GitHub, etc.), hay que crearlo y hacer `git remote add origin <url>` explícitamente.

## Arranque local

```bash
# 1. Base de datos: el servicio Postgres 16 ya arranca solo con Windows.
#    (Alternativa Docker: docker compose up -d)

# 2. Backend
cd backend
# venv ya creado con Python 3.12; si hace falta recrearlo:
#   py -3.12 -m venv .venv && ./.venv/Scripts/python -m pip install -r requirements.txt
./.venv/Scripts/python -m alembic -c ../db/alembic.ini upgrade head   # crea/actualiza el esquema
./.venv/Scripts/python -m app.seed                                    # master data determinística (§7)
./.venv/Scripts/python -m app.seed_from_goldens                       # master data extraída de goldens (dept/payment map)
./.venv/Scripts/python -m app.bootstrap_initial_data                  # Budget 2026 + Revenue Actual diario (db/seed_data/*.xlsx, versionados)
./.venv/Scripts/python -m uvicorn app.main:app --reload                # http://localhost:8000  (/docs = OpenAPI)
./.venv/Scripts/python -m pytest -q                                    # 20 tests, deben pasar en verde

**`bootstrap_initial_data`** carga el Presupuesto 2026 (Tab 6.1) y el Revenue
Actual diario Ene-Jun 2026 (Tab 6.4) desde los 2 Excel versionados en
`db/seed_data/` — así un servidor nuevo (ej. el del hotel) queda con los
datos reales sin tener que volver a subirlos a mano desde la UI. Es
idempotente (se puede correr de nuevo sin duplicar nada). Si el presupuesto o
el revenue real se actualizan, reemplazá los archivos en `db/seed_data/` y
volvé a correr el script — no hace falta tocar código.

# 3. Frontend
cd ../frontend
npm install        # ya instalado
npm run dev         # http://localhost:3000  ->  /audit es el Tab 2 completo

# 4. Cargar y auditar un día (ejemplo con el día ya disponible)
curl -X POST http://localhost:8000/ingest/2026-06-08
```

**Equivalente PowerShell** (por si la sesión nueva usa PowerShell en vez de Git Bash):
```powershell
cd backend
.\.venv\Scripts\python.exe -m alembic -c ..\db\alembic.ini upgrade head
.\.venv\Scripts\python.exe -m app.seed
.\.venv\Scripts\python.exe -m app.seed_from_goldens
.\.venv\Scripts\python.exe -m app.bootstrap_initial_data
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
.\.venv\Scripts\python.exe -m pytest -q
```

### API — todos los endpoints existentes (`/docs` tiene el Swagger completo)
```
GET  /health
GET  /properties
POST /ingest/{fecha}                    ingesta + auditoría de un día, lee de goldens/inputs/<fecha> (?prop=, ?run_audit=)
POST /ingest/{fecha}/upload             Tab 1 — upload real (multipart, files[]) + ingesta + auditoría
GET  /ingest/status?year=               Tab 1 — malla de 365 días × sistema (?prop=)
GET  /audit/{fecha}                     payload completo del Tab 2, incluye 'gate' (?prop=)
POST /audit/{fecha}/release             libera a dueños (body: released_by, override_flag, override_note)
POST /audit/{fecha}/refresh             re-ingesta + re-audita, deja traza (body: refreshed_by)
GET  /ledgers/{fecha}                   saldos corrientes de los 4 ledgers (?prop=)
GET  /ledgers/{fecha}/detail?ledger=    detalle auxiliar (movimiento por TCode + folios si aplica)
PUT  /ledgers/{fecha}/opening           re-ancla la apertura de un ledger (body: ledger, amount, note)
GET  /revenue/{fecha}                   Daily Revenue Report — Today+MTD+KPIs+room_categories (?prop=)
GET  /revenue/weekly/{fecha}            Weekly Revenue Report — semana+YTD+room_categories (?prop=)
GET  /cash/{fecha}                      Daily Cash — Today+MTD, buckets de dos niveles (?prop=)
GET  /cash/weekly/{fecha}               Weekly Cash — semana+YTD, buckets de dos niveles (?prop=)
GET  /export/{fecha}/excel              descarga .xlsx (Revenue+Cash+Auditoria) (?prop=)
GET  /export/{fecha}/pdf                descarga .pdf ejecutivo de una página (?prop=)
GET/POST    /master-data/payment-map[/{id}]   CRUD de dim_payment_map (Tab 6.2) (?prop=)
PUT/DELETE  /master-data/payment-map/{id}     editar / borrar un mapeo de pago
GET/POST    /master-data/departments[/{id}]   CRUD de dim_department (Tab 6.3) (?prop=)
PUT/DELETE  /master-data/departments/{id}     editar / borrar un departamento
GET  /master-data/budget/template?year=       descarga plantilla Excel de Budget, año (Tab 6.1)
POST /master-data/budget/upload?year=         sube la plantilla llena — reset anual + deriva diario
GET  /master-data/budget?year=                vista mensual por depto cargada (Tab 6.1) (?prop=)
GET  /master-data/budget/daily?year=&month=   vista diaria derivada (Tab 6.5) (?prop=)
```

## Estructura

```
/backend
  /app/ingest      parsers puros (Opera, Integrity, POS, Bills, statroomtype) — sin pandas, de auditoria.py
  /app/engine      reconcile, revenue, cash, room_stats, gate, pos_recon, budget — motores puros (§5), sin DB/UI
  /app/services    ingest/audit/ledger/revenue/cash/export/master_data/budget_service — orquestan parseo→DB→motor
  /app/api         routers FastAPI (ingest, audit, ledgers, revenue, cash, export, master_data, budget)
  /app/export      excel.py (openpyxl) y pdf.py (fpdf2) — arman el archivo desde payloads ya calculados
  /app/models      ORM SQLAlchemy (fuente de verdad del esquema junto con db/schema.sql)
  /reference       auditoria.py original (leído, no se ejecuta) + inspect_inputs.py (utilidad de inspección)
  /tests           pytest — incluye tests golden contra los datos reales del 06-08
/db                Alembic (migraciones 0001-0006) + db/schema.sql (DDL baseline de la 0001)
/frontend          Next.js 14 — Tabs 2/3/4/5 completos; Tabs 1/6 son placeholders (tabs §4)
/goldens           Excels de validación + /inputs/<fecha>/ con los insumos crudos recibidos
/docs              CLAUDE.md (spec) + INGESTA_CONTRATO.md (contrato real, con diffs vs el spec)
```

## Decisiones de modelado (marcadas `TODO(bismark)` donde correspondía una decisión de negocio)
- **`property_id`** = FK `UUID` → `dim_property(id)`. `dim_property.code` guarda el código natural (`COWLCR`).
- **`dim_calendar`** es global (sin `property_id`); generado por código, semanas Lun–Dom sin huecos (corrige bug §6.1 del Excel).
- Alembic vive en `/db`; `env.py` importa los modelos del backend.
- **`dim_department.cuenta_nature`** es nullable: el `DEPT_MAP` real solo trae outlets 4-díg (`cost_center`+`output_column`), no el mapa de naturaleza 9-char completo (§5.1a) — ese falta como insumo.
- **Ledgers (2.3):** saldo corriente = suma acumulada desde el anclaje manual más reciente (o desde el inicio si no hay anclaje) + movimiento de cada día. Editar la apertura de una fecha = reiniciar la acumulación desde ahí ("empezar bien").
- **`gate_hard`** default `false` (política suave) — pendiente que Bismark confirme el default definitivo.

## Snapshot verificado (última vez que se corrió todo, no confiar si pasó mucho tiempo)
Confirmado en la sesión que dejó el commit `e2cca74`+POS real del 06-08: 57/57 tests pasan,
`alembic current` = `0006 (head)`, servicio Postgres `Automatic`/`Running`, backend
`GET /health` → `db:up`, frontend `/audit`, `/revenue-daily`, `/revenue-weekly`, `/cash`,
`/data-input`, `/master-data` → `200`.
Conteos de filas para el día 2026-06-08 (propiedad `COWLCR`) tras un `POST /ingest/2026-06-08`
**con los 4 sistemas** (Opera + Integrity + Room Stats + POS, día completo):

| Tabla | Filas |
|---|---|
| `dim_property` | 1 |
| `dim_department` | 17 |
| `dim_payment_map` | 66 |
| `fact_opera_txn` | 36 |
| `fact_opera_txn_detail` | 276 |
| `stg_integrity_line` | 43 |
| `fact_bill` | 2 |
| `fact_bill_line` | 22 |
| `fact_occupancy_stat` | 8 |
| `fact_otb` | 2 |
| `fact_room_stat` | 4 (solo 4/6 categorías — Corcovado Deluxe y Carate Deluxe sin inventario ese día) |
| `fact_pos_check` | 24 |
| `fact_pos_summary` | 1 |
| `audit_run` | 1 (kpi_ok=33, kpi_discrepancia=2, kpi_faltante=0) |
| `audit_finding` | 7 (2 tcodes 6480/6485 + 2 OTB operativos + 3 Simphony POS) |
| `ledger_opening` | 0 (sin anclajes manuales cargados — los que se probaron en desarrollo se borraron) |

KPIs reales del día (Revenue/Cash/Room Stats/POS, todos reconcilian entre sí salvo lo ya
documentado como hallazgo): revenue total $9,560.02, Rooms $5,023.96, RN=13, Pax=20,
disponibles=22 (no 30), ADR=$386.46, ocupación=59.1%, cash real recibido=$317.87. POS: Ventas
Netas $1,402.80 + Cargos $74.40 = Total $1,477.20, Room Charge confirmado $964.12 (14 checks) —
pero F&B posteado en Opera/Integrity ($2,005.32) no coincide con lo vendido en POS ($1,477.20),
diferencia $528.12 (hallazgo abierto, ver bloqueantes).

Si estos números no coinciden después de retomar, algo cambió (o hace falta re-ingerir el día).
