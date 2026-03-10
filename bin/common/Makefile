
semaphore-up:
	@docker compose up -d #admin /changeme
	@docker exec -ti semaphore git config --global --add safe.directory /app/.git
	@docker exec -ti --user root semaphore cp -r /root/.ssh /home/semaphore/
	@docker exec -ti --user root semaphore chown -R semaphore /home/semaphore/.ssh

semaphore-stop:
	@docker compose stop

ansible-up:
	@docker compose up -d pyro-ansible
	@docker exec -it pyro-ansible sh

ansible-stop:
	@docker compose down pyro-ansible

ping: prepare
	@ansible all -i inventory/hosts_prod -m ping --vault-password-file=$(VAULT_PASSWORD_FILE)

check-engines: prepare
	@SECOND_REPO=$(REPO_PATH) ./bin/pyro-ansible playbook playbooks/check-engine.yml -i inventory/hosts_prod -l engine_servers --vault-password-file=$(VAULT_PASSWORD_FILE)

init-engine: prepare
	@bash -c 'set -a; source init_script/.env; set +a;SECOND_REPO=$(REPO_PATH) ./bin/pyro-ansible playbook playbooks/rpi-init.yml -i inventory/hosts_prod -l engine_servers --vault-password-file=$(VAULT_PASSWORD_FILE)'

init-engine-filtered: prepare
	@bash -c 'set -a; source init_script/.env; set +a;SECOND_REPO=$(REPO_PATH) ./bin/pyro-ansible playbook playbooks/rpi-init.yml -i inventory/hosts_prod -l $(LIMIT) --vault-password-file=$(VAULT_PASSWORD_FILE)'

install-engines: prepare
	@bash -c 'set -a; source init_script/.env; set +a;SECOND_REPO=$(REPO_PATH) ./bin/pyro-ansible playbook playbooks/deploy-engines.yml -i inventory/hosts_prod -l engine_servers --vault-password-file=$(VAULT_PASSWORD_FILE)'

install-engines-filtered: prepare
	@bash -c 'set -a; source init_script/.env; set +a;SECOND_REPO=$(REPO_PATH) ./bin/pyro-ansible playbook playbooks/deploy-engines.yml -i inventory/hosts_prod -l $(LIMIT) --vault-password-file=$(VAULT_PASSWORD_FILE)'

down: prepare
	@SECOND_REPO=$(REPO_PATH) ./bin/pyro-ansible playbook playbooks/down-engines.yml -i inventory/hosts_prod -l engine_servers --vault-password-file=$(VAULT_PASSWORD_FILE)

up: prepare
	@SECOND_REPO=$(REPO_PATH) ./bin/pyro-ansible playbook playbooks/up-engines.yml -i inventory/hosts_prod -l engine_servers --vault-password-file=$(VAULT_PASSWORD_FILE)

install-servers: prepare
	@bash -c 'set -a; source init_script/.env; set +a;SECOND_REPO=$(REPO_PATH) ./bin/pyro-ansible playbook playbooks/deploy-servers.yml -i inventory/hosts_prod -l $(LIMIT) --vault-password-file=$(VAULT_PASSWORD_FILE)'

install-openvpn: prepare
	@bash -c 'set -a; source init_script/.env; set +a;SECOND_REPO=$(REPO_PATH) ./bin/pyro-ansible playbook playbooks/deploy-servers.yml -i inventory/hosts_prod -l openvpn --vault-password-file=$(VAULT_PASSWORD_FILE)'

install-mediamtx: prepare
	@SECOND_REPO=$(REPO_PATH) ./bin/pyro-ansible playbook playbooks/deploy-servers.yml -i inventory/hosts_prod -l mediamtx_server --vault-password-file=$(VAULT_PASSWORD_FILE)

update-mediamtx-conf: prepare
	@SECOND_REPO=$(REPO_PATH) ./bin/pyro-ansible playbook playbooks/update-mediamtx.yml -i inventory/hosts_prod -l mediamtx_server --vault-password-file=$(VAULT_PASSWORD_FILE)

install-annotation-server: prepare
	@SECOND_REPO=$(REPO_PATH) ./bin/pyro-ansible playbook playbooks/deploy-servers.yml -i inventory/hosts_prod -l annotation_server --vault-password-file=$(VAULT_PASSWORD_FILE)

install-platform-react-server: prepare
	ansible-playbook playbooks/deploy-servers.yml -i inventory/hosts_prod -l platform_react_server

