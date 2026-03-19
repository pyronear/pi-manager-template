# Raspberry Pi Ansible Automation

This repository contains Ansible playbooks and configuration files to manage and automate Raspberry Pi tasks. It also includes a `Makefile` for easier command execution and integration with Semaphore for a web-based UI.

## How to Use the Repository

### Pre-requisites

1) git clone the pi-manager-X repository, corresponding to the github repository containing your inventory and host_vars file.
2) create a .env file in the root of this repository (used by your Makefile) and set the REPO_PATH variable accordingly (for ex : ../pi-manager-X)
3) create the .vault_passwrd file containing your ansible vault password

Ensure the following tools are installed by using the Makefile "dependencies" command.

YOU WILL NEVER NEED TO MODIFY THIS REPOSITORY. All the modification must to be done by the pyronear team. If you want to install a new raspberry pi, you only need to modify the files in your pi-manager-X repository.

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
