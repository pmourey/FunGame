#!/usr/bin/env bash
# scripts/deploy.sh - simple deploy helper: build (optional), up service, healthcheck loop + logs
# Usage:
#   ./scripts/deploy.sh               # build (par défaut) + up + healthcheck + follow logs
#   NO_BUILD=1 ./scripts/deploy.sh    # skip build
#   ./scripts/deploy.sh --timeout 60 --interval 2 --health-url http://localhost:5000/api

set -euo pipefail
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$SCRIPT_DIR/.."

COMPOSE_CMD=${COMPOSE_CMD:-docker compose}
SERVICE=${SERVICE:-fungame}
HEALTH_URL=${HEALTH_URL:-http://localhost:5000/api}
TIMEOUT=${TIMEOUT:-60}
INTERVAL=${INTERVAL:-2}
FOLLOW_LOGS=${FOLLOW_LOGS:-1}
NO_BUILD=${NO_BUILD:-0}

show_help(){
  cat <<EOF
Usage: $0 [--help] [--timeout N] [--interval S] [--health-url URL] [--no-follow]

Environment vars:
  NO_BUILD=1        skip docker compose build
  COMPOSE_CMD       override compose command (default 'docker compose')
  SERVICE           service name to start (default fungame)
  HEALTH_URL        URL to poll for health (default http://localhost:5000/api)
  TIMEOUT           health timeout seconds (default 60)
  INTERVAL          health poll interval seconds (default 2)
  FOLLOW_LOGS=0     don't follow logs after starting

Examples:
  ./scripts/deploy.sh
  NO_BUILD=1 ./scripts/deploy.sh --timeout 120
EOF
}

# basic args parsing
while [[ $# -gt 0 ]]; do
  case "$1" in
    --help|-h) show_help; exit 0 ;;
    --timeout) TIMEOUT="$2"; shift 2 ;;
    --interval) INTERVAL="$2"; shift 2 ;;
    --health-url) HEALTH_URL="$2"; shift 2 ;;
    --no-follow) FOLLOW_LOGS=0; shift ;;
    *) echo "Unknown arg: $1" >&2; show_help; exit 2 ;;
  esac
done

echo "[deploy] Using compose command: $COMPOSE_CMD"
echo "[deploy] Service: $SERVICE"
echo "[deploy] Health URL: $HEALTH_URL (timeout=${TIMEOUT}s interval=${INTERVAL}s)"

# optional build
if [[ "${NO_BUILD}" == "1" || "${NO_BUILD}" == "true" ]]; then
  echo "[deploy] NO_BUILD set -> skipping build"
else
  echo "[deploy] Building service ${SERVICE} (no-cache)"
  $COMPOSE_CMD build --no-cache "$SERVICE"
fi

# bring up service
echo "[deploy] Bringing up ${SERVICE}"
$COMPOSE_CMD up -d "$SERVICE"

# healthcheck loop in background
health_loop(){
  local start ts elapsed
  start=$(date +%s)
  while :; do
    if curl -sS -f "$HEALTH_URL" >/dev/null 2>&1; then
      echo "[deploy][health] OK: $HEALTH_URL"
      return 0
    fi
    ts=$(date +%s)
    elapsed=$((ts - start))
    if [ "$elapsed" -ge "$TIMEOUT" ]; then
      echo "[deploy][health] TIMEOUT after ${elapsed}s waiting for $HEALTH_URL" >&2
      return 1
    fi
    echo "[deploy][health] waiting... (${elapsed}s)"
    sleep "$INTERVAL"
  done
}

# start health loop in background and keep PID
health_loop &
HEALTH_PID=$!

# trap to forward signals and cleanup
cleanup(){
  echo "[deploy] Stopping background health loop (pid=$HEALTH_PID)"
  kill -9 "$HEALTH_PID" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

# follow logs if requested (this call will block)
if [ "$FOLLOW_LOGS" -eq 1 ]; then
  echo "[deploy] Following logs for ${SERVICE} (ctrl-c to exit)"
  # while health loop runs in background it will print status; show logs in foreground
  $COMPOSE_CMD logs -f --tail=200 "$SERVICE"
else
  echo "[deploy] Not following logs (FOLLOW_LOGS=0). Health loop continues in background (PID=$HEALTH_PID)"
fi

# wait for health loop to finish if logs were not followed
wait "$HEALTH_PID" || true

exit 0

