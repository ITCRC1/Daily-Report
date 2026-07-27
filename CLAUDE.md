# CLAUDE.md — DAILY-OPS

> **Lee este archivo COMPLETO antes de escribir una sola línea de código.**
> Contiene la misión, el modelo de datos, todas las reglas de negocio, el orden de construcción y los criterios de validación. Las decisiones ya están tomadas; tu trabajo es convertir este spec en software funcional.
> Documento de contexto largo: `PLANTEAMIENTO_DAILY_OPS.md`. Contrato de ingesta: `BITACORA_INSUMOS_AUDITORIA.md`. Script a portar: `auditoria.py`.

---

## 0. MISIÓN Y AUTONOMÍA

**Qué construyes:** DAILY-OPS, una app web que unifica en un solo sistema tres reportes que hoy viven en Excel + Power Query y un script de auditoría en Python, para SCP Corcovado Wilderness Lodge (`COWLCR`) — Revenue diario, Revenue semanal, Posición de efectivo y Auditoría diaria de ingresos.

**Principio rector:** la app **absorbe** los Excel actuales, no los reemplaza a mano. Los formatos de salida se vuelven **vistas** que la app reproduce **idénticas** (validadas contra golden files a tolerancia **$0.01**). Las tablas de configuración se vuelven **master data** editable.

**Prueba de éxito:** subir los archivos crudos de un día conocido → obtener exactamente lo mismo que produce el Excel hoy.

**Cómo trabajar (modo autónomo, sin aprobaciones):**
1. Lee este CLAUDE.md y los golden files de referencia.
2. Construye en el orden de §9, un módulo a la vez.
3. Corre los tests después de cada módulo (§8). Si un test falla, **corrige antes de seguir**.
4. No inventes reglas de negocio. Si algo es ambiguo, deja un `TODO(bismark):` visible y sigue con lo demás; no adivines umbrales, nombres ni políticas.
5. No pares hasta que todos los módulos estén completos y los tests pasen.

---

## 0.1 EFICIENCIA: QUÉ MODELO USAR EN CADA FASE

Cambiá de modelo con `/model` según la fase. Regla base: **Opus para razonamiento, correctitud y depuración; Sonnet para volumen, boilerplate y UI.** (Con Max 5x hay headroom, pero esto acelera lo mecánico y reserva el presupuesto pesado para donde importa.)

| Fase (§9) | Modelo | Por qué |
|---|---|---|
| 0 Scaffold | **Sonnet** | Traducir el esquema (ya especificado) a migraciones/seed es mecánico. |
| 1 Ingesta Integrity | **Opus** el parser+cálculo, luego Sonnet para repetir | Correctitud crítica (se valida a $0.01). |
| 2 Revenue daily/weekly | **Opus** el cálculo (mapa 9-char, budget derivado), Sonnet las vistas | Evita el fallback mal clasificado. |
| 3 Cash | **Opus** los dos niveles de bucket + UNMAPPED, Sonnet los cortes | Lógica sutil. |
| 4 Auditoría (portar `auditoria.py`) | **Opus** | Lo más complejo: reconciliación, signos, estados, XML/POS, OTB. |
| 5 Room stats + ADR/Occ/Yield | **Opus** el cálculo, Sonnet la presentación | Fórmulas exactas. |
| 6 Frontend (dashboard, tabs, REFRESH) | **Sonnet** | UI de alto volumen; Sonnet es rápido en Next/React. |
| 7 Hallazgos (workflow 2.10) | **Sonnet** | CRUD + UI. |
| 8 Orquestación + gate + export | **Opus** gate/orquestación, Sonnet export | Lógica de control vs formato mecánico. |

**Escalado dinámico:**
- Si un **test golden falla** y estás depurando → **Opus** hasta que pase.
- Si **Sonnet** se traba (2 intentos fallidos en la misma tarea) → escalá a **Opus**.
- Si la tarea es puramente repetitiva (otra vista igual, otro CRUD) → bajá a **Sonnet**.
- Comando: `/model opus` o `/model sonnet` al inicio de cada fase.

## 0.2 PROTOCOLO DE FEEDBACK (procesos largos)

