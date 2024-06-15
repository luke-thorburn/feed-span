.PHONY: test run

# use the new docker compose command if available or the legacy docker-compose command
DOCKER_COMPOSE := $(shell \
	docker compose version > /dev/null 2>&1; \
	if [ $$? -eq 0 ]; then \
		echo "docker compose"; \
	else \
		docker-compose version > /dev/null 2>&1; \
		if [ $$? -eq 0 ]; then \
			echo "docker-compose"; \
		fi; \
	fi; \
)

run:
	$(DOCKER_COMPOSE) up --build

test:
	$(DOCKER_COMPOSE) up -d database redis-celery-broker redis
	poetry run pytest components/sandbox_worker/*_test.py
	poetry run pytest components/scorer_worker/*_test.py
	$(DOCKER_COMPOSE) down

ci:
	$(DOCKER_COMPOSE) up -d database
	./components/ci.sh
	$(DOCKER_COMPOSE) down
