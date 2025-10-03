#!/usr/bin/env bash
# orchestrator.sh
# Start Router MCP (uvicorn) + wait for /health + live-tail logs (macOS/Linux)

set -euo pipefail

# --- Resolve paths (repo root = folder containing this script) ---
SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

DOCS_DIR="$SCRIPT_DIR/docs"
PROJECT_DIR="$SCRIPT_DIR/project"

# Ensure docs directory & files exist (so tails don't fail)
mkdir -p "$DOCS_DIR"
touch "$DOCS_DIR/build-summary.md" "$DOCS_DIR/router_log.jsonl" "$DOCS_DIR/CHANGELOG.md"

# --- Environment (edit as needed; keep in sync with README) ---
: "${ROUTER_LOG_DIR:=$DOCS_DIR}"
: "${ROUTER_MAX_STEPS:=10}"
: "${ROUTER_ENFORCE_RULE_ACK:=true}"
: "${ROUTER_PORT:=8085}"

HEALTH_URL="http://127.0.0.1:${ROUTER_PORT}/health"

echo "LOG_DIR      : $ROUTER_LOG_DIR"
echo "MAX_STEPS    : $ROUTER_MAX_STEPS"
echo "RULE_ACK     : $ROUTER_ENFORCE_RULE_ACK"
echo "ROUTER_PORT  : $ROUTER_PORT"
echo "HEALTH URL   : $HEALTH_URL"
echo

# --- Cleanup on exit ---
UVICORN_PID=""
TAIL_PIDS=()

cleanup() {
  set +e
  if [[ -n "${UVICORN_PID}" ]] && ps -p "${UVICORN_PID}" >/dev/null 2>&1; then
    kill "${UVICORN_PID}" 2>/dev/null || true
  fi
  for pid in "${TAIL_PIDS[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

# --- Sanity: uvicorn present? ---
if ! python -c "import pkgutil; import sys; sys.exit(0 if pkgutil.find_loader('uvicorn') else 1)"; then
  echo "❌ uvicorn not found. Install with:  python -m pip install uvicorn fastapi pydantic"
  exit 1
fi

# --- Start uvicorn in background (module import style is most reliable) ---
# Use line-buffering so logs stream promptly.
echo "Starting Router MCP (uvicorn)…"
stdbuf -oL -eL python -m uvicorn router_mcp:APP \
  --host 127.0.0.1 \
  --port "${ROUTER_PORT}" \
  --log-level info &
UVICORN_PID=$!

sleep 0.2

# --- Wait for /health (timeout ~60s) ---
echo "Waiting for router to become healthy…"
deadline=$((SECONDS + 60))
healthy=0
while (( SECONDS < deadline )); do
  if curl -fsS --max-time 3 "$HEALTH_URL" >/dev/null; then
    healthy=1
    break
  fi
  printf "."
  sleep 0.8
done
echo

if (( ! healthy )); then
  echo "⚠️  Router did not become healthy within 60s."
  echo "Diagnostics:"
  echo "  * Confirm you're in the repo root: $SCRIPT_DIR"
  echo "  * Confirm router_mcp.py exists and is importable."
  echo "  * Install deps: python -m pip install uvicorn fastapi pydantic"
  echo "  * Check if port ${ROUTER_PORT} is in use (macOS/Linux): lsof -i :${ROUTER_PORT}"
  echo "  * Last 50 lines of uvicorn (if any):"
  # Try to dump recent uvicorn stderr/stdout (best-effort)
  pkill -P "${UVICORN_PID}" 2>/dev/null || true
  kill "${UVICORN_PID}" 2>/dev/null || true
  wait "${UVICORN_PID}" 2>/dev/null || true
  exit 1
fi

echo "✅ Router is healthy at ${HEALTH_URL}"
echo "Tailing logs: build-summary.md and router_log.jsonl (Ctrl+C to stop tails; server stops on exit)"
echo

# --- Tail logs (non-terminating) ---
BUILD_SUMMARY="$DOCS_DIR/build-summary.md"
JSON_LOG="$DOCS_DIR/router_log.jsonl"

( echo "[TAIL] $BUILD_SUMMARY"; tail -n +1 -F "$BUILD_SUMMARY" ) &
TAIL_PIDS+=($!)
( echo "[TAIL] $JSON_LOG"; tail -n +1 -F "$JSON_LOG" ) &
TAIL_PIDS+=($!)

# --- Also stream uvicorn process output to console ---
# Keep the script in the foreground by waiting on the uvicorn process.
wait "${UVICORN_PID}"
