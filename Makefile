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

# Check if .vault_passwrd is provided
ifeq ("$(wildcard .vault_passwrd)","")
  $(error ".vault_passwrd is required but was not found.")
endif

# Copy the necessary files from the specified repository
copy-inventory:
	@echo "Copying inventory files from $(REPO_PATH)..."
	@cp $(REPO_PATH)/inventory/inventory inventory/
	@cp -r $(REPO_PATH)/inventory/host_vars inventory/
	@cp $(REPO_PATH)/inventory/all_vault inventory/group_vars/all/vault
	@cp -r $(REPO_PATH)/inventory/host_vars inventory/group_vars/engine_servers/vault

dependencies:
	@pip install ansible==10.3.0
	@pip install netaddr
	@ansible-galaxy role install -r requirements.yml
	@ansible-galaxy collection install -r requirements.yml
	cp hooks/pre-commit .git/hooks/pre-commit
	@chmod +x .git/hooks/pre-commit

ping: copy-inventory
	@ansible all -i inventory/inventory -m ping --vault-password-file=.vault_passwrd

check-engines: copy-inventory
	@./bin/pyro-ansible playbook playbooks/check-engine.yml -i inventory/inventory -l engine_servers --vault-password-file=.vault_passwrd

init-engine: copy-inventory
	@bash -c 'set -a; source init_script/.env; set +a; ./bin/pyro-ansible playbook playbooks/rpi-init.yml -i inventory/inventory -l engine_servers --vault-password-file=.vault_passwrd'

init-engine-filtered: copy-inventory
	@bash -c 'set -a; source init_script/.env; set +a; ./bin/pyro-ansible playbook playbooks/rpi-init.yml -i inventory/inventory -l $(LIMIT) --vault-password-file=.vault_passwrd'

install-engines: copy-inventory
	@bash -c 'set -a; source init_script/.env; set +a; ./bin/pyro-ansible playbook playbooks/deploy-engines.yml -i inventory/inventory -l engine_servers --vault-password-file=.vault_passwrd'

install-engines-filtered: copy-inventory
	@bash -c 'set -a; source init_script/.env; set +a; ./bin/pyro-ansible playbook playbooks/deploy-engines.yml -i inventory/inventory -l $(LIMIT) --vault-password-file=.vault_passwrd'

down: copy-inventory
	@./bin/pyro-ansible playbook playbooks/down-engines.yml -i inventory/inventory -l engine_servers --vault-password-file=.vault_passwrd

up: copy-inventory
	@./bin/pyro-ansible playbook playbooks/up-engines.yml -i inventory/inventory -l engine_servers --vault-password-file=.vault_passwrd

install-servers: copy-inventory
	@bash -c 'set -a; source init_script/.env; set +a; ./bin/pyro-ansible playbook playbooks/deploy-servers.yml -i inventory/inventory -l alert-api-test --vault-password-file=.vault_passwrd'

install-openvpn: copy-inventory
	@bash -c 'set -a; source init_script/.env; set +a; ./bin/pyro-ansible playbook playbooks/deploy-servers.yml -i inventory/inventory -l openvpn --vault-password-file=.vault_passwrd'

install-mediamtx: copy-inventory
	@./bin/pyro-ansible playbook playbooks/deploy-servers.yml -i inventory/inventory -l mediamtx --vault-password-file=.vault_passwrd

update-mediamtx-conf: copy-inventory
	@./bin/pyro-ansible playbook playbooks/update-mediamtx.yml -i inventory/inventory -l mediamtx --vault-password-file=.vault_passwrd

install-annotation-server: copy-inventory
	@./bin/pyro-ansible playbook playbooks/deploy-servers.yml -i inventory/inventory -l annotation_server --vault-password-file=.vault_passwrd

semaphore-up:
	@docker compose up -d #admin /changeme
	@docker exec -ti semaphore git config --global --add safe.directory /app/.git
	@docker exec -ti --user root semaphore cp -r /root/.ssh /home/semaphore/
	@docker exec -ti --user root semaphore chown -R semaphore /home/semaphore/.ssh

semaphore-stop:
	@docker compose stop
