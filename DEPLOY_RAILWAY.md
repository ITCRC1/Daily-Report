# DEPLOY_RAILWAY — Levantar DAILY-OPS completo en Railway

Proyecto **nuevo** en Railway con **tres servicios**: `Postgres` + `backend`
(FastAPI) + `frontend` (Next.js). No depende de Vercel.

> El deploy es desde esta PC con la CLI de Railway (`railway up`), no desde
> GitHub — esta copia del repo no tiene historial de commits.
> Para restaurar/entender los datos: [`HANDOFF.md`](./HANDOFF.md).

---

## Antes de empezar

| Requisito | Estado en esta PC (27-jul-2026) |
|---|---|
| Railway CLI | ✅ v5.26.1 instalada |
| Sesión de Railway | ❌ **falta `railway login`** (abre el navegador — hacelo vos) |
| Node.js | ✅ v24.18.0 |
| Python 3.12 | ✅ 3.12.10 en PATH |
| `backend\.venv` | ❌ no existe — lo crea el script del Paso 2 |
| `psql` | ❌ no instalado — **no hace falta**, el restore va por Python |

El backup a restaurar es `db/backups/prod_data_latest.sql`: **58.284 filas**,
esquema Alembic `e1f2a3b4c5d6`, que es exactamente el head de las 27 migraciones
de esta copia (verificado). Código y datos están en sync.

---

## Paso 1 — Crear el proyecto y los servicios

```powershell
railway login                      # navegador
railway init --name daily-ops      # crea el proyecto y linkea esta carpeta
railway add --database postgres    # servicio "Postgres"
railway add --service backend
railway add --service frontend
```

Tomá la URL **pública** de la base (host `*.proxy.rlwy.net`; la privada
`*.railway.internal` solo resuelve dentro de Railway):

```powershell
railway variable list -s Postgres --kv
# copiá el valor de DATABASE_PUBLIC_URL
```

## Paso 2 — Dejar la base lista (esquema + históricos)

Un solo comando: crea el venv si falta, migra y restaura las 58.284 filas.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\railway_db_setup.ps1 `
  -DatabaseUrl "<DATABASE_PUBLIC_URL>"
```

- El restore corre en **una sola transacción**: si algo falla, revierte todo y
  la base queda intacta.
- Se planta si la base ya tiene datos (el dump son `INSERT`s sin `ON CONFLICT`;
  correrlo dos veces duplicaría todo). `-Force` lo salta a propósito.
- Al final imprime el conteo por tabla. Referencia del backup actual:
  `fact_otb_daily` 32.866 · `fact_budget` 6.712 · `fact_opera_txn_detail` 4.670 ·
  `fact_bill_line` 4.177 · `fact_revenue_actual_daily` 2.534 ·
  `stg_integrity_line` 1.119 · `dim_calendar` 1.095 · `audit_finding` 148.

Para volver a chequear una base en cualquier momento:

```powershell
backend\.venv\Scripts\python.exe scripts\check_db.py "<DATABASE_PUBLIC_URL>"
```

## Paso 3 — Backend

Variables (usan referencias `${{Postgres...}}`: Railway las resuelve solo, y el
backend ahora acepta la URL plana `postgresql://` — la normaliza al driver que
corresponde en `app/config.py`).

```powershell
railway variable set -s backend `
  'DATABASE_URL=${{Postgres.DATABASE_URL}}' `
  'DATABASE_URL_SYNC=${{Postgres.DATABASE_URL}}' `
  'DEFAULT_PROPERTY=COWLCR' `
  'UPLOADS_DIR=/data/uploads/inputs'
```

> ⚠️ **El app NO tiene autenticación** (decisión del owner, 27-jul-2026): el
> login se eliminó del código, no quedó apagado. Cualquiera que llegue a la URL
> entra y puede escribir — subir y borrar días, liberar dailies, editar master
> data. No hay variable que lo prenda: si hace falta cerrarlo, va por fuera
> (red privada, VPN o un proxy con auth adelante).

**Volumen** — los archivos crudos que se suben por Tab 1 tienen que sobrevivir a
cada redeploy:

```powershell
railway volume add -s backend -m /data
```

Deploy (la carpeta `backend` pasa a ser la raíz del build; `backend/railway.json`
ya define start command y healthcheck `/health`):

```powershell
railway up backend -s backend --ci
railway domain -s backend          # genera el dominio público; anotalo
```

## Paso 4 — Frontend

`NEXT_PUBLIC_API_URL` se **incrusta en el build** de Next: hay que setearla
*antes* de desplegar, con el dominio del backend del paso anterior.

```powershell
railway variable set -s frontend "NEXT_PUBLIC_API_URL=https://<dominio-backend>"
railway up frontend -s frontend --ci
railway domain -s frontend         # dominio público del app
```

## Paso 5 — Cerrar el círculo (CORS)

El backend solo acepta al navegador desde los orígenes que liste `CORS_ORIGINS`:

```powershell
railway variable set -s backend "CORS_ORIGINS=https://<dominio-frontend>"
```

Cambiar una variable dispara redeploy del backend solo. Si más adelante se suma
un dominio propio, va en la misma lista separado por comas.

