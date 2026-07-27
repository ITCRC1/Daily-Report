# DAILY-OPS — Plan por fases (roadmap)

> Guardado 2026-07-18. Estado y decisiones acordadas con el owner (Bismark).
> Para retomar en cualquier momento: "seguimos con el Tab 9" (o la fase que toque).

---

## FASE 0 — Infraestructura administrativa — ❌ AUTH ELIMINADA (2026-07-27)
- **Auth: BORRADA por pedido del owner.** El app no tiene login, ni password compartido, ni usuarios/roles: se entra directo por la URL. Se eliminaron `backend/app/deps.py`, `services/auth_service.py`, `api/auth.py`, `api/admin_users.py`, la página `/login` y el `AuthGate` del frontend. Las tablas `app_user`/`role` quedan en la base (el backup las trae; borrarlas rompería el restore), pero ya no las usa nadie. Si se quiere restringir el acceso, va por fuera del app: red privada, VPN o un proxy con auth adelante.
- **Página `/admin`** (⚙ en la nav): prender/apagar **tabs y sub-tabs** por propiedad (`config/nav`, guardado en `app_config`). Entra directo, sin desbloqueo.

## FASE 1 — Tab 9 · Daily Extendido (EN CURSO) — replicar el Daily Revenue Report FS **al pie, 1 a 1 cada página**
Fuente: `Daily Revenue Report FORMAT.pdf` (Four Seasons, 11 pág, USALI). NO simplificar.
- **1.1 ✅ 9.1 Summary** (pág 2) — datos reales: rooms stats + revenue por categoría (motor sobre Integrity, `merged_revenue_actual`) + budget MTD. Forecast/Año-ant/additional-stats = "—" (van en la carga). `daily_extended_service.py`, `GET /daily-extended/summary`.
- **1.2 ✅ 9.3 Rooms by Segment** (pág 5-6) — RN · Occ% · Rev · ADR por segmento/market code, columnas Today + MTD, agrupado por grupo de negocio (Direct/OTA/Travel Agency/Groups/Other) con subtotales y total. Reutiliza el pivote del Tab 7.10 (`market_code_service`: RN/Pax del XML Statistics + Room Revenue del XML Revenue) y agrega Occ% (RN seg / hab. disponibles) y ADR (Rev/RN). `daily_extended_service.rooms_by_segment`, `GET /daily-extended/rooms-by-segment`. Verificado: Today reconcilia 1:1 con 9.1 (RN 13, Rev $5,023.96, ADR $386.46). **Lo que el owner más quiere.**
- **1.3 Plantilla Excel de carga** que replica el formato — para lo que NO existe en el sistema (Forecast, Año anterior, F&B por período, Spa por servicio, Additional Rooms Stats: Arrivals/Departures/ALOS/Children/Walkins) **y** para propiedades sin feed automático (clave multi-propiedad).
- **1.4 ✅ 9.2 Revenue Detail** (pág 3-4) — revenue por outlet (dept_code), detalle de lo que 9.1 colapsa por categoría. Secciones: Rooms / F&B / Spa / Guest Support & Activities / Other Operating, con Today + MTD Actual + Budget + Var y subtotales + total. Mismo motor sobre Integrity (`merged_revenue_actual`) + budget por cost_center (`_budget_by_dept_cost_center`); dept_codes no mapeados → "Other" (§10). `daily_extended_service.revenue_detail`, `GET /daily-extended/revenue-detail`. Verificado: cada sección reconcilia 1:1 con la categoría del 9.1 y el total ($9,560.02 today / $72,234.94 MTD / $48,055.04 budget para 06-08).
- **1.5 ❌ 9.4 Residential Rental** (pág 7-8) — villas. **OMITIDO: COWLCR no tiene residencial/villas** (confirmado por el owner 2026-07-18). Sub-tab retirado de la nav.
- **1.6 ✅ 9.5 F&B by Meal Period** (pág 9-11) — desde **Simphony POS** (`fact_pos_check`: restaurant + hora + check_num + monto). Meal period derivado de la hora (Breakfast 05-10 / Lunch 11-16 / Dinner 17-23 / Other). Por período × revenue center: Checks (cheques distintos por (fecha,check_num)) · Revenue · Avg Check, Today + MTD, subtotales + total. `daily_extended_service.fb_by_meal_period`, `GET /daily-extended/fb-by-meal-period`. Verificado 06-08: 24 checks $1,622.92 (Terra Kitchen 18/$1,307.42, Corcovado 6/$315.50). ⚠️ Fuente POS ≠ Integrity (9.1/9.2) — no cuadra 1:1 con lo posteado (eso audita Tab 2.9); split Food/Beverage y covers vienen de la carga (1.3).
- **1.7 Export PDF** del Tab 9 completo (mismo look del formato).

## FASE 2 — ~~Activar la protección en el servidor final~~ CANCELADA (2026-07-27)
El owner pidió sacar el login por completo y el código se eliminó (ver Fase 0).
Si algún día se quiere volver a cerrar el app, hay que construirlo de nuevo o
resolverlo por infraestructura (VPN / proxy con auth). `CREDENTIALS.local.md`
quedó sin uso — se puede borrar.

## FASE 3 — Multi-propiedad (gemelear) — **cada propiedad SEPARADA** (app + DB + deploy propios)
Decisión: NO una app multi-tenant; Corcovado (DAILY-OPS) es la **plantilla**. Reusar el núcleo genérico (Cash Flow Forecast, Cash Position, P&L, dashboards, Tab 9).
- Por cada propiedad nueva:
  1. Clonar el esqueleto (auth, deploy, modelo base, módulos genéricos).
  2. **Adaptador de ingesta** para SUS sistemas — las otras propiedades **no usan OPERA/Simphony/Integrity**; se adapta a sus archivos (o carga 100% manual con la plantilla de Fase 1.3).
  3. **Prender solo los tabs/sub-tabs que aplican** desde `/admin` (muchos desarrollos de COWLCR no aplican a otras).
- La **carga manual de estadísticas** (Fase 1.3) es la llave para las propiedades sin sistema del cual leer.

---

## Cómo está el paquete
- Todo commiteado en GitHub (`brodriguez7301-dot/daily-ops`, privado). Backup completo en `db/backups/prod_data_latest.sql` (se regenera en cada commit; restaurar = `alembic upgrade head` + `psql -f`). Ver `HANDOFF.md`.
- Backend prod: `backend-production-15f24.up.railway.app` · Frontend: `daily-ops-bay.vercel.app`.
