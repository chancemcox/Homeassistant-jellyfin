#!/usr/bin/env bash
# Boot Home Assistant in Docker with jellyfin_ha installed against a mock
# Jellyfin server, then assert the integration sets up without errors.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HA_IMAGE="${HA_IMAGE:-ghcr.io/home-assistant/home-assistant:2024.11.0}"
NETWORK_NAME="${NETWORK_NAME:-jellyfin-ha-smoke}"
HA_NAME="${HA_NAME:-ha-jellyfin-smoke}"
MOCK_NAME="${MOCK_NAME:-mock-jellyfin}"
CONFIG_DIR="${CONFIG_DIR:-${ROOT}/.ha-smoke-config}"
TIMEOUT_SECS="${TIMEOUT_SECS:-300}"
JELLYFIN_PORT="${JELLYFIN_PORT:-8096}"

assert_port_connects() {
  local host="$1"
  local port="$2"
  local label="$3"
  echo "==> Testing TCP connect: ${label} (${host}:${port})"
  if ! timeout 5 bash -c "echo > /dev/tcp/${host}/${port}" 2>/dev/null; then
    # Fallback when /dev/tcp is unavailable
    if command -v nc >/dev/null 2>&1; then
      if ! nc -z -w 5 "${host}" "${port}"; then
        echo "::error::Port ${port} did not accept connections at ${host} (${label})"
        return 1
      fi
    elif command -v python3 >/dev/null 2>&1; then
      if ! python3 - "${host}" "${port}" <<'PY'
import socket, sys
host, port = sys.argv[1], int(sys.argv[2])
with socket.create_connection((host, port), timeout=5):
    pass
PY
      then
        echo "::error::Port ${port} did not accept connections at ${host} (${label})"
        return 1
      fi
    else
      echo "::error::No TCP probe tool available to test ${host}:${port}"
      return 1
    fi
  fi
  echo "Port ${port} is open at ${host} (${label})"
}

assert_jellyfin_http() {
  local url="$1"
  local label="$2"
  echo "==> Testing Jellyfin HTTP on port ${JELLYFIN_PORT}: ${label}"
  if ! curl -sf --connect-timeout 5 --max-time 10 "${url}" >/dev/null; then
    echo "::error::Jellyfin HTTP check failed for ${url} (${label})"
    return 1
  fi
  echo "Jellyfin HTTP OK: ${url}"
}

