#!/usr/bin/env bash
# scripts/deploy_https.sh
# Start fungame backend and nginx HTTPS reverse-proxy, validate health and PNA preflight.
# Requires: deploy/certs/philippe.pem and philippe-key.pem (mkcert)

set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

CERT_DIR=deploy/certs
CERT_PEM=$CERT_DIR/philippe.pem
CERT_KEY=$CERT_DIR/philippe-key.pem

if [ ! -f "$CERT_PEM" ] || [ ! -f "$CERT_KEY" ]; then
  echo "Certificates not found in $CERT_DIR. See deploy/README-mkcert.md to generate mkcert certificates."
  exit 1
fi

echo "Starting backend (fungame)"
docker compose build fungame
docker compose up -d fungame

echo "Starting nginx reverse-proxy (HTTPS)"
docker compose up -d nginx

# wait for services
sleep 3

# health check loop (HTTPS via nginx)
HEALTH_URL="https://philippe.mourey.com:60000/api"
TIMEOUT=${TIMEOUT:-60}
INTERVAL=${INTERVAL:-2}

echo "Waiting for health at $HEALTH_URL (timeout ${TIMEOUT}s)"
start=$(date +%s)
while true; do
  if curl -k -sS -f "$HEALTH_URL" >/dev/null 2>&1; then
    echo "Health OK"
    break
  fi
  now=$(date +%s)
  elapsed=$((now-start))
  if [ $elapsed -ge $TIMEOUT ]; then
    echo "Healthcheck timeout after ${elapsed}s" >&2
    docker compose logs --tail=100 fungame || true
    docker compose logs --tail=100 nginx || true
    exit 2
  fi
  echo "still waiting... (${elapsed}s)"
  sleep $INTERVAL
done

# verify PNA preflight (curl to nginx preflight)
echo "Testing preflight (PNA) via nginx"
PRE_URL="https://philippe.mourey.com:60000/socket.io/?EIO=4&transport=polling"
PRE_OUT=$(curl -k -i -X OPTIONS "$PRE_URL" \
  -H "Origin: http://philippe.mourey.com:60000" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: content-type" \
  -H "Access-Control-Request-Private-Network: true" || true)

echo "--- preflight response ---"
echo "$PRE_OUT"

echo "Done. Open https://philippe.mourey.com:60000 in your browser. If your browser shows a padlock, the site is served over HTTPS and websocket upgrades should work through /socket.io/."
