# HANDOFF — DAILY-OPS (Corcovado Wilderness Lodge / COWLCR)

App web de revenue/cash/auditoría diaria + On The Books. Este documento es para
quien tome el proyecto a largo plazo: **cómo levantar todo sin perder ningún dato.**

Stack: FastAPI (async SQLAlchemy) · Next.js 14 + Tailwind · PostgreSQL.
Deploy actual: Railway (backend + Postgres + volumen `/data`) · Vercel (frontend).

---

## ⭐ Lo más importante: restaurar TODOS los datos

> ⚠️ **Los datos NO viajan por git** (desde 2026-07-27). `db/backups/*.sql` y
> `db/seed_data/` están en `.gitignore`: el repo de GitHub es público y esos
> archivos traen folios de huéspedes, revenue y presupuestos reales. Viajan
> **con la carpeta** (copia por USB / disco compartido, ver `SETUP_OTRA_PC.md`),
> nunca por `git clone`. Quien clone del repo obtiene el código, no los datos.

El paquete (esta carpeta) tiene **dos** caminos de restauración. **NO son equivalentes.**

### 1. Backup completo — `db/backups/prod_data_latest.sql`  ← USAR ESTE
Dump lógico de **todas las tablas** (data-only). Incluye **todo**: budget 2026 **y
2027**, OTB **multi-año 2026-2030**, e ingesta diaria (integrity/opera/occupancy/
POS/cash/auditoría/comps/ancla 6.6). Se regenera solo en cada commit (hook
pre-commit).

```bash
# En una base NUEVA y vacía:
alembic upgrade head                                  # crea el esquema (desde db/alembic)
psql "<DATABASE_URL>" -f db/backups/prod_data_latest.sql   # restaura TODO
```
El archivo usa `SET session_replication_role = replica;` para insertar sin pelear
con las FKs. Restaurar en base limpia (o vaciar antes).

### 2. Bootstrap — `db/seed_data/` + `python -m app.bootstrap_initial_data`
⚠️ Es SOLO un subconjunto: master-data 2026 (budget 2026, revenue actual, comps,
ancla). **NO** trae Budget 2027, ni snapshots OTB, ni la ingesta diaria. Sirve
para arrancar un entorno vacío desde cero, no para conservar el estado actual.

**➡️ Para no perder nada: restaurar desde el backup completo (opción 1).**

---

## ⚠️ Lo que NO viaja en el repo de git

- `db/backups/*.sql` — el respaldo completo de datos (ver el aviso de arriba).
- `db/seed_data/` — presupuesto, revenue real, comps y anclas del hotel.
- `goldens/` — los Excel/XML de validación.
- `backend/.env`, `db/backups/.prod_conn`, `CREDENTIALS.local.md` — secretos.

Todo eso sí está en **la carpeta**: para mudar el sistema completo se copia el
directorio, no se clona el repo.

Los **archivos crudos** de la ingesta diaria (XML/Excel de Opera/Integrity/POS)
viven en el **volumen del servidor** (`/data/uploads/inputs/<fecha>/`), no en git.
Solo importan si hay que **re-procesar desde cero** un día viejo. El dato ya
procesado de esos días SÍ está en el backup, así que para uso normal no se pierde
nada. (Opcional recomendable: guardar los crudos diarios en un Drive compartido.)

---

## Arranque de un entorno nuevo (resumen)

1. Clonar el repo.
2. Backend: crear base Postgres y setear `DATABASE_URL` / `DATABASE_URL_SYNC`
   (async/sync) en el env. El app no tiene login: no hay claves que configurar.
3. `alembic upgrade head` (desde `db/`, toma `DATABASE_URL_SYNC`).
4. `psql "<URL>" -f db/backups/prod_data_latest.sql`  → restaura todos los datos.
5. Frontend: setear `NEXT_PUBLIC_API_URL` al backend y desplegar.

---

## Deploy TODO en Railway (backend + Postgres + frontend)

Para levantar el stack completo en un proyecto Railway nuevo, sin Vercel:
**[`DEPLOY_RAILWAY.md`](./DEPLOY_RAILWAY.md)** — paso a paso, con los scripts
que dejan la base migrada y con los históricos restaurados (`scripts/
railway_db_setup.ps1`, que no necesita `psql`).

---

## Deploy (flujo actual, manual)

Migraciones SIEMPRE **antes** del deploy, contra el proxy público de Postgres:
```bash
cd db && DATABASE_URL_SYNC="postgresql+psycopg2://…@<proxy>/railway" \
  alembic -c alembic.ini upgrade head
```
Backend:  `railway up backend --path-as-root --service backend --ci`
Frontend: `cd frontend && vercel --prod --yes`

El backup de prod se regenera automáticamente en cada `git commit`
(`.githooks/pre-commit` → `scripts/regen_prod_backup.py`). La URL de prod se lee
de `db/backups/.prod_conn` (gitignored) o de la env `DAILY_OPS_PROD_URL`.

---

## Herramientas útiles

- `scripts/regen_prod_backup.py` — regenera el dump completo (lo corre el hook).
- `scripts/otb_backfill.py` — carga quirúrgica del snapshot OTB de un día (solo
  tablas OTB) desde los 2 `history_forecast`, sin tocar el resto:
  ```bash
  PYTHONPATH=backend DATABASE_URL="postgresql+asyncpg://…/railway" \
    backend/.venv/Scripts/python.exe scripts/otb_backfill.py <fecha> <Default.XML> <TotalRevenue.XML>
  ```

---

## Notas de operación

- El año en la UI sale del selector de **Día** (business date). El On The Books
  soporta multi-año (2026-2030+): subir un `history_forecast` que incluya los años
  y ponerse en una fecha de ese año.
- El Budget de cualquier año se sube por **Master Data → Tab 6.1** (selector de
  año, Download plantilla → llenar → Upload → deriva el diario solo).
- Secretos (DB password, proxy) NO están en el repo: viven en el env del
  proveedor y en `db/backups/.prod_conn` (gitignored).
- **El app no tiene autenticación** (27-jul-2026, decisión del owner): se entra
  directo por la URL, sin login ni roles. Si hace falta restringir el acceso,
  va por fuera del app (red privada, VPN, proxy con auth).
