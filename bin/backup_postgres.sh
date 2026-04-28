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

# Quote remote-side values to survive spaces / shell metacharacters.
Q_ENV_FILE=$(printf '%q' "${ENV_FILE}")
Q_CONTAINER=$(printf '%q' "${CONTAINER}")

# ====== READ DB CREDS FROM SERVER ======
echo "Reading DB config from ${ENV_FILE}..."
read_env_var() {
  local key="$1"
  ssh "${SSH_USER}@${SERVER_HOST}" \
    "set -o pipefail; grep -E ^${key}= ${Q_ENV_FILE} | head -n1 | cut -d= -f2-"
}

PGUSER=$(read_env_var POSTGRES_USER)
DB=$(read_env_var POSTGRES_DB)

if [ -z "${PGUSER}" ] || [ -z "${DB}" ]; then
  echo "ERROR: POSTGRES_USER or POSTGRES_DB missing in ${ENV_FILE}" >&2
  exit 1
fi

Q_PGUSER=$(printf '%q' "${PGUSER}")
Q_DB=$(printf '%q' "${DB}")

OUTPUT_FILE="${DB}_${DATE}.dump"
TMP_FILE="${OUTPUT_FILE}.tmp.$$"
trap 'rm -f "${TMP_FILE}"' EXIT INT TERM

# ====== BACKUP ======
echo "Starting backup of ${DB} (user=${PGUSER}) → ${OUTPUT_FILE}..."
ssh "${SSH_USER}@${SERVER_HOST}" \
  "sudo docker exec ${Q_CONTAINER} pg_dump -U ${Q_PGUSER} -d ${Q_DB} -Fc" \
  > "${TMP_FILE}"

# ====== VERIFY ======
SIZE=$(stat -f%z "${TMP_FILE}" 2>/dev/null || stat -c%s "${TMP_FILE}")
if [ "${SIZE}" -lt 1024 ]; then
  echo "ERROR: backup file too small (${SIZE} bytes)" >&2
  exit 1
fi

mv "${TMP_FILE}" "${OUTPUT_FILE}"
trap - EXIT INT TERM
echo "Backup OK: ${OUTPUT_FILE} (${SIZE} bytes)"