Trabajá por **checkpoints** (uno por módulo). En cada checkpoint —y siempre que una tarea supere ~5 min— **antes de arrancar el siguiente módulo, re-leé los últimos mensajes del chat**:
- Si hay **feedback nuevo relevante** (corrige una regla, cambia una prioridad, aclara un `TODO`): **aplicalo de inmediato** antes de seguir y confirmá en una línea qué cambiaste.
- Si el mensaje **no es relevante** para lo que estás construyendo: anotalo como `NOTA(bismark): …` y seguí sin desviarte.
- **Nunca ignores en silencio** un mensaje del usuario ni lo dejes para el final.
- Para feedback urgente a mitad de un proceso, el usuario interrumpe con **Esc** e inyecta el mensaje; retomá incorporándolo. (Claude Code no vigila el chat durante una generación ininterrumpida — checkpoints + Esc son el mecanismo real.)

---

## 1. STACK Y ESTRUCTURA

- **Backend:** FastAPI (Python). Porta `auditoria.py` como núcleo de reconciliación (parsers XML Opera + POS ya están ahí).
- **DB:** PostgreSQL, base dedicada **`daily_ops`** (NO compartir instancia lógica con PlanificaCR).
- **Frontend:** Next.js. Dashboard con **selector de día (dropdown global)**: se elige la fecha y todas las vistas muestran ese día.
- **Ingesta:** parsers propios que reemplazan Power Query (lógica en §5) + parsers de `auditoria.py`.

```
/backend    FastAPI + ingesta + reconciliación (auditoria.py portado)
/db         migraciones + seeds de master data (§7)
/frontend   Next.js (tabs §4)
/goldens    Excels actuales como fixtures de validación (§8)
/docs       este CLAUDE.md + planteamiento + bitácora
```

---

## 2. DECISIONES CERRADas (no reabrir)

1. **Multi-property desde el día uno** (`property_id` en TODO). v1 se desarrolla y valida **solo en Corcovado** (`COWLCR`); luego se "coloniza" a Ojochal/Oxigen/Amarena sembrando catálogos, **sin cambio de esquema**.
2. **Presupuesto manual, mensual por departamento** (Tab 6.1). Descarga Excel bloqueado → copy-paste → upload. **Reset anual**. El diario se **deriva** (mensual ÷ días del mes).
3. **Entrega = dashboard** con selector de día. Sin correo/Drive automático. Export PDF/Excel opcional.
4. **Multiusuario.** Roles: `admin` (Controller), `income_auditor` (operador principal de la corrida), `viewer` (dueños, solo lectura). **La corrida la puede correr cualquier usuario con rol de escritura**, no solo el auditor.
5. **Re-carga = reemplazo total por día:** volver a subir un día **borra** las líneas de ese día y reingesta; solo el último batch queda vigente (sin versionado).
6. **Estabilidad + REFRESH:** un daily, una vez calculado/enviado, **queda igual**; no se auto-recalcula. La única forma de actualizarlo es un **botón REFRESH por día** (acción explícita, deja traza).
7. **Gate configurable** (`app_config.gate_hard`): controla si un daily puede enviarse a dueños con una discrepancia abierta. **Default: suave** (se permite enviar con `override_flag` + `override_note`, todo logueado). Construir ambas conductas; la política se cambia con el flag, sin tocar código. `TODO(bismark): confirmar default definitivo suave vs duro.`
8. **Ingesta por batch de un día:** clasificar por **contenido**, no por nombre de archivo. `business_date` la asigna el batch, NO se parsea del filename.

---

## 3. MODELO DE DATOS (PostgreSQL)

### Convenciones (todas las tablas)
- **PK:** `UUID` (`gen_random_uuid()`).
- **Timestamps:** toda tabla editable lleva `created_at` y `updated_at` (default `now()`, trigger en update). Aplica a `budget_monthly` y todos los `dim_*`.
- **Índices:** `business_date` en todos los hechos y en staging; `property_id` en todo; `tcode` en staging, `fact_opera_txn`, `dim_opera_revenue_cat`, `dim_payment_map`; todas las FKs indexadas.
- **Constraints:** montos `NUMERIC(15,2)`; `CHECK` de no-negatividad donde aplique; estados con `DEFAULT` y `CHECK` sobre el set válido.
- Todo hecho y catálogo cuelga de `dim_property`.

