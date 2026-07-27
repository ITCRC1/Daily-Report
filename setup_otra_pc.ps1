<#
  DAILY-OPS — Setup en una PC nueva (copia local completa).
  Crea la base + usuario, instala dependencias, aplica el esquema y RESTAURA
  todos los historicos desde db\backups\prod_data_latest.sql.

  Requisitos previos (ver SETUP_OTRA_PC.md): PostgreSQL 16, Python 3.12, Node.js.

  Uso:
    powershell -ExecutionPolicy Bypass -File .\setup_otra_pc.ps1
    powershell -ExecutionPolicy Bypass -File .\setup_otra_pc.ps1 -PgPort 5433
#>
param(
  [int]$PgPort = 5432,
  [string]$PgBin = "",
  [string]$PgSuperUser = "postgres"
)
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
Write-Host "== DAILY-OPS setup en PC nueva ==" -ForegroundColor Cyan
Write-Host "Proyecto: $root"

# --- Localizar psql.exe ---
function Find-Psql {
  if ($PgBin -and (Test-Path (Join-Path $PgBin "psql.exe"))) { return (Join-Path $PgBin "psql.exe") }
  $cmd = Get-Command psql.exe -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  $hit = Get-ChildItem "C:\Program Files\PostgreSQL\*\bin\psql.exe" -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1
  if ($hit) { return $hit.FullName }
  throw "No encontre psql.exe. Instala PostgreSQL o pasa -PgBin 'C:\Program Files\PostgreSQL\16\bin'."
}
$psql = Find-Psql
Write-Host "psql: $psql"

# --- Pedir contrasena del superusuario postgres ---
$sec = Read-Host "Contrasena del usuario '$PgSuperUser' de PostgreSQL" -AsSecureString
$PgSuperPass = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
$env:PGPASSWORD = $PgSuperPass

function Psql-Admin([string]$db, [string]$sql) {
  & $psql -h localhost -p $PgPort -U $PgSuperUser -d $db -v ON_ERROR_STOP=1 -tAc $sql
  if ($LASTEXITCODE -ne 0) { throw "psql fallo (db=$db): $sql" }
}

# --- 1) Usuario + base ---
Write-Host "`n[1/6] Creando usuario y base 'daily_ops'..." -ForegroundColor Yellow
Psql-Admin "postgres" "DO `$`$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='daily_ops') THEN CREATE ROLE daily_ops LOGIN PASSWORD 'daily_ops'; END IF; END `$`$;"
$exists = & $psql -h localhost -p $PgPort -U $PgSuperUser -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='daily_ops'"
if (-not $exists) { Psql-Admin "postgres" "CREATE DATABASE daily_ops OWNER daily_ops" ; Write-Host "  base creada" } else { Write-Host "  la base ya existia (se reutiliza)" }

# --- 2) backend\.env ---
Write-Host "`n[2/6] Escribiendo backend\.env..." -ForegroundColor Yellow
$envText = @"
DATABASE_URL=postgresql+asyncpg://daily_ops:daily_ops@localhost:$PgPort/daily_ops
DATABASE_URL_SYNC=postgresql+psycopg2://daily_ops:daily_ops@localhost:$PgPort/daily_ops
CORS_ORIGINS=http://localhost:3000
DEFAULT_PROPERTY=COWLCR
"@
Set-Content -Path (Join-Path $root "backend\.env") -Value $envText -Encoding utf8

# --- 3) venv + dependencias backend ---
Write-Host "`n[3/6] Creando entorno Python e instalando backend (puede tardar)..." -ForegroundColor Yellow
Push-Location (Join-Path $root "backend")
if (-not (Test-Path ".venv")) { python -m venv .venv }
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip | Out-Null
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "pip install fallo" }
Pop-Location

# --- 4) Esquema (alembic) ---
Write-Host "`n[4/6] Aplicando esquema (migraciones)..." -ForegroundColor Yellow
Push-Location (Join-Path $root "db")
$env:DATABASE_URL_SYNC = "postgresql+psycopg2://daily_ops:daily_ops@localhost:$PgPort/daily_ops"
& "..\backend\.venv\Scripts\alembic.exe" upgrade head
if ($LASTEXITCODE -ne 0) { throw "alembic upgrade fallo" }
Pop-Location

# --- 5) Restaurar historicos (como superusuario) ---
Write-Host "`n[5/6] Restaurando historicos desde db\backups\prod_data_latest.sql..." -ForegroundColor Yellow
$dump = Join-Path $root "db\backups\prod_data_latest.sql"
if (-not (Test-Path $dump)) { throw "No existe el backup: $dump" }
& $psql -h localhost -p $PgPort -U $PgSuperUser -d daily_ops -v ON_ERROR_STOP=1 -f $dump | Out-Null
if ($LASTEXITCODE -ne 0) { throw "restauracion fallo" }
$rows = & $psql -h localhost -p $PgPort -U $PgSuperUser -d daily_ops -tAc "SELECT (SELECT count(*) FROM fact_otb_daily)+(SELECT count(*) FROM fact_budget)+(SELECT count(*) FROM stg_integrity_line)"
Write-Host "  restaurado OK (muestra de control fact_otb_daily+fact_budget+integrity = $($rows.Trim()))"

# --- 6) Frontend ---
Write-Host "`n[6/6] Instalando frontend (npm install, puede tardar)..." -ForegroundColor Yellow
Set-Content -Path (Join-Path $root "frontend\.env.local") -Value "NEXT_PUBLIC_API_URL=http://localhost:8000" -Encoding utf8
Push-Location (Join-Path $root "frontend")
npm install
if ($LASTEXITCODE -ne 0) { throw "npm install fallo" }
Pop-Location

$env:PGPASSWORD = $null
Write-Host "`n== SETUP COMPLETO ==" -ForegroundColor Green
Write-Host "Arranca el app con:  powershell -ExecutionPolicy Bypass -File .\run_local.ps1"
Write-Host "Luego abri http://localhost:3000  (entra directo, sin clave)"
