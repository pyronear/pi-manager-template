
semaphore-up:
	@docker compose up -d #admin /changeme
	@docker exec -ti semaphore git config --global --add safe.directory /app/.git
	@docker exec -ti --user root semaphore cp -r /root/.ssh /home/semaphore/
	@docker exec -ti --user root semaphore chown -R semaphore /home/semaphore/.ssh

semaphore-stop:
	@docker compose stop

ansible-up:
	@docker compose up -d --build pyro-ansible
	@docker exec -it pyro-ansible sh

ansible-stop:
	@docker compose down pyro-ansible

ping: prepare
	@ansible all -i inventory/hosts_prod -m ping

check-engines: prepare
	@SECOND_REPO=$(REPO_PATH) ./bin/pyro-ansible playbook playbooks/check-engine.yml -i inventory/hosts_prod -l engine_servers

init-engine: prepare
	@bash -c 'set -a; source init_script/.env; set +a;SECOND_REPO=$(REPO_PATH) ./bin/pyro-ansible playbook playbooks/rpi-init.yml -i inventory/hosts_prod -l engine_servers'

init-engine-filtered: prepare
	@bash -c 'set -a; source init_script/.env; set +a;SECOND_REPO=$(REPO_PATH) ./bin/pyro-ansible playbook playbooks/rpi-init.yml -i inventory/hosts_prod -l $(LIMIT)'

install-engines: prepare
	@bash -c 'set -a; source init_script/.env; set +a;SECOND_REPO=$(REPO_PATH) ./bin/pyro-ansible playbook playbooks/deploy-engines.yml -i inventory/hosts_prod -l engine_servers'

install-engines-filtered: prepare
	@bash -c 'set -a; source init_script/.env; set +a;SECOND_REPO=$(REPO_PATH) ./bin/pyro-ansible playbook playbooks/deploy-engines.yml -i inventory/hosts_prod -l $(LIMIT)'

init-one-engine:
	ansible-playbook playbooks/rpi-init.yml -i inventory/hosts_prod -l $(SITE),mediamtx_server

deploy-one-engine:
	ansible-playbook playbooks/deploy-engines.yml -i inventory/hosts_prod -l $(SITE)

down: prepare
	@SECOND_REPO=$(REPO_PATH) ./bin/pyro-ansible playbook playbooks/down-engines.yml -i inventory/hosts_prod -l engine_servers

up: prepare
	@SECOND_REPO=$(REPO_PATH) ./bin/pyro-ansible playbook playbooks/up-engines.yml -i inventory/hosts_prod -l engine_servers

install-servers: prepare
	@bash -c 'set -a; source init_script/.env; set +a;SECOND_REPO=$(REPO_PATH) ./bin/pyro-ansible playbook playbooks/deploy-servers.yml -i inventory/hosts_prod -l $(LIMIT)'

install-openvpn: prepare
	@bash -c 'set -a; source init_script/.env; set +a;SECOND_REPO=$(REPO_PATH) ./bin/pyro-ansible playbook playbooks/deploy-servers.yml -i inventory/hosts_prod -l openvpn'

install-mediamtx: prepare
	@SECOND_REPO=$(REPO_PATH) ./bin/pyro-ansible playbook playbooks/deploy-servers.yml -i inventory/hosts_prod -l mediamtx_server

update-mediamtx-conf: prepare
	@SECOND_REPO=$(REPO_PATH) ./bin/pyro-ansible playbook playbooks/update-mediamtx.yml -i inventory/hosts_prod -l mediamtx_server

install-annotation-server: prepare
	@SECOND_REPO=$(REPO_PATH) ./bin/pyro-ansible playbook playbooks/deploy-servers.yml -i inventory/hosts_prod -l annotation_server

install-platform-react-server: prepare
	ansible-playbook playbooks/deploy-servers.yml -i inventory/hosts_prod -l platform_react_server

install-alert-api-server: prepare
	ansible-playbook playbooks/deploy-servers.yml -i inventory/hosts_prod -l alert_server

init-pi-zero:
	ansible-playbook playbooks/rpi-init-pi-zero.yml -i inventory/hosts_prod -l $(SITE)
