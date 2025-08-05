include .env

DKC_OPT := --profile ${SAO_PROFILE}
DOCKER_COMPOSE_FILE := docker-compose.yml
SERVICE_NAME := web-${SAO_PROFILE}


# 環境変数をエクスポート
export MYSQL_DATABASE
export SAO_DB_USER
export SAO_DB_PASSWORD


.PHONY: build dn deploy deploy-bg shell log ps clean debug-db run-db stop-db db-shell \
		test test-with-db test-verbose test-coverage test-app test-file \
		coverage-report coverage-html clean-test clean-coverage generate-db-init
		
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

deploy: build
	docker compose ${DKC_OPT} up

deploy-bg: build
	docker compose ${DKC_OPT} up -d

clean:
	-docker compose --profile dev --profile prod down --volumes --remove-orphans
	-docker image prune -f
	-docker builder prune -f
	-docker network prune -f

# Webサービスの起動（データベース依存関係付き）
run-web: run-db
	@echo "🚀 Starting web service..."
	docker compose ${DKC_OPT} up ${SERVICE_NAME}
	@echo "✅ Web service started"

# Webサービスの停止
stop-web:
	@echo "🛑 Stopping web service..."
	docker compose ${DKC_OPT} stop ${SERVICE_NAME}
	@echo "✅ Web service stopped"

# Webサービスの再起動
restart-web:
	@echo "🔄 Restarting web service..."
	make stop-web
	make start-web
	
# データベースサービスの起動
run-db:
	docker compose ${DKC_OPT} up -d db
	@echo "✅ db service ready"

# データベースサービスの停止
stop-db:
	docker compose ${DKC_OPT} stop db
	@echo "✅ Database service stopped"

# データベース初期化ファイルの生成
# 	ファイル内で使用する変数は.envファイルから取得
generate-db-init:
	@echo "🔧 Generating database initialization file..."
	envsubst < docker/db-init/init.template > docker/db-init/init.sql
	@echo "✅ Generated docker/db-init/init.sql"

# データベース接続デバッグ
debug-db:
	@echo "🔍 Debugging database connection..."
	docker compose ${DKC_OPT} exec db mysql -u root -p${MYSQL_ROOT_PASSWORD} \
		-e "SELECT User, Host FROM mysql.user WHERE User='saoadmin';"
	docker compose ${DKC_OPT} exec db mysql -u root -p${MYSQL_ROOT_PASSWORD} \
		-e "SHOW DATABASES;"
# MySQLに直接接続
db-shell:
	docker compose ${DKC_OPT} exec db mysql -u root -p


# === テスト関連 ===

# 基本テスト
test:
	@echo "🧪 Running Django tests (fast mode)..."
	docker compose ${DKC_OPT} run --rm --no-deps \
		-e IS_TEST=true \
		-e MYSQL_HOST="" \
		${SERVICE_NAME} python manage.py test

# データベース付きテスト
test-with-db:
	@echo "🧪 Running Django tests with database..."
	docker compose ${DKC_OPT} run --rm ${SERVICE_NAME} \
		python manage.py test --keepdb

# 詳細テスト
test-verbose:
	@echo "🧪 Running Django tests (verbose)..."
	docker compose ${DKC_OPT} run --rm --no-deps \
		-e IS_TEST=true \
		${SERVICE_NAME} python manage.py test --verbosity=2

# カバレッジ付きテスト
test-coverage:
	@echo "🧪 Running Django tests with coverage..."
	docker compose ${DKC_OPT} run --rm --no-deps \
		-e IS_TEST=true \
		-e MYSQL_HOST="" \
		${SERVICE_NAME} \
		bash -c "coverage run --source='.' manage.py test && coverage report && coverage html"

# 特定のアプリのテスト
test-app:
	@echo "🧪 Running tests for specific app: $(APP)"
	@if [ -z "$(APP)" ]; then \
		echo "❌ Please specify APP name: make test-app APP=sao"; \
		exit 1; \
	fi
	docker compose ${DKC_OPT} run --rm --no-deps \
		-e IS_TEST=true \
		${SERVICE_NAME} python manage.py test $(APP)

# 特定のテストファイル/クラスの実行
test-file:
	@echo "🧪 Running specific test: $(FILE)"
	@if [ -z "$(FILE)" ]; then \
		echo "❌ Please specify FILE: make test-file FILE=sao.tests.TestModel"; \
		exit 1; \
	fi
	docker compose ${DKC_OPT} run --rm --no-deps \
		-e IS_TEST=true \
		${SERVICE_NAME} python manage.py test $(FILE)

# カバレッジレポートの表示
coverage-report:
	@echo "📊 Displaying coverage report..."
	docker compose ${DKC_OPT} run --rm --no-deps \
		${SERVICE_NAME} coverage report

# HTMLカバレッジレポートの生成
coverage-html:
	@echo "📊 Generating HTML coverage report..."
	docker compose ${DKC_OPT} run --rm --no-deps \
		${SERVICE_NAME} coverage html
	@echo "✅ HTML report generated in htmlcov/ directory"

# テスト関連ファイルのクリーンアップ
clean-test:
	@echo "🧹 Cleaning test files..."
	docker compose ${DKC_OPT} run --rm --no-deps \
		${SERVICE_NAME} \
		bash -c "find . -name '*.pyc' -delete && find . -name '__pycache__' -type d -exec rm -rf {} + || true"
	docker compose ${DKC_OPT} run --rm --no-deps \
		${SERVICE_NAME} \
		bash -c "rm -rf htmlcov/ .coverage* || true"
	@echo "✅ Test cleanup completed"

	
# ヘルプ

help:
	@echo "🚀 SAO Application Commands:"
	@echo ""
	@echo "  Start/Stop:"
	@echo "    make build   - Build Docker images"
	@echo "    make up      - Start services (foreground)"
	@echo "    make up-bg   - Start services (background)"
	@echo "    make dn      - Stop services"
	@echo ""
	@echo "  Development:"
	@echo "    make shell   - Access container shell"
	@echo "    make log     - View logs"
	@echo "    make ps      - Show running containers"
	@echo ""
	@echo "  Testing:"
	@echo "    make test            - Run basic Django tests"
	@echo "    make test-dev        - Run tests in development mode"
	@echo "    make test-coverage   - Run tests with coverage report"
	@echo "    make test-app APP=sao - Run tests for specific app"
	@echo "    make test-file FILE=sao.tests.TestModel - Run specific test"
	@echo "    make clean-test      - Clean test-related files"
	@echo ""
	@echo "  Database:"
	@echo "    make debug-db    - Debug database connection"
	@echo "    make mysql-shell - Access MySQL shell"
	@echo ""
	@echo "  Maintenance:"
	@echo "    make clean   - Clean up Docker resources"