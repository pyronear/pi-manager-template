# Raspberry Pi Ansible Automation

This repository contains Ansible playbooks and configuration files to manage and automate Raspberry Pi tasks. It also includes a `Makefile` for easier command execution and integration with Semaphore for a web-based UI.

## How to Use the Repository

### Pre-requisites

1) git clone the pi-manager-X repository, corresponding to the github repository containing your inventory and host_vars file. This repo is **private** — see [The pi-manager-X sister repo](#the-pi-manager-x-sister-repo) below for what it must contain.
2) create a .env file in the root of this repository (used by your Makefile) and set the REPO_PATH variable accordingly (for ex : ../pi-manager-X)
3) create the .vault_passwrd file containing your ansible vault password

Ensure the following tools are installed by using the Makefile "dependencies" command.

YOU WILL NEVER NEED TO MODIFY THIS REPOSITORY. All the modification must to be done by the pyronear team. If you want to install a new raspberry pi, you only need to modify the files in your pi-manager-X repository.

### The pi-manager-X sister repo

The sister repo holds your fleet's inventory and secrets. It is private, but its shape is fixed:

```
pi-manager-X/
├── .vault_passwrd                 # ansible-vault password, read in place via VAULT_PASSWORD_FILE (.env)
├── id_rsa                         # SSH private key, read in place via SSH_PRIVATE_KEY_FILE (.env)
├── inventory/
│   ├── hosts_prod                 # production inventory          ─┐
│   ├── hosts_dev                  # dev inventory                  │  copied into this
│   └── group_vars/                                                 │  repo by `make prepare`
│       ├── all/{vars.yml,vars.vault.yml}                           │
│       ├── alert_server/vars.yml                                   │
│       ├── annotation_server/vars.yml                              │
│       ├── engine_servers/{vars.yml,vars.vault.yml}                │
│       ├── envdev/vars.yml                                         │
│       ├── envprod/vars.yml                                        │
│       └── pi_zero/vars.yml                                        │
└── host_vars/                                                     ─┘
    ├── <engine-host>/{vars.yml,vars.vault.yml}
    ├── <pi-zero-host>/{vars.yml,vars.vault.yml}
    ├── <alert-server-host>/vars.vault.yml
    └── <annotation-server-host>/vars.vault.yml
```

`make prepare` copies `inventory/hosts*`, `host_vars/`, and `inventory/group_vars/` into this repo on every run. The vault password file and SSH key stay in the sister repo and are referenced in place through `.env`.

Worked examples for every file above ship with this repo as templates — copy them into your sister repo and edit:

- `inventory/inventory.template` — inventory groups skeleton (see `inventory/hosts_*` for fully filled-in examples).
- `group_vars/template/` — one folder per group, including `vars.vault.yml` files listing the expected vault keys.
- `host_vars/template/` — one folder per host kind (`engine`, `pi_zero`, `alert_server`, `annotation_server`).

`vars.vault.yml` files in the templates are intentionally **plain YAML with `CHANGE_ME` placeholders** so the expected keys are visible. Encrypt each one before committing it to your sister repo:

```bash
ansible-vault encrypt host_vars/<host>/vars.vault.yml
```

Two extras worth knowing about:
- The `static_ip_address` of each engine and pi_zero is referenced by name across host_vars (e.g. the pi_zero watchdog derives `MAIN_PI_IP` from `hostvars[relay_host]`), so keep the values consistent.
- After the first run of `rpi-init-pi-zero.yml`, the Pi Zero reboots onto its static IP — update `ansible_host` in its `vars.yml` to match `static_ip_address` before the next run.

### Installing a new Raspberry Pi
See [How to configure a new raspberry](./docs/howto/how-to-configure-a-new-raspberry.md)

### Commands

The following commands are available in the `Makefile`:

- **Ping all hosts**:
  Ping all hosts defined in the Ansible inventory.
  ```bash
  make ping
  ```
#### Commands on Raspberry
- **Check watchdog on local Raspberry Pi**:
  Run a playbook to check the watchdog service on the local Raspberry Pi.
  ```bash
  make check-watchdog
  ```

- **Check engine service**:
  Run a playbook to check the engine service on specific servers.
  ```bash
  make check-engine
  ```

- **Install test engine**:
  Deploy the engine on the test servers. You will need to fill the init_script/.env file
  ```bash
  make install-test-engine
  ```

- **Install prod engine**:
  Deploy the engine on the test servers. You will need to fill the init_script/.env file
  ```bash
  make install-engine-fr
  ```

#### Commands on setup environnement
- **Start Semaphore**:
  Spin up Semaphore using Docker, a web-based UI for Ansible playbook execution.
  ```bash
  make semaphore-up
  ```

- **Stop Semaphore**:
  Stop the Semaphore Docker containers.
  ```bash
  make semaphore-stop
  ```

## Using Docker
### Ansible
- Check that a file `.env` is configured with the same variables than `.env.template`
- **Start Ansible**:
  ```bash
  make ansible-up
  ```
  
- Execute ansible commands using make
Example : 
> make install-platform-react-server

### Using Semaphore

Semaphore is a UI tool to manage and run Ansible playbooks:

1. Start Semaphore using `make semaphore-up`.
2. Access the UI at `http://localhost:3000` (default credentials: `admin / changeme`).
3. Manage playbooks, tasks, and inventory directly from the web interface.

## Ansible Directory Structure

This repository follows a typical Ansible directory structure:

- **playbooks/**: Contains playbooks that perform specific tasks (e.g., engine deployment, watchdog checks).
- **roles/**: Custom roles (if needed) to be reused across playbooks.
- **host_vars/**: Directory containing per-host variables and vault files (sensitive information).
- **files/**: Contains files (e.g., OpenVPN client configurations) that need to be deployed on the hosts.

Ensure all sensitive data is encrypted using Ansible Vault before pushing it to the repository.
