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

# Copy the necessary files from the specified repository
prepare: confirm
	@echo "Copying inventory files from $(REPO_PATH)..."
	@cp -r $(REPO_PATH)/inventory/hosts* ./inventory
	@cp -r $(REPO_PATH)/host_vars .
	@cp -r $(REPO_PATH)/inventory/group_vars/ ./group_vars

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

include ./bin/common/Makefile