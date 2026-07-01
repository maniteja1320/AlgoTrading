# Stop processes on port 8002, then start one backend (8000 may have stale zombie listeners).
$port = 8002
Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue |
  ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2
Set-Location $PSScriptRoot
.\venv\Scripts\uvicorn app.main:app --reload --port $port
