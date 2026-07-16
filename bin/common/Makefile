
.PHONY: require-container help ansible-up ansible-stop ping check-engines \
	init-one-engine deploy-one-engine deploy-all-engines down up \
	install-openvpn install-mediamtx update-mediamtx-conf update-reverse-ssh install-annotation-server \
	install-platform-react-server install-alert-api-server install-alert-api-preprod-server install-temporal-server \
	install-combined-server init-pi-zero sync-ssh-keys

# Operational targets must run inside the pyro-ansible container, where the
# sister repo's inventory/host_vars/group_vars are mounted. The Dockerfile sets
# IN_PYRO_ANSIBLE_CONTAINER=1; on the host this guard fails fast instead of
# running ansible against an empty or stale inventory.
require-container:
	@if [ -z "$$IN_PYRO_ANSIBLE_CONTAINER" ]; then \
		echo "This target must run inside the pyro-ansible container."; \
		echo "Run 'make ansible-up' first, then re-run it from the container shell."; \
		exit 1; \
	fi

help:
	@echo "Host targets:"
	@echo "  make ansible-up      build the image and open a shell in the container"
	@echo "  make ansible-stop    stop the container"
	@echo "  make dependencies    install host-side ansible + pre-commit hook"
	@echo ""
	@echo "Container targets (run after 'make ansible-up'):"
	@echo "  make ping / check-engines / up / down / sync-ssh-keys"
	@echo "  make deploy-all-engines | deploy-one-engine SITE=<host>"
	@echo "  make init-one-engine SITE=<host> | init-pi-zero SITE=<host>"
	@echo "  make install-openvpn | install-mediamtx | update-mediamtx-conf"
	@echo "  make install-annotation-server | install-platform-react-server"
	@echo "  make install-alert-api-server | install-temporal-server"
	@echo "  make install-combined-server   (traefik + mediamtx + platform + alert API on one VM)"
	@echo "  make update-combined-api | update-combined-platform | update-combined-mediamtx | update-combined-traefik"
	@echo "                                 (redeploy a single service on the combined server)"

ansible-up:
	@if [ -n "$$(git status --porcelain)" ]; then \
		echo "⚠️  Uncommitted changes in this repo will be deployed (playbooks/roles are bind-mounted)."; \
	fi
	@if [ -n "$(REPO_PATH)" ] && [ -n "$$(git -C $(REPO_PATH) status --porcelain 2>/dev/null)" ]; then \
		echo "⚠️  Uncommitted changes in $(REPO_PATH) will be deployed (inventory/host_vars are bind-mounted)."; \
	fi
	@docker compose up -d --build pyro-ansible
	@docker exec -it pyro-ansible sh

ansible-stop:
	@docker compose down pyro-ansible

ping: require-container
	@ansible all -i inventory/hosts_prod -m ping

check-engines: require-container
	ansible-playbook playbooks/check-engine.yml -i inventory/hosts_prod -l engine_servers

init-one-engine: require-container
	ansible-playbook playbooks/rpi-init.yml -i inventory/hosts_prod -l $(SITE),mediamtx_server

deploy-one-engine: require-container
	ansible-playbook playbooks/deploy-engines.yml -i inventory/hosts_prod -l $(SITE)

deploy-all-engines: require-container
	ansible-playbook playbooks/deploy-engines.yml -i inventory/hosts_prod -l engine_servers

down: require-container
	ansible-playbook playbooks/down-engines.yml -i inventory/hosts_prod -l engine_servers

up: require-container
	ansible-playbook playbooks/up-engines.yml -i inventory/hosts_prod -l engine_servers

install-openvpn: require-container
	@bash -c 'set -a; source init_script/.env || exit 1; set +a; ansible-playbook playbooks/deploy-servers.yml -i inventory/hosts_prod -l openvpn'

install-mediamtx: require-container
	ansible-playbook playbooks/deploy-servers.yml -i inventory/hosts_prod -l mediamtx_server

update-mediamtx-conf: require-container
	ansible-playbook playbooks/update-mediamtx.yml -i inventory/hosts_prod -l mediamtx_server

update-reverse-ssh: require-container
	ansible-playbook playbooks/update-reverse-ssh.yml -i inventory/hosts_prod -l $(or $(LIMIT_HOSTS),engine_servers)

install-annotation-server: require-container
	ansible-playbook playbooks/deploy-servers.yml -i inventory/hosts_prod -l annotation_server

install-platform-react-server: require-container
	ansible-playbook playbooks/deploy-servers.yml -i inventory/hosts_prod -l platform_react_server

install-alert-api-server: require-container
	ansible-playbook playbooks/deploy-servers.yml -i inventory/hosts_prod -l alert_server

install-alert-api-preprod-server: require-container
	ansible-playbook playbooks/deploy-servers.yml -i inventory/hosts_prod -l alert_server_preprod

install-temporal-server: require-container
	ansible-playbook playbooks/deploy-servers.yml -i inventory/hosts_prod -l temporal_server

install-combined-server: require-container
	ansible-playbook playbooks/deploy-combined.yml -i inventory/hosts_prod -l combined_server

update-combined-api: require-container
	ansible-playbook playbooks/deploy-combined.yml -i inventory/hosts_prod -l combined_server --tags alert_api

update-combined-platform: require-container
	ansible-playbook playbooks/deploy-combined.yml -i inventory/hosts_prod -l combined_server --tags platform

update-combined-mediamtx: require-container
	ansible-playbook playbooks/deploy-combined.yml -i inventory/hosts_prod -l combined_server --tags mediamtx

update-combined-traefik: require-container
	ansible-playbook playbooks/deploy-combined.yml -i inventory/hosts_prod -l combined_server --tags traefik

init-pi-zero: require-container
	ansible-playbook playbooks/rpi-init-pi-zero.yml -i inventory/hosts_prod -l $(SITE)

sync-ssh-keys: require-container
	ansible-playbook playbooks/sync-ssh-keys.yml -i inventory/hosts_prod
