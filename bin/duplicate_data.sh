#!/usr/bin/env bash
# Duplicate one organization's sequences, detections (frames + crops on S3) and alerts from the prod
# alert API to '<org>-preprod' on preprod, verbatim: same timestamps, labels, scores, validation
# status (an API replay would re-group everything at now()). Runs duplicate_org.sh first.
# Window: sequences started on [from, to] (UTC calendar days, both inclusive), their detections,
# unsequenced detections created in the window, and the alerts those sequences belong to.
# Re-runnable: rows already present are skipped.
#
# Usage: bin/duplicate_data.sh <org_name> <from YYYY-MM-DD> <to YYYY-MM-DD>
ORG=${1:?usage: $0 <org_name> <from YYYY-MM-DD> <to YYYY-MM-DD>}
FROM=${2:?usage: $0 <org_name> <from YYYY-MM-DD> <to YYYY-MM-DD>}
TO=${3:?usage: $0 <org_name> <from YYYY-MM-DD> <to YYYY-MM-DD>}
for d in "$FROM" "$TO"; do [[ $d =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] || { echo "invalid date '$d', expected YYYY-MM-DD" >&2; exit 1; }; done
"$(dirname "$0")/duplicate_org.sh" "$ORG"
. "$(dirname "$0")/preprod-lib.sh"
check_org "$ORG"

WINDOW="BETWEEN '$FROM' AND DATE '$TO' + 1"  # [from 00:00, to+1 00:00]; the extra instant is harmless
CTE="WITH org AS (SELECT id FROM organizations WHERE name = '$ORG'),
cams AS (SELECT id FROM cameras WHERE organization_id = (SELECT id FROM org)),
seqs AS (SELECT * FROM sequences WHERE camera_id IN (SELECT id FROM cams) AND started_at $WINDOW),
dets AS (SELECT * FROM detections WHERE camera_id IN (SELECT id FROM cams)
  AND (sequence_id IN (SELECT id FROM seqs) OR (sequence_id IS NULL AND created_at $WINDOW))),
links AS (SELECT * FROM alerts_sequences WHERE sequence_id IN (SELECT id FROM seqs)),
al AS (SELECT * FROM alerts WHERE id IN (SELECT alert_id FROM links))"
export_table organizations "SELECT * FROM organizations WHERE id = (SELECT id FROM org)"
export_table cameras "SELECT * FROM cameras WHERE organization_id = (SELECT id FROM org)"
export_table poses "SELECT * FROM poses WHERE camera_id IN (SELECT id FROM cams)"
export_table sequences "SELECT * FROM seqs"
export_table detections "SELECT * FROM dets"
export_table alerts "SELECT * FROM al"
export_table alerts_sequences "SELECT * FROM links"

{
  echo "BEGIN;"
  for t in organizations cameras poses sequences detections alerts alerts_sequences; do stage $t; done
  maps_sql
  cat <<'SQL'
-- Sequences: keep prod ids -> preprod ids in the staging table so detections and alerts can follow.
-- ponytail: dedup key (camera, started_at, sequence_azimuth); two smokes at the same instant and
-- azimuth would collapse into one. An existing row is not refreshed (last_seen_at, label, score).
ALTER TABLE src_sequences ADD COLUMN new_id int, ADD COLUMN existing bool DEFAULT false;
UPDATE src_sequences s SET new_id = x.id, existing = true
  FROM cam_map cm, sequences x
  WHERE cm.old_id = s.camera_id AND x.camera_id = cm.new_id AND x.started_at = s.started_at
    AND x.sequence_azimuth IS NOT DISTINCT FROM s.sequence_azimuth;
UPDATE src_sequences SET new_id = nextval(pg_get_serial_sequence('sequences', 'id')) WHERE new_id IS NULL;
-- validation_due_at / validation_lease_until stay NULL: the preprod worker must not re-validate
-- (and re-notify) sequences that already carry their prod verdict.
INSERT INTO sequences (id, camera_id, pose_id, camera_azimuth, is_wildfire, sequence_azimuth, cone_angle, started_at, last_seen_at,
                       max_conf, temporal_model_score, temporal_model_version, temporal_api_version, is_validated, validation_status, validation_attempts)
  SELECT s.new_id, cm.new_id, pm.new_id, s.camera_azimuth, s.is_wildfire, s.sequence_azimuth, s.cone_angle, s.started_at, s.last_seen_at,
         s.max_conf, s.temporal_model_score, s.temporal_model_version, s.temporal_api_version, s.is_validated, s.validation_status, s.validation_attempts
  FROM src_sequences s JOIN cam_map cm ON cm.old_id = s.camera_id LEFT JOIN pose_map pm ON pm.old_id = s.pose_id
  WHERE NOT s.existing;

-- Detections: bucket keys are kept verbatim (objects are copied under the same key in the preprod bucket).
CREATE TEMP TABLE ins_dets AS
  SELECT cm.new_id AS camera_id, pm.new_id AS pose_id, sm.new_id AS sequence_id, d.bucket_key, d.crop_bucket_key, d.bbox, d.others_bboxes, d.created_at, d.recorded_at
  FROM src_detections d
  JOIN cam_map cm ON cm.old_id = d.camera_id
  JOIN pose_map pm ON pm.old_id = d.pose_id
  LEFT JOIN src_sequences sm ON sm.id = d.sequence_id
  WHERE NOT EXISTS (SELECT 1 FROM detections x WHERE x.camera_id = cm.new_id AND x.bucket_key = d.bucket_key AND x.bbox = d.bbox);
INSERT INTO detections (camera_id, pose_id, sequence_id, bucket_key, crop_bucket_key, bbox, others_bboxes, created_at, recorded_at)
  SELECT * FROM ins_dets;

-- Alerts, then the alert <-> sequence links through both maps. An alert also spanning sequences
-- outside the window gets those links when that window is duplicated.
ALTER TABLE src_alerts ADD COLUMN new_id int, ADD COLUMN existing bool DEFAULT false;
UPDATE src_alerts a SET new_id = x.id, existing = true
  FROM org_map om, alerts x
  WHERE om.old_id = a.organization_id AND x.organization_id = om.new_id AND x.started_at = a.started_at
    AND x.lat IS NOT DISTINCT FROM a.lat AND x.lon IS NOT DISTINCT FROM a.lon;
UPDATE src_alerts SET new_id = nextval(pg_get_serial_sequence('alerts', 'id')) WHERE new_id IS NULL;
INSERT INTO alerts (id, organization_id, lat, lon, started_at, last_seen_at)
  SELECT a.new_id, om.new_id, a.lat, a.lon, a.started_at, a.last_seen_at
  FROM src_alerts a JOIN org_map om ON om.old_id = a.organization_id WHERE NOT a.existing;
INSERT INTO alerts_sequences (alert_id, sequence_id)
  SELECT a.new_id, s.new_id FROM src_alerts_sequences x JOIN src_alerts a ON a.id = x.alert_id JOIN src_sequences s ON s.id = x.sequence_id
  ON CONFLICT DO NOTHING;

SELECT 'preprod: ' || count(*) FILTER (WHERE NOT existing) || ' sequences inserted, ' || count(*) FILTER (WHERE existing) || ' already there' FROM src_sequences
UNION ALL SELECT 'preprod: ' || count(*) || ' detections inserted' FROM ins_dets
UNION ALL SELECT 'preprod: ' || count(*) FILTER (WHERE NOT existing) || ' alerts inserted, ' || count(*) FILTER (WHERE existing) || ' already there' FROM src_alerts;
COMMIT;
SQL
} | preprod_psql >&2

# S3: frames and crops, same keys, prod org bucket -> preprod org bucket (bucket = SERVER_NAME-alert-api-<org id>).
PROD_ORG_ID=$(tail -1 "$WORK/organizations.csv" | cut -d, -f1)
PROD_SERVER=${PROD_SERVER_NAME:-$(prod_backend printenv SERVER_NAME)}
PREPROD_ORG_ID=$(echo "SELECT id FROM organizations WHERE name = '$ORG-preprod'" | preprod_psql)
KEYS=$(python3 -c '
import csv, sys
for row in csv.DictReader(sys.stdin):
    print(row["bucket_key"]); row["crop_bucket_key"] and print(row["crop_bucket_key"])' <"$WORK/detections.csv" | sort -u)

cat <<PY | preprod_backend python - >&2
import sys
from concurrent.futures import ThreadPoolExecutor
from botocore.exceptions import ClientError
from app.services.storage import s3_service
SRC = "${PROD_SERVER}-alert-api-${PROD_ORG_ID}"
DST = s3_service.resolve_bucket_name(${PREPROD_ORG_ID})
KEYS = """${KEYS}""".split()
s3 = s3_service._s3
if DST not in {b["Name"] for b in s3.list_buckets()["Buckets"]}:
    assert s3_service.create_bucket(DST), f"cannot create bucket {DST}"
def copy(key):
    try:
        s3.copy_object(Bucket=DST, Key=key, CopySource={"Bucket": SRC, "Key": key})
        return "ok"
    except ClientError as e:
        print(f"{key}: {e.response['Error']['Code']}", file=sys.stderr)
        return "error"
with ThreadPoolExecutor(16) as pool:
    done = list(pool.map(copy, KEYS))
print(f"s3: {done.count('ok')}/{len(KEYS)} objects copied {SRC} -> {DST}, {done.count('error')} errors")
PY
