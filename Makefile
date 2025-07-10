.phony: build up shell go log

go:
	make build
	make up

build:
	docker compose build --no-cache

up:
	docker compose up -d

shell:
	docker compose exec sao-web-1 bash

log:
	docker compose logs -f