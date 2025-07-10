.phony: build dn up shell go log ps

go:
	make dn
	make build
	make up

build:
	docker compose build --no-cache

dn:
	docker compose down

up:
	docker compose up -d

shell:
	docker exec -it sao-web-1 bash

log:
	docker compose logs -f

ps:
	docker compose ps