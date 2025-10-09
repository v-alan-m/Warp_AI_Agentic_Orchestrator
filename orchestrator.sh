#!/usr/bin/env bash
# orchestrator.sh
# Safe Attached (macOS/Linux): start Router MCP (uvicorn) in the foreground, no background jobs, no hidden windows.
# - Creates/ensures docs + log files
# - Prints placement guidance (POSIX vs double-backslash Windows path)
# - Runs uvicorn attached (stop with Ctrl+C)
# - Disables ANSI colors in uvicorn logs via --no-use-colors for clean output

set -euo pipefail

# --- Resolve paths (repo root = folder containing this script) ---
SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

DOCS_DIR="$SCRIPT_DIR/docs"
PROJECT_DIR="$SCRIPT_DIR/project"

# Ensure docs directory & files exist (so manual tails don't fail)
mkdir -p "$DOCS_DIR"
: > "$DOCS_DIR/build-summary.md"   || true
: > "$DOCS_DIR/router_log.jsonl"   || true
: > "$DOCS_DIR/CHANGELOG.md"       || true

# --- Environment (defaults; keep in sync with README) ---
export ROUTER_LOG_DIR="${ROUTER_LOG_DIR:-$DOCS_DIR}"
export ROUTER_MAX_STEPS="${ROUTER_MAX_STEPS:-17}"
export ROUTER_ENFORCE_RULE_ACK="${ROUTER_ENFORCE_RULE_ACK:-true}"
export ROUTER_PORT="${ROUTER_PORT:-8085}"

# Behavior toggles (global)
export ROUTER_FORCE_AUTORUN="${ROUTER_FORCE_AUTORUN:-true}"         # false = manual
export ROUTER_ECHO_INTERMEDIATE="${ROUTER_ECHO_INTERMEDIATE:-true}" # include step lines
export ROUTER_STEPWISE_ECHO="${ROUTER_STEPWISE_ECHO:-true}"         # auto-run but return each step

# --- Resolve Python interpreter (prefer repo venv) ---
if [[ -x "$SCRIPT_DIR/.venv/bin/python" ]]; then
  PYTHON="$SCRIPT_DIR/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
  PYTHON="$(command -v python)"
else
  echo "❌ No python interpreter found. Install Python 3.10+ or create .venv first."
  exit 1
fi

echo "LOG_DIR      : $ROUTER_LOG_DIR"
echo "MAX_STEPS    : $ROUTER_MAX_STEPS"
echo "RULE_ACK     : $ROUTER_ENFORCE_RULE_ACK"
echo "ROUTER_PORT  : $ROUTER_PORT"
echo "AUTO_RUN     : $ROUTER_FORCE_AUTORUN"
echo "ECHO_STEPS   : $ROUTER_ECHO_INTERMEDIATE"
echo "STEPWISE     : $ROUTER_STEPWISE_ECHO"
echo "PYTHON       : $PYTHON"
echo

# --- Placement Guidance (POSIX for Profiles, double-backslash Windows for MCP Servers JSON) ---
POSIX_PROJECT_DIR="$PROJECT_DIR"
WIN_ESCAPED_PROJECT_DIR="${PROJECT_DIR//\//\\\\}"
echo "===== Placement Guidance ====="
echo "Agent Profiles (use POSIX path with /):"
echo "  $POSIX_PROJECT_DIR"
echo "MCP Servers (use Windows path with double backslashes \\):"
printf "  %s\n" "$WIN_ESCAPED_PROJECT_DIR"
echo "==============================="
echo

# --- Sanity: uvicorn present in the SAME interpreter we will run ---
if ! "$PYTHON" - <<'PY'
import importlib.util, sys
sys.exit(0 if importlib.util.find_spec("uvicorn") else 1)
PY
then
  echo "❌ uvicorn not found in this interpreter."
  echo "   Install into your venv (recommended) or current Python:"
  echo "   $PYTHON -m pip install uvicorn fastapi pydantic"
  exit 1
fi

# --- Tips for watching logs in another terminal ---
echo "Tip: In another terminal you can watch live logs with:"
echo "  tail -f \"$DOCS_DIR/build-summary.md\""
echo "  tail -f \"$DOCS_DIR/router_log.jsonl\""
echo

# --- Start uvicorn in the foreground (attached) ---
# We explicitly disable ANSI colors for clean, plain log lines.
# (Alternative env approach would be: NO_COLOR=1 python -m uvicorn ... )
echo "Starting Router MCP (attached, Ctrl+C to stop)…"
# Disable ANSI colors for clean output (you could also export NO_COLOR=1)
exec "$PYTHON" -m uvicorn router_mcp:APP \
  --host 127.0.0.1 \
  --port "${ROUTER_PORT}" \
  --log-level info \
  --no-use-colors

# Press Ctrl+C in that terminal to kill/stop the script.