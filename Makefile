include .env

DKC_OPT := --profile ${SAO_PROFILE}
DOCKER_COMPOSE_FILE := docker-compose.yml


.phony: build dn up up-bg shell go log ps clean debug-db run-db mysql-shell

build:
	docker compose ${DKC_OPT} build

dn:
	docker compose ${DKC_OPT} down

shell:
	docker exec -it sao-web-${SAO_PROFILE}-1 bash

log:
	docker compose logs -f

ps:
	docker compose ps

up: build
	docker compose ${DKC_OPT} up

up-bg: build
	docker compose ${DKC_OPT} up -d

clean:
	-docker compose --profile dev --profile prod down --volumes --remove-orphans
	-docker image prune -f
	-docker builder prune -f
	-docker network prune -f


run-db:
	docker compose -f ${DOCKER_COMPOSE_FILE} run db

# データベース接続デバッグ
debug-db:
	@echo "🔍 Debugging database connection..."
	docker compose ${DKC_OPT} exec db mysql -u root -p${MYSQL_ROOT_PASSWORD} \
		-e "SELECT User, Host FROM mysql.user WHERE User='saoadmin';"
	docker compose ${DKC_OPT} exec db mysql -u root -p${MYSQL_ROOT_PASSWORD} \
		-e "SHOW DATABASES;"
# MySQLに直接接続
mysql-shell:
	docker compose ${DKC_OPT} exec db mysql -u root -p
