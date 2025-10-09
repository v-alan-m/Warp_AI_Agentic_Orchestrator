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
if (-not $env:ROUTER_MAX_STEPS)       { $env:ROUTER_MAX_STEPS = "17" }
if (-not $env:ROUTER_ENFORCE_RULE_ACK){ $env:ROUTER_ENFORCE_RULE_ACK = "true" }
if (-not $env:ROUTER_PORT)            { $env:ROUTER_PORT = "8085" }

# NEW: behavior toggles (global)
if (-not $env:ROUTER_FORCE_AUTORUN)     { $env:ROUTER_FORCE_AUTORUN     = "true" }  # false = manual
if (-not $env:ROUTER_ECHO_FINAL) { $env:ROUTER_ECHO_FINAL = "true" }  # include step lines
if (-not $env:ROUTER_STEPWISE_ECHO)     { $env:ROUTER_STEPWISE_ECHO     = "true" }  # auto-run but return each step

# --- Resolve Python interpreter (prefer repo venv) ---
$Python = Join-Path $ScriptDir ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }

$ProjectDirPosix  = ($ProjectDir -replace '\\','/')
$ProjectDirWinEsc = ($ProjectDir -replace '\\','\\')

Write-Host "LOG_DIR      : $($env:ROUTER_LOG_DIR)"
Write-Host "MAX_STEPS    : $($env:ROUTER_MAX_STEPS)"
Write-Host "RULE_ACK     : $($env:ROUTER_ENFORCE_RULE_ACK)"
Write-Host "ROUTER_PORT  : $($env:ROUTER_PORT)"
Write-Host "AUTO_RUN     : $($env:ROUTER_FORCE_AUTORUN)"
Write-Host "ECHO_STEPS   : $($env:ROUTER_ECHO_FINAL)"
Write-Host "STEPWISE     : $($env:ROUTER_STEPWISE_ECHO)"
Write-Host "PYTHON       : $Python"
Write-Host ""

# Quick check required modules are present (in the SAME interpreter we'll run)
$probe = 'import importlib.util, sys; mods=["uvicorn","fastapi","pydantic"]; sys.exit(0 if all(importlib.util.find_spec(m) for m in mods) else 1)'
& $Python -c $probe
if ($LASTEXITCODE -ne 0) {
  Write-Host "❌ Required modules not found in this interpreter (If .venv present, activate it using: .\.venv\Scripts\activate)"
  Write-Host "   Install into this venv/interpreter:"
  Write-Host "   $Python -m pip install uvicorn fastapi pydantic"
  exit 1
}

Write-Host "Starting Router MCP (attached)..."
Write-Host ""
Write-Host "Tip:"
Write-Host ""
Write-Host "View the build summary live by opening a new terminal and pasting in:"
Write-Host "  Get-Content -Path `"$($DocsDir)\build-summary.md`" -Wait"
Write-Host ""
Write-Host "View the router log live by opening a new terminal and pasting in:"
Write-Host "  Get-Content -Path `"$($DocsDir)\router_log.jsonl`" -Wait"
Write-Host ""
Write-Host "===== Placement Guidance ====="
Write-Host ""
Write-Host "IMPORTANT: Copy and paste these directories into Warp's MCP configuration JSON and Agent profile pages respectively."
Write-Host ""
Write-Host "Agent Profiles (use POSIX path with /):`n  $ProjectDirPosix"
Write-Host ""
Write-Host "MCP Servers (use Windows path with double backslashes \\):`n  $ProjectDirWinEsc"
Write-Host ""
Write-Host "=========Running server========="
Write-Host ""
Write-Host "Starting router_mcp server (router_mcp.py):"
Write-Host ""

# Run in the foreground (visible). Stop with Ctrl+C or closing the window.
& $Python -m uvicorn router_mcp:APP --host 127.0.0.1 --port $env:ROUTER_PORT --log-level info --no-use-colors

# For Windows Powershell 7, run: pwsh -NoProfile -ExecutionPolicy Bypass -File .\orchestrator.ps1
# Press Ctrl+C in that terminal to kill/stop the script.
