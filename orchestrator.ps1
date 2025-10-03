# orchestrator_safe.ps1
# Minimal + AV-friendly: no hidden windows, no detached child, no jobs.

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# --- Resolve paths (repo root = the folder containing this script) ---
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$DocsDir    = Join-Path $ScriptDir "docs"
$ProjectDir = Join-Path $ScriptDir "project"

# Ensure docs directory & files exist (so tail doesn't fail)
New-Item -ItemType Directory -Force -Path $DocsDir | Out-Null
@("build-summary.md","router_log.jsonl","CHANGELOG.md") | ForEach-Object {
  $p = Join-Path $DocsDir $_
  if (-not (Test-Path $p)) { New-Item -ItemType File -Path $p | Out-Null }
}

if (-not $env:ROUTER_LOG_DIR)         { $env:ROUTER_LOG_DIR = $DocsDir }
if (-not $env:ROUTER_MAX_STEPS)       { $env:ROUTER_MAX_STEPS = "10" }
if (-not $env:ROUTER_ENFORCE_RULE_ACK){ $env:ROUTER_ENFORCE_RULE_ACK = "true" }
if (-not $env:ROUTER_PORT)            { $env:ROUTER_PORT = "8085" }

$ProjectDirPosix  = ($ProjectDir -replace '\\','/')
$ProjectDirWinEsc = ($ProjectDir -replace '\\','\\')

Write-Host "LOG_DIR      : $($env:ROUTER_LOG_DIR)"
Write-Host "MAX_STEPS    : $($env:ROUTER_MAX_STEPS)"
Write-Host "RULE_ACK     : $($env:ROUTER_ENFORCE_RULE_ACK)"
Write-Host "ROUTER_PORT  : $($env:ROUTER_PORT)"
Write-Host ""
Write-Host "===== Placement Guidance ====="
Write-Host "Agent Profiles (use POSIX path with /):`n  $ProjectDirPosix"
Write-Host "MCP Servers (use Windows path with double backslashes \\):`n  $ProjectDirWinEsc"
Write-Host "================================"
Write-Host ""

# Quick check uvicorn is present
$uv = & python -c "import pkgutil; import sys; sys.exit(0 if pkgutil.find_loader('uvicorn') else 1)"; if ($LASTEXITCODE -ne 0) {
  Write-Host "❌ uvicorn not found. Run:  python -m pip install uvicorn fastapi pydantic"
  exit 1
}

Write-Host "Starting Router MCP (attached)..."
Write-Host "Tip: Open another terminal to tail logs:"
Write-Host "  Get-Content -Path `"$($DocsDir)\build-summary.md`" -Wait"
Write-Host "  Get-Content -Path `"$($DocsDir)\router_log.jsonl`" -Wait"
Write-Host ""

# Run in the foreground (visible). Stop with Ctrl+C or closing the window.
python -m uvicorn router_mcp:APP --host 127.0.0.1 --port $env:ROUTER_PORT --log-level info --no-use-colors
