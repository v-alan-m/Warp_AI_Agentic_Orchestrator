#!/usr/bin/env bash
# Orchestrator launcher for Router MCP + live tails
# - Exports env vars
# - Starts router_mcp.py
# - Health-checks the server
# - Tails Markdown + JSONL logs
set -euo pipefail

# ----- Config (edit if you like) -----
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ROUTER="${SCRIPT_DIR}/router_mcp.py"
LOG_DIR="${ROUTER_LOG_DIR:-${SCRIPT_DIR}/docs}"
PORT="${ROUTER_PORT:-8085}"
MAX_STEPS="${ROUTER_MAX_STEPS:-17}"
HEALTH_URL="http://localhost:${PORT}/health"
PID_FILE="${SCRIPT_DIR}/.router_mcp.pid"

# ----- Ensure deps & dirs -----
mkdir -p "${LOG_DIR}"
touch "${LOG_DIR}/CHANGELOG.md" "${LOG_DIR}/build-summary.md"
touch "${LOG_DIR}/router_log.jsonl"

# ----- Env for the router process -----
export ROUTER_LOG_DIR="${LOG_DIR}"
export ROUTER_MAX_STEPS="${MAX_STEPS}"

# ----- Start server -----
echo "Starting Router MCP on :${PORT} (logs in ${LOG_DIR})"
# Prefer python3 if 'python' points to py2 on your system
if command -v python3 >/dev/null 2>&1; then PY=python3; else PY=python; fi

# Run in background
"${PY}" "${ROUTER}" >"${SCRIPT_DIR}/.router_stdout.log" 2>"${SCRIPT_DIR}/.router_stderr.log" &
ROUTER_PID=$!
echo "${ROUTER_PID}" > "${PID_FILE}"
echo "Router PID: ${ROUTER_PID}"

# ----- Health check -----
echo -n "Waiting for health…"
for i in {1..30}; do
  if curl -fsS "${HEALTH_URL}" >/dev/null 2>&1; then
    echo " OK"
    break
  fi
  echo -n "."
  sleep 0.5
done

if ! curl -fsS "${HEALTH_URL}" >/dev/null 2>&1; then
  echo -e "\n❌ Router MCP failed health check. See .router_stderr.log"
  kill "${ROUTER_PID}" 2>/dev/null || true
  exit 1
fi

# ----- Cleanup on exit -----
cleanup() {
  echo -e "\nStopping Router MCP (PID ${ROUTER_PID})…"
  kill "${ROUTER_PID}" 2>/dev/null || true
  rm -f "${PID_FILE}"
  echo "Done."
}
trap cleanup INT TERM EXIT

# ----- Live tails -----
echo "Tailing Markdown + JSONL logs (Ctrl+C to stop)…"
# Tail both files; -n +1 prints from first line for context
tail -n +1 -f "${LOG_DIR}/build-summary.md" "${LOG_DIR}/router_log.jsonl"
