SAO-PROFILE := dev
DKC_OPT := --profile ${SAO-PROFILE}
DOCKER_COMPOSE_FILE := docker-compose.yml


.phony: build dn up shell go log ps clean

build:
	docker compose ${DKC_OPT} build --no-cache

dn:
	docker compose ${DKC_OPT} down

shell:
	docker exec -it sao-web-${SAO-PROFILE}-1 bash

log:
	docker compose logs -f

ps:
	docker compose ps

up: build
	docker compose ${DKC_OPT} up

clean:
	docker compose ${DKC_OPT} down --volumes --remove-orphans
	docker image prune -f
	docker builder prune -f