### Staging
`stg_integrity_line` — grano: una línea de mayor.
```
property_id, business_date, source_file, ingest_batch_id,
cuenta, nombre_cuenta, centro_costo, referencia, detalle,
moneda_fuente, tc, deb_col, cred_col, deb_usd, cred_usd,
tcode              -- parseado de Referencia (dígitos)
```
Revenue y cash **derivan de aquí**; no se re-ingiere.

### Hechos (todos con `property_id`)
- `fact_room_stat` — `business_date, room_category, room_revenue, stay_rooms, stay_persons, physical_rooms`. Fuente: Opera `statroomtype` (tabla `InputsSTATS`): `ROOM_REVENUE, STAY_ROOMS(=RN/occupied), STAY_PERSONS(=PAX), PHYSICAL_ROOMS(=available), SHORT_DESCRIPTION, BUSINESS_DATE`. Disponibilidad del día = Σ `physical_rooms` (no hay constante hardcodeada).
- `budget_monthly` (input manual) — `year, month, dept_id, amount_usd` + stats mensuales `available_rooms, rooms_occupied, guests, occupancy_pct, adr` + detalle F&B `food, beverage, misc`. **Check de integridad:** total F&B = food + beverage + misc.
- `fact_budget` (derivado) — `date, dept_id, amount_usd` = `budget_monthly / días_del_mes` (pareja). El **residual de redondeo** va al último día del mes (largest-remainder) para que Σ diarios = mensual exacto. Confirmado: 121,219.07 / 31 = 3,910.29.
- `fact_opera_txn` — `business_date, tcode, description, type, total, guest_ledger, package_ledger, ar_ledger, deposit_ledger`.
- `fact_pos_check` — `business_date, restaurant, employee, check_num, hora, forma_pago, monto, is_room_charge`.

### Dimensiones (master data, editable desde Tab 6)
- `dim_property` — `property_id, code, name, hotel_code, activa`. (`COWLCR` = Corcovado.)
- `dim_department` — `property_id, cuenta_nature, cost_center, outlet_name, output_column`. Dos dimensiones (§5.1).
- `dim_room_category` — `property_id, code2, report_name, opera_short_desc`.
- `dim_payment_map` — `property_id, transaction_code, code, description, banco_codigo, banco_nombre, moneda, tipo_pago, marca_metodo, grupo, cash_flow, canal, report_bucket`.
- `dim_market_code` — `property_id, code, name` (TAFIT, WEB, DIR, COM, CORP, GRP).
- `dim_opera_revenue_cat` — `property_id, tcode, categoria` (para OTB vs Revenue).
- `dim_calendar` — `date, iso_week, week_start, week_end, week_label, month, year`. **Semanas Lun–Dom, GENERADO** por código; `week_label` = `W26 | 22-Jun-2026 to 28-Jun-2026`.

### Dominio de auditoría
- `audit_run` — `property_id, business_date, status(abierto|cerrado), kpi_ok, kpi_discrepancia, kpi_faltante, generated_at, released_at, released_by, refreshed_at, refreshed_by, override_flag, override_note`.
- `audit_finding` — `property_id, business_date, source_view, area, persona, tcode, monto, tipo_desviacion, cobrar_empleado, charged_by, estado(abierto|cerrado), comentario, created_at, updated_at`.

### Ingesta y control operativo
- `ingest_batch` — `id, property_id, business_date, uploaded_at, uploaded_by`. Un batch = una carga de un día. Re-carga = reemplazo total (§2.5).
- `ingest_day_status` — `property_id, business_date, sistema(opera|integrity|pos), estado(Incompleto|Listo|Auditado|Cerrado), updated_at`. Es el estado que pinta el Tab 1 (malla 365 días × sistema).
- `app_config` — `property_id, key, value`: `recon_tolerance` (0.01), `gate_min_set` (Opera+Integrity), `gate_hard` (bool).
- `app_user` / `role` — roles §2.4; alimentan `released_by`, `charged_by`, `refreshed_by`.

### Estabilidad y REFRESH
Un daily calculado/enviado queda inmutable salvo **REFRESH** explícito (botón por día en Tab 1) que re-lee los insumos vigentes y recalcula (actuals + presupuesto + auditoría), dejando traza. Mientras el día esté abierto, la re-carga reemplaza libremente; tras enviarse, solo cambia vía REFRESH.

