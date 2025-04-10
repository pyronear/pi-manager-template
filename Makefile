# Prompt for the path to the other repository
REPO_PATH = "../test_update_pi"

# Check if REPO_PATH is provided
ifeq ($(REPO_PATH),)
  $(error "Repository path is required. Please provide the path to the other repository.")
endif

# Copy the necessary files from the specified repository
copy-inventory:
	@echo "Copying inventory files from $(REPO_PATH)..."
	@cp $(REPO_PATH)/inventory/inventory inventory/
	@cp -r $(REPO_PATH)/inventory/host_vars inventory/

dependencies:
	@pip install ansible==10.3.0
	@pip install netaddr
	@ansible-galaxy role install -r requirements.yml
	@ansible-galaxy collection install -r requirements.yml
	cp hooks/pre-commit .git/hooks/pre-commit
	@chmod +x .git/hooks/pre-commit

ping: copy-inventory
	@ansible all -i inventory/inventory -m ping --vault-password-file=.vault_passwrd

check-watchdog: copy-inventory
	@ansible-playbook -i inventory/inventory playbooks/check-watchdog.yml --vault-password-file=.vault_passwrd -l engine_servers

check-engine: copy-inventory
	@ansible-playbook -i inventory/inventory playbooks/check-engine.yml --vault-password-file=.vault_passwrd -l engine_servers

install-engine: copy-inventory
	@bash -c 'set -a; source init_script/.env; set +a; ansible-playbook -i inventory/inventory playbooks/deploy-engines.yml -l mateo_local --vault-password-file=.vault_passwrd'

semaphore-up:
	@docker compose up -d #admin /changeme
	@docker exec -ti semaphore git config --global --add safe.directory /app/.git
	@docker exec -ti --user root semaphore cp -r /root/.ssh /home/semaphore/
	@docker exec -ti --user root semaphore chown -R semaphore /home/semaphore/.ssh

semaphore-stop:
	@docker compose stop
