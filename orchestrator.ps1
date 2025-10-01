<#
Orchestrator Launcher (router_mcp.py) — What this script does & in what order

PURPOSE
- Starts the Router MCP (FastAPI app in router_mcp.py).
- Ensures logs exist, checks health, and tails build logs live.
- Makes it easy to stop/clean up with Ctrl+C.

EXECUTION ORDER
1) Resolve paths
   - Figures out the script directory and the path to router_mcp.py.

2) Load / set environment
   - Uses existing env vars if present; otherwise applies safe defaults:
       ROUTER_LOG_DIR         → ./docs
       ROUTER_MAX_STEPS       → 10
       ROUTER_ENFORCE_RULE_ACK→ true   (require “rules loaded …” acks)
       ROUTER_PORT            → 8085

3) Prepare log files
   - Ensures ./docs exists and touches:
       ./docs/CHANGELOG.md
       ./docs/build-summary.md
       ./docs/router_log.jsonl

4) Launch the Router MCP
   - Starts:  python router_mcp.py
   - Captures stdout/stderr and the process ID for cleanup.

5) Health check loop
   - Polls http://localhost:${ROUTER_PORT}/health until it returns 200 OK (or times out).
   - If it fails, stops the process and exits with a warning.

6) Live tails (for convenience)
   - Streams the following so you can watch progress step-by-step:
       ./docs/build-summary.md   (human-readable timeline)
       ./docs/router_log.jsonl   (structured events; one JSON per line)

7) Graceful shutdown
   - On Ctrl+C or shell exit:
       - Kills the router process
       - Removes the PID file (if used)
       - Stops background log jobs

NOTES & TIPS
- Start this script BEFORE wiring Warp’s MCP Servers/Profiles so the Router is reachable.
- On Windows, ensure Python and Node are on PATH (python/python3, node/npx).
- If ports collide, set $env:ROUTER_PORT before running (or edit the script).
- If logs don’t update, verify write permissions for ./docs and the env var values.
- The Router enforces a safety cap via ROUTER_MAX_STEPS to prevent infinite loops.
#>

$ErrorActionPreference = "Stop"

# ----- Paths -----
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Router    = Join-Path $ScriptDir "router_mcp.py"

# ----- Config (env-backed with defaults) -----
$env:ROUTER_LOG_DIR           = $env:ROUTER_LOG_DIR           -ne $null ? $env:ROUTER_LOG_DIR           : (Join-Path $ScriptDir "docs")
$env:ROUTER_MAX_STEPS         = $env:ROUTER_MAX_STEPS         -ne $null ? $env:ROUTER_MAX_STEPS         : "10"
$env:ROUTER_ENFORCE_RULE_ACK  = $env:ROUTER_ENFORCE_RULE_ACK  -ne $null ? $env:ROUTER_ENFORCE_RULE_ACK  : "true"
$env:ROUTER_PORT              = $env:ROUTER_PORT              -ne $null ? $env:ROUTER_PORT              : "8085"

$LogDir   = $env:ROUTER_LOG_DIR
$Port     = [int]$env:ROUTER_PORT
$Health   = "http://localhost:$Port/health"
$PidFile  = Join-Path $ScriptDir ".router_mcp.pid"
$StdOut   = Join-Path $ScriptDir ".router_stdout.log"
$StdErr   = Join-Path $ScriptDir ".router_stderr.log"

# ----- Ensure dirs/files -----
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
New-Item -ItemType File -Force -Path (Join-Path $LogDir "CHANGELOG.md")     | Out-Null
New-Item -ItemType File -Force -Path (Join-Path $LogDir "build-summary.md") | Out-Null
New-Item -ItemType File -Force -Path (Join-Path $LogDir "router_log.jsonl") | Out-Null

# ----- Start server -----
Write-Host "Starting Router MCP on :$Port (logs in $LogDir)"
$Python = (Get-Command python3 -ErrorAction SilentlyContinue) ? "python3" : "python"

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $Python
$psi.Arguments = "`"$Router`""
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError  = $true
$psi.UseShellExecute = $false
$psi.CreateNoWindow = $true
$proc = New-Object System.Diagnostics.Process
$proc.StartInfo = $psi
$proc.Start() | Out-Null
$proc.Id | Out-File -FilePath $PidFile -Encoding ascii -Force

# Also stream to files
$so = [System.IO.StreamWriter]::new($StdOut, $true)
$se = [System.IO.StreamWriter]::new($StdErr, $true)
Start-Job -ScriptBlock {
    param($p,$soPath,$sePath)
    $proc = Get-Process -Id $p -ErrorAction SilentlyContinue
    if ($null -eq $proc) { return }
    $pso = $proc.StandardOutput
    $pse = $proc.StandardError
    while (!$proc.HasExited) {
        while (!$pso.EndOfStream) { (Get-Date -Format o) + " " + $pso.ReadLine() | Add-Content -Path $soPath }
        while (!$pse.EndOfStream) { (Get-Date -Format o) + " " + $pse.ReadLine() | Add-Content -Path $sePath }
        Start-Sleep -Milliseconds 250
    }
} -ArgumentList $proc.Id,$StdOut,$StdErr | Out-Null

# ----- Health check -----
Write-Host -NoNewline "Waiting for health…"
$ok = $false
1..30 | ForEach-Object {
    try {
        $resp = Invoke-WebRequest -Uri $Health -UseBasicParsing -TimeoutSec 2
        if ($resp.StatusCode -eq 200) { $ok = $true; return }
    } catch {}
    Write-Host -NoNewline "."
    Start-Sleep -Milliseconds 500
}
Write-Host ""

if (-not $ok) {
    Write-Warning "Router MCP failed health check. See $StdErr"
    try { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue } catch {}
    Remove-Item -Force -ErrorAction SilentlyContinue $PidFile
    exit 1
}

# ----- Cleanup on exit -----
$global:stopHandler = {
    Write-Host "`nStopping Router MCP (PID $($proc.Id))…"
    try { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue } catch {}
    Remove-Item -Force -ErrorAction SilentlyContinue $PidFile
    Write-Host "Done."
    Stop-Job * -ErrorAction SilentlyContinue | Receive-Job -ErrorAction SilentlyContinue | Out-Null
    exit
}
# Ctrl+C / close
Register-EngineEvent PowerShell.Exiting -Action $global:stopHandler | Out-Null

# ----- Live tails -----
Write-Host "Tailing Markdown + JSONL logs (Ctrl+C to stop)…"
$fsw1 = Get-Content -Path (Join-Path $LogDir "build-summary.md") -Wait
$fsw2 = Get-Content -Path (Join-Path $LogDir "router_log.jsonl") -Wait
