#!/usr/bin/env bash
# Duplicate one organization from the prod alert API to the preprod one, as '<org>-preprod', with
# its cameras (same names) and poses. Re-runnable: whatever already exists is skipped.
# telegram_id / slack_hook are NOT copied so preprod never notifies the prod channels.
# The org's S3 bucket is created too (the API only does it on its own POST /organizations).
#
# Usage: bin/duplicate_org.sh <org_name>
ORG=${1:?usage: $0 <org_name>}
. "$(dirname "$0")/preprod-lib.sh"
check_org "$ORG"

CTE="WITH org AS (SELECT id FROM organizations WHERE name = '$ORG'),
cams AS (SELECT id FROM cameras WHERE organization_id = (SELECT id FROM org))"
export_table organizations "SELECT * FROM organizations WHERE id = (SELECT id FROM org)"
export_table cameras "SELECT * FROM cameras WHERE organization_id = (SELECT id FROM org)"
export_table poses "SELECT * FROM poses WHERE camera_id IN (SELECT id FROM cams)"
[ "$(wc -l <"$WORK/organizations.csv")" -gt 1 ] || { echo "organization '$ORG' not found on prod" >&2; exit 1; }

{
  echo "BEGIN;"
  for t in organizations cameras poses; do stage $t; done
  cat <<'SQL'
INSERT INTO organizations (name)
  SELECT s.name || '-preprod' FROM src_organizations s WHERE NOT EXISTS (SELECT 1 FROM organizations WHERE name = s.name || '-preprod');
CREATE TEMP TABLE org_map AS SELECT s.id AS old_id, o.id AS new_id FROM src_organizations s JOIN organizations o ON o.name = s.name || '-preprod';

-- Cameras matched by name (globally unique). last_image / device ips are not mirrored.
CREATE TEMP TABLE ins_cams AS
  SELECT m.new_id AS organization_id, c.name, c.angle_of_view, c.elevation, c.lat, c.lon, c.is_trustable, c.last_active_at, c.created_at
  FROM src_cameras c JOIN org_map m ON m.old_id = c.organization_id
  WHERE NOT EXISTS (SELECT 1 FROM cameras WHERE name = c.name);
INSERT INTO cameras (organization_id, name, angle_of_view, elevation, lat, lon, is_trustable, last_active_at, created_at) SELECT * FROM ins_cams;
CREATE TEMP TABLE cam_map AS SELECT s.id AS old_id, c.id AS new_id FROM src_cameras s JOIN cameras c USING (name);

-- Poses matched by (camera, azimuth, patrol_id); pose image not mirrored.
CREATE TEMP TABLE ins_poses AS
  SELECT m.new_id AS camera_id, p.azimuth, p.patrol_id, p.active
  FROM src_poses p JOIN cam_map m ON m.old_id = p.camera_id
  WHERE NOT EXISTS (SELECT 1 FROM poses x WHERE x.camera_id = m.new_id AND x.azimuth = p.azimuth AND x.patrol_id IS NOT DISTINCT FROM p.patrol_id);
INSERT INTO poses (camera_id, azimuth, patrol_id, active) SELECT * FROM ins_poses;

SELECT 'preprod: organization ' || o.name || ' (id ' || o.id || ')' FROM org_map m JOIN organizations o ON o.id = m.new_id
UNION ALL SELECT 'preprod: ' || count(*) || ' cameras inserted, ' || (SELECT count(*) FROM src_cameras) - count(*) || ' already there' FROM ins_cams
UNION ALL SELECT 'preprod: ' || count(*) || ' poses inserted, ' || (SELECT count(*) FROM src_poses) - count(*) || ' already there' FROM ins_poses;
COMMIT;
SQL
} | preprod_psql >&2

PREPROD_ORG_ID=$(echo "SELECT id FROM organizations WHERE name = '$ORG-preprod'" | preprod_psql)
cat <<PY | preprod_backend python - >&2
from app.services.storage import s3_service
bucket = s3_service.resolve_bucket_name(${PREPROD_ORG_ID})
if bucket in {b["Name"] for b in s3_service._s3.list_buckets()["Buckets"]}:
    print(f"s3: bucket {bucket} already there")
else:
    assert s3_service.create_bucket(bucket), f"cannot create bucket {bucket}"
    print(f"s3: bucket {bucket} created")
PY
