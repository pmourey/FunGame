#!/usr/bin/env bash
# scripts/clean.sh - safe cleanup helper for FunGame
# Stops and removes containers created by docker-compose in this project,
# removes anonymous volumes and (optionally) removes the fungame image.

set -euo pipefail
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$SCRIPT_DIR/.."

REMOVE_IMAGE=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --remove-image) REMOVE_IMAGE=1; shift ;;
    -h|--help) echo "Usage: $0 [--remove-image]"; exit 0 ;;
    *) echo "Unknown arg: $1"; exit 2 ;;
  esac
done

echo "[clean] Stopping and removing compose stack (volumes + orphans)"
docker compose down --volumes --remove-orphans || true

if [ "$REMOVE_IMAGE" -eq 1 ]; then
  echo "[clean] Removing local 'fungame:latest' image"
  docker rmi fungame:latest || true
fi

echo "[clean] Done. To free more space run: docker system prune --volumes -f"
