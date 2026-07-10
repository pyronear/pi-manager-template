# Raspberry Pi Ansible Automation

Ansible playbooks and roles to manage the Pyronear Raspberry Pi fleet (wildfire
detection engines) and the backing servers (alert API, platform, mediamtx,
openvpn, annotation, temporal).

This repository is a **template**: it holds the playbooks, roles and tooling but
**no inventory and no secrets**. The inventory, `host_vars/`, `group_vars/` and
the vault password live in a sister repo (`pi-manager-X`), glued in through
`REPO_PATH`. You should not need to modify this repository to onboard a new site
— per-site work happens in the sister repo.

## Pyronear services

The services this repo deploys, and where their code lives:

| Service | What it does | Repo |
|---|---|---|
| **Engine** | Runs on each Raspberry Pi. Analyzes the camera streams, detects smoke and pushes alerts to the alert API. Ships with `pyro-camera-api`, a local API to control the cameras. | [pyro-engine](https://github.com/pyronear/pyro-engine) |
| **Alert API** | Central FastAPI + PostgreSQL service. Stores organizations, cameras, detections and alerts; engines authenticate against it to post detections. | [pyro-api](https://github.com/pyronear/pyro-api) |
| **Platform** | React web app used to monitor and acknowledge alerts (docker image `pyronear/pyro-platform-react`). | [new-pyro-platform](https://github.com/pyronear/new-pyro-platform) |
| **MediaMTX** | Media server relaying the live camera streams; each engine registers a stream path so streams are viewable from the platform. | [bluenviron/mediamtx](https://github.com/bluenviron/mediamtx) (config managed here) |
| **OpenVPN** | VPN server; every engine and API server gets a client, so the whole fleet is reachable remotely over the VPN. | [ansible-role-openvpn](https://github.com/pyronear/ansible-role-openvpn) |
| **Traefik** | Reverse proxy and TLS termination in front of the services on the combined server. | role in this repo |
| **Reverse SSH** | Fallback access: each engine keeps an SSH tunnel open to a bastion server, used when the VPN is down. | role in this repo |

### Secondary services

| Service | What it does | Repo |
|---|---|---|
| **Temporal API** | Serves the temporal smoke-detection model (docker image `pyronear/temporal-model-api`), used to confirm detections over time. | [temporal-model](https://github.com/pyronear/temporal-model) |
| **Annotation** | Annotation API + web app to label detection sequences and build training datasets. | [pyro-annotator](https://github.com/pyronear/pyro-annotator) |

## How it works

Ansible runs **inside a Docker container** (`pyro-ansible`). The sister repo's
inventory, `host_vars` and `group_vars` are bind-mounted straight into the
container (see `docker-compose.yml`), so there is no copy step to run.

## Setup

1. Clone the sister `pi-manager-X` repo next to this one.
2. Create a `.env` at the repo root from `.env.template` and set `REPO_PATH`,
   `VAULT_PASSWORD_FILE` and `SSH_PRIVATE_KEY_FILE` (see `.env.template`).
3. To seed the API database for a new site, fill `init_script/.env`
   (copy `init_script/.env.ex`).

## Usage

Build the image and drop into a shell inside the container:

```bash
make ansible-up
```

From that shell, run any target below. The operational targets only work inside
the container; running them on the host fails fast with a reminder. When you're
done, exit the shell and stop the container from the host with `make ansible-stop`.

### Fleet / engine targets

```bash
make ping                          # ping all hosts in inventory/hosts_prod
make check-engines                 # verify engine containers are running + healthy
make deploy-all-engines            # deploy-engines.yml on every engine
make deploy-one-engine SITE=<host> # deploy-engines.yml on a single host
make init-one-engine  SITE=<host>  # rpi-init.yml on a single host (+ mediamtx)
make init-pi-zero     SITE=<host>  # rpi-init-pi-zero.yml on a single Pi Zero
make up / make down                # start / stop engine docker-compose stacks fleet-wide
make sync-ssh-keys                 # push authorized SSH keys to all hosts
```

What the main targets actually do:

- **`init-one-engine`** — one-time OS setup of a new Pi: hostname, wifi,
  docker, OpenVPN client, reverse SSH tunnel, Grafana Alloy monitoring and
  static IP. Also registers the site's stream path on the mediamtx server.
- **`deploy-one-engine` / `deploy-all-engines`** — (re)deploys the engine
  application: pulls the `pyro-engine` and `pyro-camera-api` images, fetches a
  fresh API token per camera, writes `credentials.json` and `.env`, then
  restarts the docker-compose stack. Also installs the daily-reboot and
  watchdog cron jobs. Run it again to ship an engine update.
- **`check-engines`** — verifies the engine containers are up and healthy on
  every engine; use it after a deploy or when a site looks silent.
- **`init-pi-zero`** — sets up a Pi Zero (wifi, static IP, watchdog scripts).
  Engines and Pi Zeros watchdog each other through power relays — see
  [watchdog-setup](./docs/howto/watchdog-setup.md).

#### Typical workflow for a new Pi

1. Seed the API database from `init_script/` (`create_orga.py`,
   `create_user.py`, `create_cameras.py`) and write the returned IDs into the
   site's `host_vars` in the sister repo (`site_config/app.py` can generate it).
2. `make init-one-engine SITE=<host>` — base system, VPN, static IP.
3. `make deploy-one-engine SITE=<host>` — deploy the detection stack.
4. `make check-engines` — confirm the containers are running and healthy.

The full walkthrough lives in
[How to configure a new raspberry](./docs/howto/how-to-configure-a-new-raspberry.md).

### Server targets

```bash
make install-openvpn                 # deploy-servers.yml -l openvpn
make install-mediamtx                # deploy-servers.yml -l mediamtx_server
make update-mediamtx-conf            # refresh mediamtx streams config only
make install-annotation-server
make install-platform-react-server
make install-alert-api-server
make install-temporal-server
make install-combined-server         # deploy-combined.yml: traefik + mediamtx + platform + alert API on one VM
```

`install-openvpn` sources `init_script/.env` before running.

To redeploy a single service on the combined server (e.g. ship an API update)
without touching the others:

```bash
make update-combined-api             # alert API only
make update-combined-platform        # platform only
make update-combined-mediamtx        # mediamtx only
make update-combined-traefik         # traefik only
```

## Adding a new Raspberry Pi

See [How to configure a new raspberry](./docs/howto/how-to-configure-a-new-raspberry.md).

## Directory structure

- **playbooks/** — playbooks per task (engine deploy, server deploy, checks).
- **roles/** — custom and vendored roles.
- **init_script/** — Python helpers to seed the API DB before onboarding a site.
- **docker/** — Dockerfile, entrypoint and container-side `ansible.cfg`/`Makefile`.

Sensitive data is stored vault-encrypted in the sister repo.
