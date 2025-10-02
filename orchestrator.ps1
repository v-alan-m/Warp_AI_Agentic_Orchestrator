# orchestrator.ps1
# Start Router MCP (uvicorn) + wait for /health + tail logs (Windows/PowerShell)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# --- Resolve paths (repo root = the folder containing this script) ---
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$DocsDir = Join-Path $ScriptDir "docs"
$ProjectDir = Join-Path $ScriptDir "project"

# Ensure docs directory & files exist (so tail doesn't fail)
New-Item -ItemType Directory -Force -Path $DocsDir | Out-Null
@("build-summary.md","router_log.jsonl","CHANGELOG.md") | ForEach-Object {
  $p = Join-Path $DocsDir $_
  if (-not (Test-Path $p)) { New-Item -ItemType File -Path $p | Out-Null }
}

# --- Environment (edit as needed) ---
if (-not $env:ROUTER_LOG_DIR) { $env:ROUTER_LOG_DIR = $DocsDir }
if (-not $env:ROUTER_MAX_STEPS) { $env:ROUTER_MAX_STEPS = "17" }
if (-not $env:ROUTER_ENFORCE_RULE_ACK) { $env:ROUTER_ENFORCE_RULE_ACK = "true" }
if (-not $env:ROUTER_PORT) { $env:ROUTER_PORT = "8085" }

$HealthUrl = "http://localhost:$($env:ROUTER_PORT)/health"

Write-Host "LOG_DIR      : $($env:ROUTER_LOG_DIR)"
Write-Host "MAX_STEPS    : $($env:ROUTER_MAX_STEPS)"
Write-Host "RULE_ACK     : $($env:ROUTER_ENFORCE_RULE_ACK)"
Write-Host "ROUTER_PORT  : $($env:ROUTER_PORT)"
Write-Host "HEALTH URL   : $HealthUrl"
Write-Host ""

# --- Start uvicorn in a background job ---
$RouterJob = Start-Job -Name "router-mcp" -ScriptBlock {
  param($WorkingDir, $Port)
  Set-Location $WorkingDir

  # Check uvicorn availability (PowerShell-friendly)
  $pyCheck = & python -c "import pkgutil; print('UVICORN_PRESENT=', pkgutil.find_loader('uvicorn') is not None)"
  Write-Output $pyCheck

  # Launch server (module import style is most reliable)
  & python -m uvicorn router_mcp:APP --host 127.0.0.1 --port $Port --log-level info
} -ArgumentList $ScriptDir, $env:ROUTER_PORT

Start-Sleep -Milliseconds 200

# --- Wait for /health (timeout ~ 60s) ---
Write-Host "Waiting for router to become healthy..."
$deadline = (Get-Date).AddSeconds(60)
$healthy = $false

while ((Get-Date) -lt $deadline) {
  try {
    $resp = Invoke-WebRequest -Uri $HealthUrl -UseBasicParsing -TimeoutSec 3
    if ($resp.StatusCode -eq 200) { $healthy = $true; break }
  } catch {
    # ignore until deadline
  }
  Write-Host -NoNewline "."
  Start-Sleep -Milliseconds 800
}
Write-Host ""

if (-not $healthy) {
  Write-Warning "Router did not become healthy within 60s."
  Write-Host "Diagnostics:"
  Write-Host "  * Confirm you're in the repo root: $WorkingDir"
  Write-Host "  * Confirm router_mcp.py exists here and is importable."
  Write-Host "  * Confirm python can import uvicorn: 'python -m pip install uvicorn fastapi pydantic'"
  Write-Host "  * Check if port $Port is in use: 'netstat -ano | findstr $Port'"
  Write-Host "  * Job output follows:"
  Receive-Job -Id $RouterJob.Id -Keep | Write-Host
  Stop-Job -Id $RouterJob.Id -ErrorAction SilentlyContinue
  Exit 1
}

Write-Host "✅ Router is healthy at $HealthUrl"
Write-Host "Tailing logs: build-summary.md and router_log.jsonl (Ctrl+C to stop tails; server continues in job)"
Write-Host ""

# --- Tail logs (non-terminating) ---
$BuildSummary = Join-Path $DocsDir "build-summary.md"
$JsonLog      = Join-Path $DocsDir "router_log.jsonl"

$Tail1 = Start-Job -Name "tail-summary" -ScriptBlock {
  param($file)
  Write-Host "[TAIL] $file"
  Get-Content -Path $file -Wait -Encoding UTF8
} -ArgumentList $BuildSummary

$Tail2 = Start-Job -Name "tail-json" -ScriptBlock {
  param($file)
  Write-Host "[TAIL] $file"
  Get-Content -Path $file -Wait -Encoding UTF8
} -ArgumentList $JsonLog

Write-Host "`n[Router stdout follows below as it runs...]`n"
Receive-Job -Id $RouterJob.Id -Keep