cleanup() {
  docker rm -f "${HA_NAME}" >/dev/null 2>&1 || true
  docker rm -f "${MOCK_NAME}" >/dev/null 2>&1 || true
  docker network rm "${NETWORK_NAME}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "==> Cleaning previous smoke containers"
cleanup
trap cleanup EXIT

echo "==> Preparing Home Assistant config at ${CONFIG_DIR}"
rm -rf "${CONFIG_DIR}"
mkdir -p "${CONFIG_DIR}/custom_components" "${CONFIG_DIR}/.storage"

cp -a "${ROOT}/custom_components/jellyfin_ha" \
  "${CONFIG_DIR}/custom_components/jellyfin_ha"

cat > "${CONFIG_DIR}/configuration.yaml" <<'YAML'
homeassistant:
  name: CI
  latitude: 0
  longitude: 0
  elevation: 0
  unit_system: metric
  time_zone: UTC
  country: US

http:
api:
config:
system_log:
logger:
  default: warning
  logs:
    custom_components.jellyfin_ha: debug
    homeassistant.setup: info
    homeassistant.loader: info

recorder:
  db_url: sqlite:////config/home-assistant_v2.db
YAML

# Mark onboarding complete so HA boots straight into normal operation.
cat > "${CONFIG_DIR}/.storage/onboarding" <<'JSON'
{
  "version": 4,
  "minor_version": 1,
  "key": "onboarding",
  "data": {
    "done": [
      "user",
      "core_config",
      "analytics",
      "integration"
    ]
  }
}
JSON

# Pre-install a config entry pointing at the mock Jellyfin service.
cat > "${CONFIG_DIR}/.storage/core.config_entries" <<'JSON'
{
  "version": 1,
  "minor_version": 1,
  "key": "core.config_entries",
  "data": {
    "entries": [
      {
        "created_at": "2024-11-12T00:00:00.000000+00:00",
        "entry_id": "01jellyfinhaci000000000000",
        "version": 1,
        "minor_version": 1,
        "domain": "jellyfin_ha",
        "title": "CI Jellyfin",
        "data": {
          "url": "http://mock-jellyfin:8096",
          "api_key": "ci-test-api-key",
          "name": "CI Jellyfin",
          "device_id": "ha-ci-device"
        },
        "options": {},
        "pref_disable_new_entities": false,
        "pref_disable_polling": false,
        "source": "user",
        "unique_id": "ci-jellyfin-server",
        "disabled_by": null,
        "discovery_keys": {},
        "modified_at": "2024-11-12T00:00:00.000000+00:00"
      }
    ]
  }
}
JSON

echo "==> Creating docker network ${NETWORK_NAME}"
docker network create "${NETWORK_NAME}" >/dev/null

echo "==> Starting mock Jellyfin (publishes host port ${JELLYFIN_PORT})"
docker run -d --name "${MOCK_NAME}" \
  --network "${NETWORK_NAME}" \
  --network-alias mock-jellyfin \
  -p "${JELLYFIN_PORT}:8096" \
  -v "${ROOT}/scripts/mock_jellyfin.py:/mock_jellyfin.py:ro" \
  python:3.12-alpine \
  python /mock_jellyfin.py >/dev/null

echo "==> Waiting for mock Jellyfin on port ${JELLYFIN_PORT}"
mock_up=0
for _ in $(seq 1 30); do
  if docker run --rm --network "${NETWORK_NAME}" curlimages/curl:8.10.1 \
      -sf "http://mock-jellyfin:8096/System/Info/Public" >/dev/null; then
    mock_up=1
    echo "Mock Jellyfin is up on container network"
    break
  fi
  sleep 1
done
if [[ "${mock_up}" -ne 1 ]]; then
  echo "::error::Mock Jellyfin did not become ready on port 8096"
  docker logs "${MOCK_NAME}" --tail 100 || true
  exit 1
fi

assert_port_connects "127.0.0.1" "${JELLYFIN_PORT}" "host → Jellyfin"
assert_jellyfin_http "http://127.0.0.1:${JELLYFIN_PORT}/System/Info/Public" "host → Jellyfin HTTP"

echo "==> Pulling Home Assistant image ${HA_IMAGE}"
docker pull "${HA_IMAGE}"

echo "==> Starting Home Assistant"
docker run -d --name "${HA_NAME}" \
  --network "${NETWORK_NAME}" \
  -e TZ=UTC \
  -v "${CONFIG_DIR}:/config" \
  -p 8123:8123 \
  "${HA_IMAGE}" >/dev/null

echo "==> Waiting for jellyfin_ha to become ready (timeout ${TIMEOUT_SECS}s)"
# HA 2024.11 may never emit "Home Assistant initialized" in this minimal
# config, so treat successful integration setup + port check as readiness.
deadline=$((SECONDS + TIMEOUT_SECS))
ready=0
while (( SECONDS < deadline )); do
  logs="$(docker logs "${HA_NAME}" 2>&1 || true)"
  if echo "${logs}" | grep -q "Jellyfin port open: mock-jellyfin:8096" \
    && echo "${logs}" | grep -q "Finished fetching jellyfin_ha data" \
    && echo "${logs}" | grep -q "success: True" \
    && echo "${logs}" | grep -Eq "Setup of domain jellyfin_ha took|Setting up jellyfin_ha"; then
    ready=1
    echo "jellyfin_ha is ready (port 8096 open + first successful poll)"
    break
  fi
  if echo "${logs}" | grep -Eq 'ERROR.*(jellyfin_ha|custom_components\.jellyfin_ha)|Setup failed for (custom integration )?jellyfin_ha|Error setting up entry .* for jellyfin_ha'; then
    echo "::error::jellyfin_ha failed during startup"
    echo "${logs}" | tail -n 300
    exit 1
  fi
  if ! docker ps --format '{{.Names}}' | grep -qx "${HA_NAME}"; then
    echo "::error::Home Assistant container exited early"
    docker logs "${HA_NAME}" --tail 200 || true
    exit 1
  fi
  sleep 3
done

if [[ "${ready}" -ne 1 ]]; then
  echo "::error::jellyfin_ha did not become ready within ${TIMEOUT_SECS}s"
  docker logs "${HA_NAME}" --tail 300 || true
  exit 1
fi

echo "==> Verifying Home Assistant can reach Jellyfin on port 8096"
docker exec "${HA_NAME}" python3 - <<'PY'
import socket
import sys
import urllib.request

host, port = "mock-jellyfin", 8096
try:
    with socket.create_connection((host, port), timeout=5):
        print(f"OK — TCP connect to {host}:{port}")
except OSError as err:
    print(f"::error::HA container cannot TCP-connect to {host}:{port}: {err}")
    sys.exit(1)

try:
    with urllib.request.urlopen(f"http://{host}:{port}/System/Info/Public", timeout=10) as resp:
        body = resp.read().decode()
        if resp.status != 200 or "CI Jellyfin" not in body:
            raise RuntimeError(f"unexpected response status={resp.status} body={body[:200]!r}")
        print(f"OK — HTTP reachability to {host}:{port}/System/Info/Public")
except Exception as err:  # noqa: BLE001
    print(f"::error::HA container cannot HTTP-reach Jellyfin on {host}:{port}: {err}")
    sys.exit(1)
PY

echo "==> Verifying jellyfin_ha modules import inside the container"
docker exec -e PYTHONPATH=/config "${HA_NAME}" python3 -c '
from custom_components.jellyfin_ha import api, config_flow, coordinator
print("OK — jellyfin_ha modules import")
'

echo "==> Checking setup success in logs"
logs="$(docker logs "${HA_NAME}" 2>&1)"

if ! echo "${logs}" | grep -Eqi 'Setting up jellyfin_ha|Setup of domain jellyfin_ha|jellyfin_ha\.sensor|Completed setup of jellyfin_ha'; then
  # Fallback: config entry setup messages vary by HA version.
  if ! echo "${logs}" | grep -qi 'jellyfin_ha'; then
    echo "::error::No jellyfin_ha activity found in Home Assistant logs"
    echo "${logs}" | tail -n 300
    exit 1
  fi
fi

echo "==> Failing on jellyfin_ha errors / tracebacks"
if echo "${logs}" | grep -E 'ERROR.*(jellyfin_ha|custom_components\.jellyfin_ha)|Setup failed for (custom integration )?jellyfin_ha|Error setting up entry .* for jellyfin_ha' \
  | tee /tmp/jellyfin_ha_errors.log | grep -q .; then
  echo "::error::Integration setup errors detected"
  cat /tmp/jellyfin_ha_errors.log
  echo "--- full HA log (tail 300) ---"
  echo "${logs}" | tail -n 300
  exit 1
fi

# Entity registry is written once entities are created.
echo "==> Checking that jellyfin_ha entities were created"
entity_file="${CONFIG_DIR}/.storage/core.entity_registry"
deadline=$((SECONDS + 60))
found_entities=0
while (( SECONDS < deadline )); do
  if [[ -f "${entity_file}" ]] && grep -q 'jellyfin_ha' "${entity_file}"; then
    found_entities=1
    break
  fi
  sleep 2
done

if [[ "${found_entities}" -ne 1 ]]; then
  echo "::error::No jellyfin_ha entities found in entity registry"
  echo "--- entity registry ---"
  [[ -f "${entity_file}" ]] && cat "${entity_file}" || echo "(missing)"
  echo "--- HA log (tail 200) ---"
  docker logs "${HA_NAME}" --tail 200 || true
  exit 1
fi

echo "==> Smoke test passed"
grep -o '"entity_id": "[^"]*jellyfin[^"]*"' "${entity_file}" | head -n 20 || true
