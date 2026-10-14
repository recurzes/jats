#!/usr/bin/env bash
# Checks that the three kinds of caller still work: public, web app and device.
#
#   API_URL=https://api.example.com SMOKE_TOKEN=<token> DEVICE_KEY=<key> bash scripts/smoke.sh
#
# SMOKE_TOKEN  an access token of the owner: `await authClient.token()` in the web app's browser
#              console. It lasts 15 minutes.
# DEVICE_KEY   a device key, as printed by `python -m app.cli create-device`.
# API_URL      defaults to http://localhost:8000.
#
# The device check is a real claim: a waiting job is claimed and is not printed. It returns to
# the queue after LEASE_SECONDS, with one of its MAX_ATTEMPTS used.
set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"
API_URL="${API_URL%/}"
: "${SMOKE_TOKEN:?Set SMOKE_TOKEN to an access token of the owner}"
: "${DEVICE_KEY:?Set DEVICE_KEY to a device key}"

body=$(mktemp)
trap 'rm -f "$body"' EXIT
failed=0

# check <name> <path> <accepted status codes> <text the body must hold> [curl options]
check() {
  local name=$1 path=$2 accepted=$3 expected=$4 code
  shift 4
  code=$(curl -sS -o "$body" -w '%{http_code}' --max-time 15 "$@" "$API_URL$path") || code=000
  if [[ " $accepted " != *" $code "* ]]; then
    echo "FAIL  $name: $path answered $code"
    head -c 300 "$body"; echo
    failed=1
  elif [[ "$code" == 200 && "$(cat "$body")" != *"$expected"* ]]; then
    echo "FAIL  $name: $path answered 200 without $expected"
    failed=1
  else
    echo "ok    $name: $path answered $code"
  fi
  last_code=$code
}

check "public " /health 200 '"status":"ok"'
check "web app" /status 200 '"last_sync"' -H "Authorization: Bearer $SMOKE_TOKEN"
check "device " /device/jobs/next "200 204" '"lines"' -H "X-Device-Key: $DEVICE_KEY"
if [[ "$last_code" == 200 ]]; then
  echo "note  a print job was waiting and this run claimed it; it returns to the queue by itself"
fi

exit "$failed"
