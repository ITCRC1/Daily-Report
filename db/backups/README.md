# Backups — DAILY-OPS

Backup lógico COMPLETO de la base de prod (todas las tablas, data-only), para
proteger la información histórica ya cargada.

> ⚠️ **Los `.sql` de esta carpeta NO se versionan** (`.gitignore`, 2026-07-27):
> el repo de GitHub es público y el dump trae folios de huéspedes, revenue y
> presupuestos reales. Existen solo en esta carpeta y en el servidor — para
> mudar el sistema hay que copiar el directorio, no clonar el repo. Este README
> sí se versiona.

`prod_data_latest.sql` lo genera `scripts/regen_prod_backup.py` leyendo de
**producción**, no de la base local. La URL sale de la env `DAILY_OPS_PROD_URL`
o del archivo `db/backups/.prod_conn` (gitignored). Se corre a mano:

```powershell
$env:DAILY_OPS_PROD_URL="<DATABASE_PUBLIC_URL>"
backend\.venv\Scripts\python.exe scripts\regen_prod_backup.py
```

(Antes lo disparaba un hook `pre-commit`; ese hook no existe en esta copia.)

## Restaurar en un servidor nuevo

```bash
# 1. Esquema (deja alembic_version en la revisión que indica el encabezado del .sql)
cd db && alembic upgrade head

# 2. Datos — ON_ERROR_STOP para que CUALQUIER problema sea ruidoso
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/backups/prod_data_latest.sql
```

Verificar después: el total de filas restauradas debe coincidir con el que
declara el propio dump (`[backup] OK: N filas`).

Notas:
- El archivo usa `SET session_replication_role = replica;` para insertar sin
  pelear con las FKs (requiere conectarse como superusuario).
- Restaurar SIEMPRE en una base vacía (o vaciarla antes). No es idempotente:
  correrlo dos veces duplica filas.
- **`alembic_version` se excluye del dump a propósito**: el paso 1 ya deja esa
  fila puesta, y incluirla hacía que el INSERT chocara con la PK y —con
  `ON_ERROR_STOP=1`— abortara TODO el restore dejando la base vacía. La
  revisión de esquema queda como comentario en el encabezado del `.sql`, que es
  donde sirve: para saber contra qué esquema restaurar.
- Dump lógico version-independiente (el server es Postgres 18; `pg_dump` 16 no
  sirve contra esa versión).

## Los dos caminos, y cuál usar

| | `prod_data_latest.sql` (este) | `db/seed_data/` + `bootstrap_initial_data` |
|---|---|---|
| Qué trae | **TODO**: master data + ingesta diaria (integrity/opera/occupancy/POS/OTB), auditoría, usuarios, parámetros | Solo la master-data reproducible (budget, revenue actual, comps, ancla 6.6) |
| Cuándo | Migrar/clonar un entorno **sin perder nada** | Levantar un entorno nuevo "desde el paquete" |
| Idempotente | No (base vacía) | Sí (insert-only, no pisa nada) |

Para mover el sistema a otro servidor conservando todo lo cargado hasta la
fecha: **usar este dump**. `seed_data` no incluye la ingesta diaria.
