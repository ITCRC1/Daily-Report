<#
  DAILY-OPS — Arranca backend (puerto 8000) y frontend (puerto 3000) en local.
  Corre esto DESPUES de setup_otra_pc.ps1.
  Uso: powershell -ExecutionPolicy Bypass -File .\run_local.ps1
#>
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

$py = Join-Path $root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { Write-Host "Falta el entorno. Corre primero setup_otra_pc.ps1" -ForegroundColor Red; exit 1 }

Write-Host "Arrancando backend (http://localhost:8000)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit","-Command","cd '$root\backend'; & '.\.venv\Scripts\python.exe' -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

Write-Host "Arrancando frontend (http://localhost:3000)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit","-Command","cd '$root\frontend'; npm run dev"

Write-Host "`nListo. Abri http://localhost:3000 en el navegador (entra directo, sin clave)." -ForegroundColor Green
Write-Host "Para apagar: cerra las dos ventanas de PowerShell que se abrieron."
