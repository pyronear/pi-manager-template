dependencies:
	@pip install ansible==10.3.0
	@pip install netaddr
	@ansible-galaxy role install -r requirements.yml
	cp hooks/pre-commit .git/hooks/pre-commit
	@chmod +x .git/hooks/pre-commit

ping:
	@ansible all -i inventory/fr_inventory -m ping --vault-password-file=.vault_passwrd

check-watchdog:
	@ansible-playbook -i inventory/fr_inventory playbooks/check-watchdog.yml --vault-password-file=.vault_passwrd -l engine_servers

check-engine:
	@ansible-playbook -i inventory/fr_inventory playbooks/check-engine.yml --vault-password-file=.vault_passwrd -l engine_servers

install-engine:
	@bash -c 'set -a; source init_script/.env; set +a; ansible-playbook -i inventory/fr_inventory playbooks/deploy-engines.yml -l tour_st_marguerite --vault-password-file=.vault_passwrd'

semaphore-up:
	@docker compose up -d #admin /changeme
	@docker exec -ti semaphore git config --global --add safe.directory /app/.git
	@docker exec -ti --user root semaphore cp -r /root/.ssh /home/semaphore/
	@docker exec -ti --user root semaphore chown -R semaphore /home/semaphore/.ssh

semaphore-stop:
	@docker compose stop
