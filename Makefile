.phony: build up shell go log ps

go:
	make build
	make up

build:
	docker compose build --no-cache

up:
	docker compose up -d

shell:
	docker exec -it sao-web-1 bash

log:
	docker compose logs -f

ps:
	docker compose ps