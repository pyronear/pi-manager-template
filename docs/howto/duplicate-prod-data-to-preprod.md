# Duplicate prod alert data to preprod

Two scripts copy real data from the prod alert API to the preprod one, so preprod can be
looked at with concrete examples. They work at the database level (not through the API):
an API replay would regroup every detection into new sequences at `now()` and lose the
original timestamps, labels, scores and validation status.

Both run from your laptop over ssh. SQL runs inside the `db` containers of the alert API
stacks, the S3 copy inside the preprod `backend` container (it holds the S3 credentials).
Nothing sensitive is downloaded: the CSV exports only hold table rows, in a temp dir removed
at the end.

Requirements: the `pi-manager-fr` ssh key (`../pi-manager-fr/id_rsa`, or `SSH_PRIVATE_KEY_FILE`),
and sudo access on both servers (`ubuntu` is not in the docker group).

## `bin/duplicate_org.sh <org>`

```bash
bin/duplicate_org.sh sdis-67
```

Creates the organization `sdis-67-preprod` on preprod with:

- the organization row, **without** `telegram_id` / `slack_hook` so preprod never notifies
  the prod channels;
- its cameras, same names (no `last_image`, no IPs);
- their poses, matched by camera + azimuth + `patrol_id` (no pose image);
- the organization's S3 bucket (the API only creates it on `POST /organizations`).

Re-runnable: rows already present are skipped. No user is created: use
`init_script/create_user.py` against `https://alertapipreprod.pyronear.org` with
`organization_name=sdis-67-preprod` to get a login on the platform.

## `bin/duplicate_data.sh <org> <from> <to>`

```bash
bin/duplicate_data.sh sdis-67 2026-09-01 2026-09-07
```

Runs `duplicate_org.sh` first, then copies, for UTC calendar days `from` to `to` inclusive:

- sequences started in the window, with their labels, scores and validation status
  (`validation_due_at` stays NULL so the preprod worker does not re-validate or notify);
- their detections, plus unsequenced detections created in the window;
- the alerts those sequences belong to, and the alert/sequence links;
- the frames and crops on S3, same keys, prod bucket to preprod bucket.

Re-runnable: existing sequences (camera, `started_at`, azimuth), detections (camera, key,
bbox) and alerts (org, `started_at`, lat, lon) are skipped. Running another window later
only adds the new sequences and attaches them to alerts already copied. The script exits
non-zero if any S3 object could not be copied; the database rows are committed by then, so
just run it again.

## Testing locally

Against a local [pyro-api](https://github.com/pyronear/pyro-api) stack, with a second
database `src` in the same postgres acting as prod and a fake prod bucket on localstack:

```bash
PROD_HOST=local PREPROD_HOST=local COMPOSE_PROJECT=pyronear PROD_DB=src \
PROD_SERVER_NAME=fakeprod DOCKER=docker bin/duplicate_data.sh sdis-67 2026-09-07 2026-09-08
```

The local backend must run with a non-empty `SERVER_NAME`, it names the preprod bucket.
