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

# Bare `make` should print help, not silently run dependencies.
.DEFAULT_GOAL := help

dependencies:
	@pip install ansible==10.3.0
	@pip install netaddr
	@ansible-galaxy role install -r requirements.yml
	@ansible-galaxy collection install -r requirements.yml
	cp hooks/pre-commit .git/hooks/pre-commit
	@chmod +x .git/hooks/pre-commit

include ./bin/common/Makefile