# Start backend + named Cloudflare tunnel (stable URL from config.yml).
# Copy cloudflared/config.example.yml → cloudflared/config.yml first.

$ErrorActionPreference = "Stop"
$port = 8002
$root = $PSScriptRoot
$config = Join-Path $root "cloudflared\config.yml"

if (-not (Test-Path $config)) {
  Write-Host "Missing $config" -ForegroundColor Red
  Write-Host "Copy cloudflared\config.example.yml → cloudflared\config.yml and edit it." -ForegroundColor Yellow
  Write-Host "See docs/DEPLOY-FREE.md for setup steps." -ForegroundColor Yellow
  exit 1
}

if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) {
  Write-Host "Install cloudflared: winget install Cloudflare.cloudflared" -ForegroundColor Red
  exit 1
}

Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue |
  ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2

Write-Host "Starting backend on http://127.0.0.1:$port ..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
  "-NoExit",
  "-Command",
  "Set-Location '$root'; .\venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port $port"
) -WindowStyle Normal

Start-Sleep -Seconds 4
Write-Host "Starting named tunnel from cloudflared\config.yml ..." -ForegroundColor Cyan
cloudflared tunnel --config $config run
