# Stop processes on port 8010, then start one backend.
$port = 8010
for ($i = 0; $i -lt 6; $i++) {
  netstat -ano | Select-String ":$port\s" | Select-String "LISTENING" | ForEach-Object {
    $processId = ($_.Line -split '\s+')[-1]
    if ($processId -match '^\d+$') {
      taskkill /F /PID $processId 2>$null | Out-Null
    }
  }
  Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
  Start-Sleep -Seconds 1
  $stillListening = netstat -ano | Select-String ":$port\s" | Select-String "LISTENING"
  if (-not $stillListening) { break }
}
Start-Sleep -Seconds 1
Set-Location $PSScriptRoot
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload --port $port
