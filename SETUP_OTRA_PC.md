# DAILY-OPS — Instalar y correr en otra PC (copia local completa)

Esta guía deja el app corriendo en una computadora nueva, con **todos los
históricos** restaurados desde el respaldo `db/backups/prod_data_latest.sql`.

> Copiá TODA esta carpeta a la llave maya y de ahí a la otra PC (ej. a
> `C:\DAILY-OPS`). La copia NO trae `node_modules`, `.venv`, `.next` ni `.git`
> (se regeneran/instalan abajo). El respaldo de datos SÍ va incluido.

---

## Paso 0 — Instalar 3 programas (una sola vez, en la PC nueva)

Descargá e instalá, en este orden. **Importante:** en cada instalador, dejá
marcada la opción **"Add to PATH"** cuando aparezca.

| Programa | Dónde | Nota al instalar |
|---|---|---|
| **PostgreSQL 16** | <https://www.postgresql.org/download/windows/> | Anotá la **contraseña del usuario `postgres`** que te pida (la vas a necesitar). Dejá el puerto en **5432**. |
| **Python 3.12** | <https://www.python.org/downloads/> | Marcá **"Add python.exe to PATH"** en la primera pantalla. |
| **Node.js LTS** | <https://nodejs.org/> | Instalación por defecto (ya agrega al PATH). |

Reiniciá la PC (o al menos cerrá y abrí PowerShell) para que el PATH tome efecto.

---

## Paso 1 — Setup automático (crea la base + restaura históricos + instala todo)

Abrí **PowerShell**, entrá a la carpeta del proyecto y corré el script de setup.
Te va a pedir la contraseña del usuario `postgres` que pusiste al instalar.

```powershell
cd C:\DAILY-OPS
powershell -ExecutionPolicy Bypass -File .\setup_otra_pc.ps1
```

Si instalaste PostgreSQL en un puerto distinto a 5432, pasáselo así:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup_otra_pc.ps1 -PgPort 5433
```

El script hace todo esto solo:
1. Crea el usuario `daily_ops` y la base `daily_ops` en PostgreSQL.
2. Escribe `backend\.env` con la conexión correcta.
3. Crea el entorno de Python (`.venv`) e instala las dependencias del backend.
4. Aplica el esquema (migraciones Alembic).
5. **Restaura todos los históricos** desde `db\backups\prod_data_latest.sql`.
6. Instala las dependencias del frontend (`npm install`) y escribe `frontend\.env.local`.

Al final te dice **"SETUP COMPLETO"** y cuántas filas restauró (debe decir ~58,284).

---

## Paso 2 — Arrancar el app

```powershell
cd C:\DAILY-OPS
powershell -ExecutionPolicy Bypass -File .\run_local.ps1
```

Eso levanta el backend (puerto 8000) y el frontend (puerto 3000) en dos ventanas.
Abrí el navegador en **<http://localhost:3000>** — el app no pide clave, entra directo.

Para apagarlo: cerrá las dos ventanas de PowerShell que abrió.

---

## Subir MÁS datos históricos después

Una vez corriendo, en **Tab 1 · Data Input** podés seguir subiendo días
(Opera XML + Integrity + POS) como siempre. Todo lo que subas queda en la base
local de esa PC. (La auto-carga desde Google Drive es aparte y aún no está
desplegada — ver `docs/DRIVE_SETUP.md`.)

---

## Si algo falla

- **"psql no se reconoce" / no encuentra PostgreSQL:** el instalador no lo agregó
  al PATH. El script igual lo busca en `C:\Program Files\PostgreSQL\*\bin`; si lo
  instalaste en otra ruta, pasásela con `-PgBin "C:\ruta\bin"`.
- **"python no se reconoce":** faltó marcar "Add to PATH" al instalar Python;
  reinstalá marcándola, o agregalo al PATH a mano.
- **La restauración da error de permisos:** el paso de datos necesita el usuario
  `postgres` (superusuario) — es el que pusiste al instalar PostgreSQL; el script
  te lo pide.
- **Verificar que quedó todo:** el script imprime el total de filas restauradas;
  debe coincidir con lo que dice el encabezado del `.sql`.

---

## Nota

Esta es una copia **independiente**: sus datos viven solo en esa PC y no se
sincronizan con producción (`daily-ops-bay.vercel.app`) ni con otras copias.
Ideal para trabajar offline o en un entorno aislado.
