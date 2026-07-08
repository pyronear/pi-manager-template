
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
	@echo "  make install-servers | install-openvpn | install-mediamtx | update-mediamtx-conf"
	@echo "  make install-annotation-server | install-platform-react-server"
	@echo "  make install-alert-api-server | install-temporal-server"

ansible-up:
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

install-servers: require-container
	@bash -c 'set -a; source init_script/.env || exit 1; set +a; ansible-playbook playbooks/deploy-servers.yml -i inventory/hosts_prod -l $(LIMIT)'

install-openvpn: require-container
	@bash -c 'set -a; source init_script/.env || exit 1; set +a; ansible-playbook playbooks/deploy-servers.yml -i inventory/hosts_prod -l openvpn'

install-mediamtx: require-container
	ansible-playbook playbooks/deploy-servers.yml -i inventory/hosts_prod -l mediamtx_server

update-mediamtx-conf: require-container
	ansible-playbook playbooks/update-mediamtx.yml -i inventory/hosts_prod -l mediamtx_server

install-annotation-server: require-container
	ansible-playbook playbooks/deploy-servers.yml -i inventory/hosts_prod -l annotation_server

install-platform-react-server: require-container
	ansible-playbook playbooks/deploy-servers.yml -i inventory/hosts_prod -l platform_react_server

install-alert-api-server: require-container
	ansible-playbook playbooks/deploy-servers.yml -i inventory/hosts_prod -l alert_server

install-temporal-server: require-container
	ansible-playbook playbooks/deploy-servers.yml -i inventory/hosts_prod -l temporal_server

init-pi-zero: require-container
	ansible-playbook playbooks/rpi-init-pi-zero.yml -i inventory/hosts_prod -l $(SITE)

sync-ssh-keys: require-container
	ansible-playbook playbooks/sync-ssh-keys.yml -i inventory/hosts_prod
