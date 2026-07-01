# Start backend on port 8002 + Cloudflare quick tunnel (free HTTPS URL for your phone).
# Install cloudflared first: winget install Cloudflare.cloudflared
#
# The trycloudflare.com URL changes each time you run this script.
# For a fixed URL, see docs/DEPLOY-FREE.md (named Cloudflare tunnel).

$ErrorActionPreference = "Stop"
$port = 8002
$root = $PSScriptRoot

# Free port 8002
Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue |
  ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2

$localCloudflared = Join-Path $root "tools\cloudflared.exe"
$cloudflared = if (Get-Command cloudflared -ErrorAction SilentlyContinue) {
  "cloudflared"
} elseif (Test-Path $localCloudflared) {
  $localCloudflared
} else {
  $null
}

if (-not $cloudflared) {
  Write-Host ""
  Write-Host "cloudflared is not installed." -ForegroundColor Red
  Write-Host "Run: winget install Cloudflare.cloudflared" -ForegroundColor Yellow
  Write-Host "Or download to backend\tools\cloudflared.exe (see docs/DEPLOY-FREE.md)" -ForegroundColor Yellow
  exit 1
}

Write-Host "Starting backend on http://127.0.0.1:$port ..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
  "-NoExit",
  "-Command",
  "Set-Location '$root'; .\venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port $port"
) -WindowStyle Normal

Start-Sleep -Seconds 4

Write-Host ""
Write-Host "Starting Cloudflare Tunnel (copy the https URL below)..." -ForegroundColor Cyan
Write-Host "Use that URL as VITE_API_URL on Netlify / Render." -ForegroundColor Yellow
Write-Host "Add your frontend URL to backend .env CORS_ORIGINS." -ForegroundColor Yellow
Write-Host ""

Set-Location $root
& $cloudflared tunnel --url "http://127.0.0.1:$port"
