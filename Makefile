ifneq ("$(wildcard .env)","")
  include .env
  export
else
  $(error ".env file not found.")
endif

# Check if REPO_PATH is provided
ifeq ($(REPO_PATH),)
  $(error "Repository path is required. Please provide the path to the other repository.")
endif

VAULT_PASSWORD_FILE := $(REPO_PATH)/.vault_passwrd

ifeq ($(wildcard $(VAULT_PASSWORD_FILE)),)
  $(error "$(VAULT_PASSWORD_FILE) is required but was not found.")
endif

# Copy the necessary files from the specified repository
copy-inventory:
	@echo "Copying inventory files from $(REPO_PATH)..."
	@cp $(REPO_PATH)/inventory/inventory inventory/
	@cp -r $(REPO_PATH)/inventory/host_vars inventory/
	@cp $(REPO_PATH)/inventory/all_vault inventory/group_vars/all/vault
	@cp -r $(REPO_PATH)/inventory/engine_vault inventory/group_vars/engine_servers/vault

dependencies:
	@pip install ansible==10.3.0
	@pip install netaddr
	@ansible-galaxy role install -r requirements.yml
	@ansible-galaxy collection install -r requirements.yml
	cp hooks/pre-commit .git/hooks/pre-commit
	@chmod +x .git/hooks/pre-commit

ping: copy-inventory
	@ansible all -i inventory/inventory -m ping --vault-password-file=$(VAULT_PASSWORD_FILE)

check-engines: copy-inventory
	@SECOND_REPO=$(REPO_PATH) ./bin/pyro-ansible playbook playbooks/check-engine.yml -i inventory/inventory -l engine_servers --vault-password-file=$(VAULT_PASSWORD_FILE)

init-engine: copy-inventory
	@bash -c 'set -a; source init_script/.env; set +a;SECOND_REPO=$(REPO_PATH) ./bin/pyro-ansible playbook playbooks/rpi-init.yml -i inventory/inventory -l engine_servers --vault-password-file=$(VAULT_PASSWORD_FILE)'

init-engine-filtered: copy-inventory
	@bash -c 'set -a; source init_script/.env; set +a;SECOND_REPO=$(REPO_PATH) ./bin/pyro-ansible playbook playbooks/rpi-init.yml -i inventory/inventory -l $(LIMIT) --vault-password-file=$(VAULT_PASSWORD_FILE)'

install-engines: copy-inventory
	@bash -c 'set -a; source init_script/.env; set +a;SECOND_REPO=$(REPO_PATH) ./bin/pyro-ansible playbook playbooks/deploy-engines.yml -i inventory/inventory -l engine_servers --vault-password-file=$(VAULT_PASSWORD_FILE)'

install-engines-filtered: copy-inventory
	@bash -c 'set -a; source init_script/.env; set +a;SECOND_REPO=$(REPO_PATH) ./bin/pyro-ansible playbook playbooks/deploy-engines.yml -i inventory/inventory -l $(LIMIT) --vault-password-file=$(VAULT_PASSWORD_FILE)'

down: copy-inventory
	@SECOND_REPO=$(REPO_PATH) ./bin/pyro-ansible playbook playbooks/down-engines.yml -i inventory/inventory -l engine_servers --vault-password-file=$(VAULT_PASSWORD_FILE)

up: copy-inventory
	@SECOND_REPO=$(REPO_PATH) ./bin/pyro-ansible playbook playbooks/up-engines.yml -i inventory/inventory -l engine_servers --vault-password-file=$(VAULT_PASSWORD_FILE)

install-servers: copy-inventory
	@bash -c 'set -a; source init_script/.env; set +a;SECOND_REPO=$(REPO_PATH) ./bin/pyro-ansible playbook playbooks/deploy-servers.yml -i inventory/inventory -l alert-api-test --vault-password-file=$(VAULT_PASSWORD_FILE)'

install-openvpn: copy-inventory
	@bash -c 'set -a; source init_script/.env; set +a;SECOND_REPO=$(REPO_PATH) ./bin/pyro-ansible playbook playbooks/deploy-servers.yml -i inventory/inventory -l openvpn --vault-password-file=$(VAULT_PASSWORD_FILE)'

install-mediamtx: copy-inventory
	@SECOND_REPO=$(REPO_PATH) ./bin/pyro-ansible playbook playbooks/deploy-servers.yml -i inventory/inventory -l mediamtx --vault-password-file=$(VAULT_PASSWORD_FILE)

update-mediamtx-conf: copy-inventory
	@SECOND_REPO=$(REPO_PATH) ./bin/pyro-ansible playbook playbooks/update-mediamtx.yml -i inventory/inventory -l mediamtx --vault-password-file=$(VAULT_PASSWORD_FILE)

install-annotation-server: copy-inventory
	@SECOND_REPO=$(REPO_PATH) ./bin/pyro-ansible playbook playbooks/deploy-servers.yml -i inventory/inventory -l annotation_server --vault-password-file=$(VAULT_PASSWORD_FILE)

semaphore-up:
	@docker compose up -d #admin /changeme
	@docker exec -ti semaphore git config --global --add safe.directory /app/.git
	@docker exec -ti --user root semaphore cp -r /root/.ssh /home/semaphore/
	@docker exec -ti --user root semaphore chown -R semaphore /home/semaphore/.ssh

semaphore-stop:
	@docker compose stop
