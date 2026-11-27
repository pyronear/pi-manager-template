#!/usr/bin/env bash
# Back up Twenty (Postgres dump + local file storage) into one gpg-encrypted
# archive and upload it to S3. Settings come from $TWENTY_DIR/backup.env.
# Also runnable on any machine with the same compose project (e.g. to seed the
# bucket from another instance): TWENTY_DIR=/path/to/compose/dir twenty-backup.sh
set -euo pipefail

TWENTY_DIR=${TWENTY_DIR:-/home/twenty}
# shellcheck source=/dev/null
source "$TWENTY_DIR/backup.env"
cd "$TWENTY_DIR"

stamp=$(date -u +%Y%m%dT%H%M%SZ)
name="twenty-$stamp.tar.gpg"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

# pg_dump runs in one transaction: the dump is consistent while Twenty keeps running
docker compose exec -T db pg_dump -U postgres -d default --clean --if-exists | gzip > "$tmp/db.sql.gz"
docker run --rm -v twenty_server-local-data:/data:ro alpine:3.20 tar czf - -C /data . > "$tmp/storage.tar.gz"

tar cf - -C "$tmp" db.sql.gz storage.tar.gz |
  gpg --batch --yes --pinentry-mode loopback --passphrase-fd 3 \
    --symmetric --cipher-algo AES256 -o "$tmp/$name" 3<<<"$BACKUP_PASSPHRASE"

docker run --rm -v "$tmp:/backup:ro" \
  -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY \
  amazon/aws-cli --endpoint-url "$S3_ENDPOINT_URL" --region "$S3_REGION" \
  s3 cp "/backup/$name" "s3://$S3_BUCKET/$name"

echo "uploaded s3://$S3_BUCKET/$name"
