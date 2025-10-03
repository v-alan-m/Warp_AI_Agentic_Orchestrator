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
: "${ROUTER_LOG_DIR:=$DOCS_DIR}"
: "${ROUTER_MAX_STEPS:=17}"
: "${ROUTER_ENFORCE_RULE_ACK:=true}"
: "${ROUTER_PORT:=8085}"

echo "LOG_DIR      : $ROUTER_LOG_DIR"
echo "MAX_STEPS    : $ROUTER_MAX_STEPS"
echo "RULE_ACK     : $ROUTER_ENFORCE_RULE_ACK"
echo "ROUTER_PORT  : $ROUTER_PORT"
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

# --- Sanity: uvicorn present? ---
if ! python -c "import pkgutil,sys; sys.exit(0 if pkgutil.find_loader('uvicorn') else 1)"; then
  echo "❌ uvicorn not found. Install with:  python -m pip install uvicorn fastapi pydantic"
  exit 1
fi

# --- Tips for watching logs in another terminal (attached mode keeps this window for the server) ---
echo "Tip: In another terminal you can watch live logs with:"
echo "  tail -f \"$DOCS_DIR/build-summary.md\""
echo "  tail -f \"$DOCS_DIR/router_log.jsonl\""
echo

# --- Start uvicorn in the foreground (attached) ---
# We explicitly disable ANSI colors for clean, plain log lines.
# (Alternative env approach would be: NO_COLOR=1 python -m uvicorn ... )
echo "Starting Router MCP (attached, Ctrl+C to stop)…"
exec python -m uvicorn router_mcp:APP \
  --host 127.0.0.1 \
  --port "${ROUTER_PORT}" \
  --log-level info \
  --no-use-colors

# Press Ctrl+C in that terminal to kill/stop the script.