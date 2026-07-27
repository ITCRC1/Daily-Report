<#
  DAILY-OPS - Deja la base de Railway lista: esquema (Alembic) + historicos.

  Corre desde esta PC contra la URL PUBLICA de la base de Railway (la que
  Railway llama DATABASE_PUBLIC_URL, con host *.proxy.rlwy.net). La privada
  (*.railway.internal) solo resuelve dentro de Railway.

  Sin acentos a proposito: Windows PowerShell 5.1 lee los .ps1 como ANSI y los
  caracteres no-ASCII le rompen el parseo (misma convencion que setup_otra_pc.ps1).

  Uso:
    powershell -ExecutionPolicy Bypass -File .\scripts\railway_db_setup.ps1 `
      -DatabaseUrl "postgresql://postgres:PASS@shinkansen.proxy.rlwy.net:12345/railway"

    -SkipRestore   solo migra el esquema, no carga los historicos
    -Force         restaura aunque la base ya tenga datos (duplica: usar con cuidado)
#>
param(
  [Parameter(Mandatory = $true)][string]$DatabaseUrl,
  [switch]$SkipRestore,
  [switch]$Force
)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Write-Host "== DAILY-OPS -> Railway: preparar base ==" -ForegroundColor Cyan

if ($DatabaseUrl -match "railway\.internal") {
  throw "Esa es la URL PRIVADA (railway.internal): solo funciona dentro de Railway. Usa DATABASE_PUBLIC_URL (*.proxy.rlwy.net)."
}

# --- 1) venv del backend (crea si no existe) ---
$py = Join-Path $root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
  Write-Host "`n[1/4] Creando venv del backend (Python 3.12)..." -ForegroundColor Yellow
  Push-Location (Join-Path $root "backend")
  if (Get-Command py -ErrorAction SilentlyContinue) { & py -3.12 -m venv .venv } else { & python -m venv .venv }
  if ($LASTEXITCODE -ne 0) { Pop-Location; throw "no pude crear el venv (Python 3.12 instalado?)" }
  & ".\.venv\Scripts\python.exe" -m pip install --upgrade pip | Out-Null
  & ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
  $pipCode = $LASTEXITCODE
  Pop-Location
  if ($pipCode -ne 0) { throw "pip install fallo" }
} else {
  Write-Host "`n[1/4] venv del backend ya existe - se reutiliza." -ForegroundColor Yellow
}

# --- 2) Chequeo de version de Python (3.13/3.14 no compilan asyncpg/lxml) ---
$ver = & $py -c "import sys; print(str(sys.version_info[0]) + '.' + str(sys.version_info[1]))"
Write-Host "  Python del venv: $ver"
if ($ver -ne "3.12") { Write-Host "  AVISO: el proyecto esta validado en 3.12." -ForegroundColor DarkYellow }

# --- 3) Esquema (Alembic) ---
Write-Host "`n[2/4] Aplicando migraciones (alembic upgrade head)..." -ForegroundColor Yellow
$syncUrl = $DatabaseUrl -replace "^postgres(ql)?://", "postgresql+psycopg2://"
$prev = $env:DATABASE_URL_SYNC
$env:DATABASE_URL_SYNC = $syncUrl
Push-Location (Join-Path $root "db")
& $py -m alembic -c alembic.ini upgrade head
$code = $LASTEXITCODE
Pop-Location
$env:DATABASE_URL_SYNC = $prev
if ($code -ne 0) { throw "alembic upgrade head fallo" }

# --- 4) Historicos ---
if ($SkipRestore) {
  Write-Host "`n[3/4] Restore omitido (-SkipRestore)." -ForegroundColor Yellow
} else {
  Write-Host "`n[3/4] Restaurando db\backups\prod_data_latest.sql (16 MB, tarda)..." -ForegroundColor Yellow
  $restoreArgs = @((Join-Path $root "scripts\restore_backup.py"), $DatabaseUrl)
  if ($Force) { $restoreArgs += "--force" }
  & $py $restoreArgs
  if ($LASTEXITCODE -ne 0) { throw "el restore fallo (la base quedo intacta: corre en una sola transaccion)" }
}

# --- 5) Verificacion ---
Write-Host "`n[4/4] Verificando..." -ForegroundColor Yellow
& $py (Join-Path $root "scripts\check_db.py") $DatabaseUrl
if ($LASTEXITCODE -ne 0) { throw "la verificacion fallo" }

Write-Host "`n== BASE LISTA ==" -ForegroundColor Green
Write-Host "Siguiente paso: variables del servicio backend y 'railway up backend -s backend'."
Write-Host "Ver DEPLOY_RAILWAY.md."
