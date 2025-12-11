# Copy the necessary files from the specified repository
prepare: confirm
	@echo "Copying inventory files from $(REPO_PATH)..."
	@cp $(REPO_PATH)/inventory inventory/
	@cp -r $(REPO_PATH)/host_vars host_vars
	@cp -r $(REPO_PATH)/group_vars group_vars

semaphore-up:
	@docker compose up -d #admin /changeme
	@docker exec -ti semaphore git config --global --add safe.directory /app/.git
	@docker exec -ti --user root semaphore cp -r /root/.ssh /home/semaphore/
	@docker exec -ti --user root semaphore chown -R semaphore /home/semaphore/.ssh

semaphore-stop:
	@docker compose stop

include ./bin/Makefile