## Paso 6 — Verificar

```powershell
curl.exe https://<dominio-backend>/health          # {"status":"ok","db":"up"}
curl.exe -I https://<dominio-frontend>             # 200
```

Y en el navegador: entrar al frontend (no pide clave), elegir el día
**2026-06-08** en el selector y confirmar contra los números ya validados —
revenue total **$9.560,02**, Rooms **$5.023,96**, RN 13, ADR **$386,46**,
ocupación 59,1 %. Si eso cuadra, la base y el backend están bien enganchados.

---

## Lo que quedó preparado en el repo

| Archivo | Para qué |
|---|---|
| `backend/railway.json` | builder, `uvicorn --port $PORT`, healthcheck `/health`, reinicio ante fallo |
| `backend/.python-version` | fija Python **3.12** (3.13/3.14 no compilan asyncpg/lxml/psycopg2) |
| `backend/.railwayignore` | que el build no arrastre `.env`, `.venv`, tests ni `reference/` |
| `frontend/railway.json` | build `npm run build`, start `next start` en `$PORT`, healthcheck `/` |
| `frontend/.railwayignore` | excluye `node_modules`, `.next`, `.vercel`, `.env.local` |
| `scripts/railway_db_setup.ps1` | venv + `alembic upgrade head` + restore + verificación, en un comando |
| `scripts/restore_backup.py` | restaura el dump **sin psql** (por psycopg2), transaccional y con guardas |
| `scripts/check_db.py` | revisión de esquema + conteo por tabla de cualquier base |
| `app/config.py` | acepta `postgresql://` plano y le pone el driver (async/sync) |
| `backend/tests/test_config_urls.py` | fija esa normalización (5 tests) |
| `frontend/package.json` | Next **14.2.15 → 14.2.35** (parche de seguridad de la misma línea 14.2) |

## Verificado en esta PC antes de desplegar

- `pytest` → **76/76 en verde** (71 previos + 5 nuevos).
- `npm run build` del frontend → **OK**, 13 rutas, todas prerenderizadas
  estáticas — confirma que `NEXT_PUBLIC_API_URL` se hornea en el build.
- Parser del dump → **58.284 sentencias** leídas sin errores (el mismo número
  que declara el backup).
- Migraciones: 27, **un solo head** `e1f2a3b4c5d6` = el que espera el backup.
- Normalización de URLs de Postgres probada con URL plana, `postgres://`,
  driver explícito y password con `%40`.

## Cosas a tener en cuenta

- **Si el build del backend elige otra versión de Python**, forzala con
  `railway variable set -s backend "NIXPACKS_PYTHON_VERSION=3.12"`.
- **El healthcheck del frontend NO puede apuntar a `/`**: `app/page.tsx` hace
  `redirect("/data-input")`, así que la raíz devuelve **307** y Railway la toma
  como caída. Por eso apunta a `/data-input`, que responde 200. (Costó dos
  deploys fallidos: el build compilaba bien y el healthcheck moría igual.)
- **`$PORT` en el `startCommand` va con default** (`${PORT:-3000}`): si el
  servicio no lo tiene definido, `next start --port` se queda sin valor, Next no
  arranca y no hay nada escuchando.
- **`POST /ingest/{fecha}`** (el que lee de `goldens/inputs/`) no sirve en
  Railway: los goldens no viajan en el build del backend. En producción la carga
  es por **Tab 1 → upload**, que escribe en el volumen `/data`.
- **El login se eliminó del código** (27-jul-2026): se borraron `app/deps.py`,
  `app/api/auth.py`, `app/api/admin_users.py`, `app/services/auth_service.py`,
  la página `/login` y el `AuthGate` del frontend. Las tablas `app_user` y
  `role` **siguen en la base** a propósito: el backup las trae y borrarlas
  rompería el restore. La página `/admin` quedó solo con prender/apagar tabs.
- **El backup ya no se regenera solo.** El hook `pre-commit` que lo hacía no
  existe en esta copia (tampoco hay commits). Después de operar en el Railway
  nuevo, regenerá a mano apuntando a la base nueva:
  `$env:DAILY_OPS_PROD_URL="<DATABASE_PUBLIC_URL>"; backend\.venv\Scripts\python.exe scripts\regen_prod_backup.py`
- **Los datos reales quedaron fuera de git** (`db/backups/*.sql` y
  `db/seed_data/` en `.gitignore`, 2026-07-27), porque el repo de GitHub es
  público. Siguen en esta carpeta y en el servidor. Consecuencia: quien clone el
  repo tiene el código pero **no** los históricos — para eso hay que pasarle la
  carpeta.
- **`npm audit` sigue marcando avisos de Next aun en 14.2.35**: el rango de esos
  advisories llega hasta Next 16, y cerrarlos del todo implica un salto de major
  (14 → 16), no un parche. Revisado uno por uno, apuntan a superficies que este
  app **no usa**: no hay `next/image`, ni `middleware.ts`, ni Server Actions, ni
  `rewrites` — las 13 rutas son estáticas prerenderizadas. Riesgo residual bajo;
  el salto a Next 16 queda como tarea aparte, no como bloqueante del deploy.
