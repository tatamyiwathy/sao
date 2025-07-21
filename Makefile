DOCKER_COMPOSE_FILE := docker-compose.yml
DKC_OPT := --profile dev
# DKC_OPT := --profile prod

.phony: build dn up shell go log ps clean

build:
	docker compose ${DKC_OPT} build

dn:
	docker compose ${DKC_OPT} down

shell:
	docker exec -it sao-web-dev-1 bash

log:
	docker compose logs -f

ps:
	docker compose ps

up: build
	docker compose ${DKC_OPT} up -d

clean:
	docker compose ${DKC_OPT} down --volumes --remove-orphans
	docker image prune -f