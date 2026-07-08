# Raspberry Pi Ansible Automation

Ansible playbooks and roles to manage the Pyronear Raspberry Pi fleet (wildfire
detection engines) and the backing servers (alert API, platform, mediamtx,
openvpn, annotation, temporal).

This repository is a **template**: it holds the playbooks, roles and tooling but
**no inventory and no secrets**. The inventory, `host_vars/`, `group_vars/` and
the vault password live in a sister repo (`pi-manager-X`), glued in through
`REPO_PATH`. You should not need to modify this repository to onboard a new site
— per-site work happens in the sister repo.

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

### Server targets

```bash
make install-openvpn                 # deploy-servers.yml -l openvpn
make install-mediamtx                # deploy-servers.yml -l mediamtx_server
make update-mediamtx-conf            # refresh mediamtx streams config only
make install-annotation-server
make install-platform-react-server
make install-alert-api-server
make install-temporal-server
```

`install-openvpn` sources `init_script/.env` before running.

## Adding a new Raspberry Pi

See [How to configure a new raspberry](./docs/howto/how-to-configure-a-new-raspberry.md).

## Directory structure

- **playbooks/** — playbooks per task (engine deploy, server deploy, checks).
- **roles/** — custom and vendored roles.
- **init_script/** — Python helpers to seed the API DB before onboarding a site.
- **docker/** — Dockerfile, entrypoint and container-side `ansible.cfg`/`Makefile`.

Sensitive data is stored vault-encrypted in the sister repo.
