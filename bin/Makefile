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

ifeq ($(wildcard $(VAULT_PASSWORD_FILE)),)
  $(error "$(VAULT_PASSWORD_FILE) is required but was not found.")
endif

confirm:
	@echo "⚠️  Attention : vous allez lancer une commande sur \033[1;33m$(REPO_PATH)\033[0m"
	@read -p "Êtes-vous sûr ? Appuyez sur Entrée pour continuer, Ctrl+C pour annuler..." dummy

dependencies:
	@pip install ansible==10.3.0
	@pip install netaddr
	@ansible-galaxy role install -r requirements.yml
	@ansible-galaxy collection install -r requirements.yml
	cp hooks/pre-commit .git/hooks/pre-commit
	@chmod +x .git/hooks/pre-commit

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
	@SECOND_REPO=$(REPO_PATH) ./bin/pyro-ansible playbook playbooks/deploy-servers.yml -i inventory/hosts_prod -l platform_react_server --vault-password-file=$(VAULT_PASSWORD_FILE)

