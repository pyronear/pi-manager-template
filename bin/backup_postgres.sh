#!/bin/bash
set -euo pipefail

# ====== CONFIG (overridable via env) ======
INVENTORY="${INVENTORY:-inventory/hosts_prod}"
GROUP="${GROUP:-alert_server}"
SSH_USER="${SSH_USER:-ubuntu}"
CONTAINER="${CONTAINER:-alert-api-db-1}"
ENV_FILE="${ENV_FILE:-/home/alert_api/.env}"
DATE=$(date +%Y%m%d_%H%M)

# Run from repo root regardless of CWD
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

if [ ! -f "${INVENTORY}" ]; then
  echo "ERROR: inventory '${INVENTORY}' not found — run 'make prepare' first" >&2
  exit 1
fi

# ====== RESOLVE SERVER IP FROM INVENTORY ======
# Allow manual override; otherwise try local ansible-inventory; fall back to docker container.
if [ -z "${SERVER_HOST:-}" ]; then
  echo "Resolving IP for group ${GROUP} via Ansible inventory..."

  if command -v ansible-inventory >/dev/null 2>&1; then
    INV_JSON=$(ansible-inventory -i "${INVENTORY}" --list)
  else
    echo "  ansible-inventory not in PATH — using pyro-ansible docker container"
    INV_JSON=$(docker compose run --rm -T pyro-ansible \
      ansible-inventory -i "${INVENTORY}" --list 2>/dev/null)
  fi

  SERVER_HOST=$(echo "${INV_JSON}" | python3 -c "
import json, sys
data = sys.stdin.read()
data = data[data.find('{'):]   # strip any entrypoint pre-output
d = json.loads(data)
host = d['${GROUP}']['hosts'][0]
print(d['_meta']['hostvars'][host]['ansible_host'])
")
fi

echo "Target: ${SSH_USER}@${SERVER_HOST}"

# ====== READ DB CREDS FROM SERVER ======
echo "Reading DB config from ${ENV_FILE}..."
PGUSER=$(ssh "${SSH_USER}@${SERVER_HOST}" "grep '^POSTGRES_USER=' ${ENV_FILE} | cut -d= -f2-")
DB=$(ssh "${SSH_USER}@${SERVER_HOST}" "grep '^POSTGRES_DB=' ${ENV_FILE} | cut -d= -f2-")

OUTPUT_FILE="${DB}_${DATE}.dump"

# ====== BACKUP ======
echo "Starting backup of ${DB} (user=${PGUSER}) → ${OUTPUT_FILE}..."
ssh "${SSH_USER}@${SERVER_HOST}" \
  "sudo docker exec ${CONTAINER} pg_dump -U ${PGUSER} -d ${DB} -Fc" \
  > "${OUTPUT_FILE}"

# ====== VERIFY ======
SIZE=$(stat -f%z "${OUTPUT_FILE}" 2>/dev/null || stat -c%s "${OUTPUT_FILE}")
if [ "${SIZE}" -lt 1024 ]; then
  echo "ERROR: backup file too small (${SIZE} bytes)" >&2
  exit 1
fi

echo "Backup OK: ${OUTPUT_FILE} (${SIZE} bytes)"