---

## 4. ESTRUCTURA DE TABS (frontend)

**Tab 1 — Data Input.** Carga por batch de un día completo (Opera + Integrity + Simphony juntos); clasifica por contenido y asigna al día. El lunes = 3 batches (vie/sáb/dom). Malla de 365 días × sistema con estado (Incompleto/Listo/Auditado/Cerrado). Refresca snapshots YTD de Opera. **Botón REFRESH por día.**

**Tab 2 — Daily Audit** (solo diaria; no hay auditoría semanal). Sub-tabs:
- 2.1 Resumen Ejecutivo (KPIs cuadradas/discrepancias/faltantes + totales)
- 2.2 Trial Balance (TCodes por tipo + ledgers)
- 2.3 Ledgers (Guest / AR / Deposit / Package)
- 2.4 Estadísticas Ocupación (por market code / room class)
- 2.5 OTB vs Revenue (HF full vs rooms)
- 2.6 Ingresos x Market Code (pivot revenue × market code)
- 2.7 Detalle ReCon (línea por TCode)
- 2.8 Discrepancies (desviaciones crudas)
- 2.9 Simphony POS (checks, formas de pago, room charges → Opera, control de cajeros)
- 2.10 Hallazgos (workflow sobre `audit_finding`: comentario, estado abierto/cerrado, área, persona/"glitch por persona", cobro a empleado; consultable por área/persona/período)

**Tab 3 — Daily Revenue Report.** Today / MTD / Full Month por revenue center, Actual vs Budget vs Varianza (golden: `Summary`).

**Tab 4 — Weekly Revenue Report.** Listo para enviar (golden: `Weekly`). Encabezado Week #/Start/End/Label; columnas Weekly + YTD (Actual/Budget/Var $/Var %); revenue por depto (F&B en Food/Beverage/Misc) + Rooms Others + Misc + Total; stats RN/Pax/Occupied/Occupancy %/ADR. Semanas Lun–Dom.

**Tab 5 — Daily Cash from Operation.** Posición de efectivo (golden: `DAILY_CASH_POSITION`): pagos por día/semana/mes/YTD, depósitos entrados vs aplicados, por marca de tarjeta, por banco/bucket, por canal y moneda, balance corriendo.

**Tab 6 — Master Data** (editable, por propiedad): 6.1 Monthly Budget by Department (+ botón reset anual), 6.2 Cash Mapping, 6.3 Integrity Mapping, 6.4 Daily Revenue by Day by Dept, 6.5 Daily Budget by Day and Dept, 6.6 Rooms Revenue by Month by Room Type.

---

## 5. REGLAS DE NEGOCIO (ESTO ES EL MOTOR)

### 5.1 Departamentos — DOS dimensiones
Cada cuenta `4NNN-0NNN-…` tiene **naturaleza** (prefijo `4NNN`) y **outlet/centro de costo** (`0NNN`).

**(a) Naturaleza — 9-char** (`Text.Start(Cuenta,9)`, cuentas `4%`) — ESTA es la canónica (consulta `Query food&Beverage`):
`4000-0110`=Rooms · `4110*/4120*`=F&B FOOD · `4125*/4130*/4131*`=F&B BEVERAGE · `4132*`=F&B MISC. · `4201-0140`=SPA · `4305/4307/4316/4320-0151`=Retail-Gift Shop · `4400-0150`=Tours · `4500-0152`=Transportation · `4600-0155`=Innoceana · `4700-0160`=Laundry · `4800/4820/4850-0170`=Misc. Rev Others · `4880-0170`=Sustainability Fee. **ELSE → "Otros"** (excepción visible).

**Columnas de salida canónicas (12), en este orden:** Rooms, F&B FOOD, F&B BEVERAGE, F&B MISC., SPA, Retail-Gift Shop, Tours, Transportation, Laundry, Innoceana, Sustainability Fee, Misc. Rev Others.

**(b) Outlet — 4-díg** (`Text.Middle(Cuenta,5,4)`): `0110`=Rooms, `0140`=SPA, `0150`=Tours, `0151`=Retail, `0152`=Transportation, `0155`=Innoceana, `0156`=Crowther Lab (gancho, sin cuenta activa hoy), `0160`=Laundry, `0170`=Sustainable/Misc; F&B: `0123`Vitrales, `0124`Sueños del Bosque, `0125`Pool, `0126`Beach, `0127`Room Service, `0128`Private Bar, `0129`Banquets & Events, `0130`Terrakitchen → todos `OutputColumn=F&B`.

