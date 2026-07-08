
ansible-up:
	@docker compose up -d --build pyro-ansible
	@docker exec -it pyro-ansible sh

ansible-stop:
	@docker compose down pyro-ansible

ping:
	@ansible all -i inventory/hosts_prod -m ping

check-engines:
	ansible-playbook playbooks/check-engine.yml -i inventory/hosts_prod -l engine_servers

init-one-engine:
	ansible-playbook playbooks/rpi-init.yml -i inventory/hosts_prod -l $(SITE),mediamtx_server

deploy-one-engine:
	ansible-playbook playbooks/deploy-engines.yml -i inventory/hosts_prod -l $(SITE)

deploy-all-engines:
	ansible-playbook playbooks/deploy-engines.yml -i inventory/hosts_prod -l engine_servers

down:
	ansible-playbook playbooks/down-engines.yml -i inventory/hosts_prod -l engine_servers

up:
	ansible-playbook playbooks/up-engines.yml -i inventory/hosts_prod -l engine_servers

install-servers:
	@bash -c 'set -a; source init_script/.env; set +a; ansible-playbook playbooks/deploy-servers.yml -i inventory/hosts_prod -l $(LIMIT)'

install-openvpn:
	@bash -c 'set -a; source init_script/.env; set +a; ansible-playbook playbooks/deploy-servers.yml -i inventory/hosts_prod -l openvpn'

install-mediamtx:
	ansible-playbook playbooks/deploy-servers.yml -i inventory/hosts_prod -l mediamtx_server

update-mediamtx-conf:
	ansible-playbook playbooks/update-mediamtx.yml -i inventory/hosts_prod -l mediamtx_server

install-annotation-server:
	ansible-playbook playbooks/deploy-servers.yml -i inventory/hosts_prod -l annotation_server

install-platform-react-server:
	ansible-playbook playbooks/deploy-servers.yml -i inventory/hosts_prod -l platform_react_server

install-alert-api-server:
	ansible-playbook playbooks/deploy-servers.yml -i inventory/hosts_prod -l alert_server

install-temporal-server:
	ansible-playbook playbooks/deploy-servers.yml -i inventory/hosts_prod -l temporal_server

init-pi-zero:
	ansible-playbook playbooks/rpi-init-pi-zero.yml -i inventory/hosts_prod -l $(SITE)

sync-ssh-keys:
	ansible-playbook playbooks/sync-ssh-keys.yml -i inventory/hosts_prod
