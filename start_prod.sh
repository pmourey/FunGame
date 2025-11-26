#!/usr/bin/env bash
# start_prod.sh - script minimal pour build et démarrer le service fungame en production (sans nginx)
# Usage:
#   ./start_prod.sh          # rebuild + up -d fungame
#   NO_BUILD=1 ./start_prod.sh  # skip docker build
#   ./start_prod.sh --help

set -euo pipefail
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$SCRIPT_DIR"

show_help(){
  cat <<EOF
start_prod.sh - démarre l'application FunGame (service 'fungame') via docker compose

Options via variables:
  NO_BUILD=1    : ne pas reconstruire l'image (utile pour dev rapide)
  COMPOSE_CMD   : chemin/commande docker compose (défaut: 'docker compose')

Examples:
  ./start_prod.sh
  NO_BUILD=1 ./start_prod.sh
EOF
}

if [[ ${1:-} == "--help" || ${1:-} == "-h" ]]; then
  show_help
  exit 0
fi

# prefer 'docker compose' (v2) but allow override
COMPOSE_CMD=${COMPOSE_CMD:-docker compose}

# basic checks
if ! command -v ${COMPOSE_CMD%% *} >/dev/null 2>&1 && ! command -v docker >/dev/null 2>&1; then
  echo "Erreur: docker (ou docker compose) n'est pas disponible dans le PATH" >&2
  exit 2
fi

# Stop and remove old orphan containers for a clean start
echo "[start_prod] Bringing down existing compose stack (remove orphans)"
$COMPOSE_CMD down --remove-orphans || true

# Optionally build
if [[ -z "${NO_BUILD:-}" ]]; then
  echo "[start_prod] Building image 'fungame' (no-cache)"
  $COMPOSE_CMD build --no-cache fungame
else
  echo "[start_prod] NO_BUILD set -> skipping build"
fi

# Start the service
echo "[start_prod] Starting service 'fungame' (detached)"
$COMPOSE_CMD up -d fungame

# wait a short time for healthcheck
echo "[start_prod] Waiting 3s for service to initialize..."
sleep 3

# show container status
echo "[start_prod] Containers:"
$COMPOSE_CMD ps

# Basic smoke checks
echo "[start_prod] Testing HTTP /api on localhost:5000"
if curl -sS -f http://localhost:5000/api >/dev/null 2>&1; then
  echo "[start_prod] /api OK"
else
  echo "[start_prod] /api FAILED - check 'docker logs <container>' for details" >&2
fi

echo "[start_prod] Done. To follow logs: $COMPOSE_CMD logs -f fungame"