### 5.2 Categorías de habitación (últimos 2 díg de `4000-0110-…`)
`01` Corcovado Deluxe Villas · `02` Carate Deluxe Villa · `03` Agujas Villa · `04` Sirena Suites · `05` Treehouse King · `06` 5 Elements Treehouse · `00` Other Rooms Revenue.
`opera_short_desc` exactos (para join/seed): `01`→"Corcovado Deluxe", `02`→"Carate Deluxe", `03`→"Agujas Villa", `04`→"Sirena Suites", `05`→"Treehouse", `06`→"5 Elements".

### 5.3 Montos
Revenue USD = `Créditos − Débitos`. Cash `Amount USD Eq = Débitos − Créditos` (opuesto); `Amount CRC Eq = Débitos Col − Créditos Col`. ADR = Room Revenue / RN. Occ física = STAY_ROOMS / PHYSICAL_ROOMS. Yield = ADR categoría / ADR overall.

### 5.4 Reconciliación (núcleo — portar de `auditoria.py`)
Llave **TCode** (Opera `transaction_code` ↔ Integrity `Referencia`→dígitos). Regla de signo: para `type=PAYMENT`, lado Integrity = `−int_db`; resto = `int_cr`. `diferencia = integrity − opera`. Estados: `OK` (|dif|<0.01) · `DISCREPANCIA` · `FALTA EN INTEGRITY` · `FALTA EN OPERA` · `INTERNO` (INTERNAL/PACKAGE). ADR de auditoría = Accommodation (tcode 1000) / total rooms. **Gate:** el daily se libera a dueños según `app_config.gate_hard` (§2.7).

### 5.5 Buckets de cash (dos niveles)
TCode → `report_bucket` vía `dim_payment_map`. **Cash-relevant (amplio):** `Banco Código ∈ {BAC,BCR,BNCR,LAF,CASH,SINPE,ROOM,HOUSE,AR}`. **Bank-only (estricto, para Bank Recon):** `Tipo Pago ∈ {Tarjeta,Transferencia}` **y** `Banco Código ∈ {BAC,BCR,BNCR,LAF}`. Flag `cash_flow`: Real Cash vs Non-Cash. **UNMAPPED:** un TCode de pago sin entrada en el mapping debe **surgir como excepción visible**, NO descartarse en silencio.

### 5.6 Catálogos de auditoría
- **Market Code** (`dim_market_code`): TAFIT=Agencia · WEB=Website · DIR=Directo · COM=Complementario · CORP=Corporativo · GRP=Grupo.
- **Opera TCode → categoría** (`dim_opera_revenue_cat`, para OTB vs Revenue): Accommodation `1000` · Retail `2320,2321,2324,2330,2490` · Sustainable `3005` · Boat `3320` · F&B Terra `2139,2140,2142,2143,2149,2161` · F&B Bosque `2224,2225,2227,2228,2233,2234,2245,2246,2249` · Packages `2500,2502,2504,2507` · Tours `3400,3405,3406,3407,3411`.
- **OTB vs Revenue:** total_rev (HF full) vs rooms_rev (HF rooms); diferencia = no-alojamiento por habitación. HF: mayor=Total, menor=Rooms Only (≥2 archivos).
- **POS→Opera:** room charges confirmados (`AnswerStat=OK`); control de cajeros por empleado (base del "glitch por persona").
- **RN/PAX/room-revenue actuales = Opera** (`InputsSTATS`); la extracción por celdas del Integrity está vacía → NO usarla.

### 5.7 Limpieza de ingesta (centralizar una vez)
Por archivo Integrity: hoja `Datos`, `skip 8`, promote headers, `Text.Trim`, `try Number.From … otherwise 0`, null→0, filtro `Cuenta LIKE '4%'` (revenue) o join a `dim_payment_map` (cash). TCode = `Text.Select(Referencia, dígitos)`.

---

