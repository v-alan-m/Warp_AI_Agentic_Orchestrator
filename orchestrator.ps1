# start-warp-and-router.ps1
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$HealthUrl = "http://localhost:8085/health"

function Test-Health {
  try { (Invoke-WebRequest -UseBasicParsing -Uri $HealthUrl -TimeoutSec 2) | Out-Null; return $true }
  catch { return $false }
}

if (-not (Test-Health)) {
  Start-Process powershell -ArgumentList "-ExecutionPolicy Bypass -File `"$ScriptDir\orchestrator.ps1`""
  Start-Sleep -Seconds 2
  # wait up to ~10s for health
  1..20 | % { if (Test-Health) { break } ; Start-Sleep -Milliseconds 500 }
}

# Launch Warp (adjust path if needed)
Start-Process "C:\Program Files\Warp\Warp.exe"
