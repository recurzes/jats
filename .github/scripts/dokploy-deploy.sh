#!/usr/bin/env bash
# Points the Dokploy application at one image tag, redeploys it, then waits for /health.
# Needs: DOKPLOY_URL, DOKPLOY_API_KEY, DOKPLOY_APP_ID, IMAGE (with tag), HEALTH_URL.
set -euo pipefail

for name in DOKPLOY_URL DOKPLOY_API_KEY DOKPLOY_APP_ID IMAGE HEALTH_URL; do
  if [ -z "${!name:-}" ]; then
    echo "::error::$name is not set"
    exit 1
  fi
done

dokploy() {
  curl -fsS -X POST "$DOKPLOY_URL/api/$1" \
    -H "x-api-key: $DOKPLOY_API_KEY" \
    -H "Content-Type: application/json" \
    -d "$2"
  echo
}

echo "Deploying $IMAGE"
dokploy application.saveDockerProvider \
  "$(jq -n --arg id "$DOKPLOY_APP_ID" --arg image "$IMAGE" '{applicationId: $id, dockerImage: $image}')"
dokploy application.deploy \
  "$(jq -n --arg id "$DOKPLOY_APP_ID" '{applicationId: $id}')"

for attempt in $(seq 1 30); do
  if curl -fsS "$HEALTH_URL"; then
    echo
    echo "Healthy after $attempt attempt(s)"
    exit 0
  fi
  sleep 6
done

echo "::error::Health check failed: $HEALTH_URL"
exit 1