## 6. BUGS DEL EXCEL ACTUAL — CORREGIR, NO REPLICAR
1. **Calendario semanal roto** (`CAL_WEEKS_2026` tiene días huérfanos 17–19 may) → generar Lun–Dom por código, sin huecos.
2. **Fecha "hoy" hardcodeada** (`#datetime(2026,5,1)` en ~7 consultas) → derivar del día.
3. **Sprawl de carpetas** (`INPUT`/`INPUTCASH`/`WEEKLY\INPUT`, inconsistente dentro del propio weekly) → **una sola ingesta**.
4. **Fallback mal clasificado:** `q_Today`/`Query1` mandan cuentas no reconocidas a "Sustainability Fee". Usar el mapa 9-char con **ELSE → "Otros"**.
5. **Fecha desde filename** (últimos 10 chars) → `business_date` del batch.
6. **Consultas duplicadas/redundantes** (`tblMapping (2)` = copia; 4 consultas daily se solapan con la canónica) → consolidar a una ingesta + un mapa.

---

## 7. SEED DE MASTER DATA (Corcovado v1)
| Catálogo | Fuente |
|---|---|
| `dim_property` | fila `COWLCR` = Corcovado (primero, antes que todo) |
| `dim_department` | Power Query 9-char + `DEPT_MAP` |
| `dim_room_category` | Query2 (últimos 2 díg) + `SHORT_DESCRIPTION` Opera (§5.2) |
| `dim_payment_map` | hoja `Mapping`/`tblMapping` del libro de Cash |
| `dim_market_code` | `auditoria.py` |
| `dim_opera_revenue_cat` | `auditoria.py` |
| `budget_monthly` | plantilla mensual (imagen provista) |
| `dim_calendar` | **generado** por código (Lun–Dom) |

---

## 8. VALIDACIÓN (golden files) — DEFINITION OF DONE
Por cada vista, un test que alimenta inputs crudos de un día conocido y compara contra el Excel actual a **tolerancia $0.01**:

| Golden | Vista |
|---|---|
| `DAILY_REV_REP…` → `Summary` | Daily Revenue |
| ídem → `Room Statistics` | ADR / Occ / Yield |
| `WEEKLY…` → `Weekly` | Weekly / YTD |
| `DAILY_CASH_POSITION…` → Flash/Recon/Bank/Brand | Cash |
| salida de `auditoria.py` (pestañas) | Reconciliación + KPIs |

Un módulo está "done" cuando su test pasa.

---

## 9. ORDEN DE CONSTRUCCIÓN (modular — una etapa a la vez)
*Modelo recomendado por fase: §0.1. Revisá el chat en cada checkpoint: §0.2.*
0. **Scaffold** — repo, Postgres `daily_ops`, migraciones (incluye `ingest_batch`, `ingest_day_status`, `app_config`, `app_user`/`role`), seed §7, goldens en `/goldens`.
1. **Ingesta Integrity** → `stg_integrity_line`. Test: conteo + sumas.
2. **Revenue (daily/weekly)** → validar `Summary` / `Weekly`.
3. **Cash** → validar Flash/Recon/Bank/Brand.
4. **Auditoría** — portar `auditoria.py` (parsers Opera XML + POS) → reconciliación por TCode → `audit_run` + `audit_finding`. Validar pestañas.
5. **Room stats + ADR/Occ/Yield** → validar `Room Statistics`.
6. **Frontend** — dashboard + selector de día + tabs (§4) + botón REFRESH.
7. **Hallazgos (2.10)** — comentarios, estado, cobros, vistas por área/persona.
8. **Orquestación** — batch por día → corre todo → gate (§2.7) → export.

---

## 10. GUARDARRAÍLES
- No reproduzcas los bugs de §6.
- No decidas políticas de negocio: si falta una (ej. `gate_hard` definitivo), déjala configurable con default y marca `TODO(bismark:)`.
- `business_date` viene del batch, nunca del filename.
- UNMAPPED (cash) y ELSE (revenue) = excepciones visibles, nunca descartes ni recategorices en silencio.
- Todo cálculo de un día cerrado es inmutable salvo REFRESH explícito.
- Valida contra los golden files a $0.01 antes de dar por hecho un módulo.

---

*Al terminar: todos los módulos construidos, todos los tests de §8 en verde, un solo `TODO(bismark:)` pendiente (default del gate). Listo para producción.*
