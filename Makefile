DOCKER_COMPOSE_FILE := docker-compose.yml


.phony: build dn up shell go log ps

build:
	docker compose --profile dev build

dn:
	docker compose --profile dev down

shell:
	docker exec -it sao-web-dev-1 bash

log:
	docker compose logs -f

ps:
	docker compose ps

up: build
	docker compose --profile dev up -d

