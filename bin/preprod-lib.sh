# Shared helpers for duplicate_org.sh / duplicate_data.sh (sourced, not executed).
# Everything runs from the laptop over ssh: SQL inside the alert-api `db` containers, S3 work
# inside the preprod `backend` container (it holds the S3 credentials, nothing leaves the servers).
#
# Overrides for local testing: PROD_HOST=local PREPROD_HOST=local COMPOSE_PROJECT=pyronear
#   PROD_DB=src PROD_SERVER_NAME=fakeprod DOCKER=docker
set -euo pipefail

PROD=${PROD_HOST:-ubuntu@91.134.45.165}
PREPROD=${PREPROD_HOST:-ubuntu@51.210.213.188}
SSH="ssh -i ${SSH_PRIVATE_KEY_FILE:-$(dirname "$0")/../../pi-manager-fr/id_rsa} -o StrictHostKeyChecking=no"
DOCKER=${DOCKER:-sudo docker}  # docker command on the servers (ubuntu is not in the docker group)
COMPOSE_PROJECT=${COMPOSE_PROJECT:-alert-api}
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

run_on() { local host=$1; shift; if [ "$host" = local ]; then sh -c "$*"; else $SSH "$host" "$*"; fi; }
# `$(docker ps ...)` is left unexpanded on purpose: it is evaluated on the server.
compose_container() { echo "\$($DOCKER ps -q -f label=com.docker.compose.project=$COMPOSE_PROJECT -f label=com.docker.compose.service=$1)"; }
psql_on() { # <host> [db]: runs the SQL read on stdin
  run_on "$1" "$DOCKER exec -i \"$(compose_container db)\" sh -c 'exec psql -qAXt -v ON_ERROR_STOP=1 -U \$POSTGRES_USER -d ${2:-\$POSTGRES_DB}'"
}
prod_psql() { psql_on "$PROD" "${PROD_DB:-}"; }
preprod_psql() { psql_on "$PREPROD" "${PREPROD_DB:-}"; }
backend_on() { local host=$1; shift; run_on "$host" "$DOCKER exec -i \"$(compose_container backend)\" $*"; }
prod_backend() { backend_on "$PROD" "$@"; }
preprod_backend() { backend_on "$PREPROD" "$@"; }

check_org() { # org names are interpolated into SQL, keep them to the API's own charset
  [[ $1 =~ ^[A-Za-z0-9_.-]+$ ]] || { echo "invalid organization name '$1'" >&2; exit 1; }
}

export_table() { # <table> <select>: prod -> $WORK/<table>.csv, prefixed with the global $CTE
  echo "COPY ($CTE $2) TO STDOUT WITH CSV HEADER" | prod_psql >"$WORK/$1.csv"
  echo "prod: $(($(wc -l <"$WORK/$1.csv") - 1)) $1" >&2
}
stage() { # SQL that loads $WORK/<table>.csv into a temp table src_<table> typed after the preprod table
  local cols; cols=$(head -1 "$WORK/$1.csv")
  echo "CREATE TEMP TABLE src_$1 AS SELECT $cols FROM $1 WITH NO DATA;"
  echo "COPY src_$1 ($cols) FROM STDIN WITH CSV HEADER;"
  cat "$WORK/$1.csv"
  echo '\.'
}
# SQL mapping staged prod ids to preprod ids: org by '<name>-preprod', cameras by name,
# poses by (camera, azimuth, patrol_id). Lookups only, rows must already exist (duplicate_org.sh).
maps_sql() {
  cat <<'SQL'
CREATE TEMP TABLE org_map AS SELECT s.id AS old_id, o.id AS new_id FROM src_organizations s JOIN organizations o ON o.name = s.name || '-preprod';
CREATE TEMP TABLE cam_map AS SELECT s.id AS old_id, c.id AS new_id FROM src_cameras s JOIN cameras c USING (name);
CREATE TEMP TABLE pose_map AS
  SELECT DISTINCT ON (s.id) s.id AS old_id, p.id AS new_id
  FROM src_poses s JOIN cam_map m ON m.old_id = s.camera_id
  JOIN poses p ON p.camera_id = m.new_id AND p.azimuth = s.azimuth AND p.patrol_id IS NOT DISTINCT FROM s.patrol_id
  ORDER BY s.id, p.id;
SQL
}
