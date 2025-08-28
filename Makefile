include .env

DKC_OPT := --profile ${SAO_PROFILE}
DOCKER_COMPOSE_FILE := docker-compose.yml
SERVICE_NAME := web-${SAO_PROFILE}
DB_CMD := psql
# DB_CMD := mysql

# 環境変数をエクスポート
export DB_NAME
export DB_HOST
export DB_PORT
export SAO_DB_USER
export SAO_DB_PASSWORD


.PHONY: build dn deploy deploy-bg shell log ps clean debug-db run-db stop-db db-shell \
		test test-with-db test-verbose test-coverage test-app test-file \
		coverage-report coverage-html clean-test clean-coverage generate-db-init \
		makemigrations migrate help run-web stop-web restart-web \
		merge-to-main create-branch finish-branch git-status
		
build:
	docker compose ${DKC_OPT} build

dn:
	docker compose ${DKC_OPT} down

shell:
	docker exec -it sao-web-${SAO_PROFILE}-1 bash

log:
	docker compose ${DKC_OPT} logs -f

ps:
	docker compose ps

deploy: build
	docker compose ${DKC_OPT} up

deploy-bg: build
	docker compose ${DKC_OPT} up -d

clean:
	-docker compose --profile dev --profile prod down --remove-orphans
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

makemigrations:
	docker compose ${DKC_OPT} run --rm ${SERVICE_NAME} \
		python manage.py makemigrations --noinput

migrate:
	docker compose ${DKC_OPT} run --rm ${SERVICE_NAME} \
		python manage.py migrate

# データベース接続デバッグ
debug-db:
	@echo "🔍 Debugging database connection..."
	docker compose ${DKC_OPT} exec db psql -U ${SAO_DB_USER} -d ${DB_NAME} \
		-c "SELECT usename FROM pg_user WHERE usename='${SAO_DB_USER}';"

# MySQLに直接接続
db-shell:
	docker compose ${DKC_OPT} exec db psql -U ${SAO_DB_USER} -d ${DB_NAME}

# === テスト関連 ===

# 基本テスト
test:
	@echo "🧪 Running Django tests (fast mode)..."
	docker compose ${DKC_OPT} run --rm --no-deps \
		-e IS_TEST=true \
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
		-e DB_HOST="" \
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
	@echo ""
	@echo "SAO Django Application Make Commands"
	@echo ""
	@echo "  Build/Deploy:"
	@echo "    make build       - Build Docker images"
	@echo "    make deploy      - Start all services (foreground)"
	@echo "    make deploy-bg   - Start all services (background)"
	@echo "    make dn          - Stop all services"
	@echo "    make clean       - Clean up Docker resources"
	@echo ""
	@echo "  Service Management:"
	@echo "    make run-web     - Start web service (with database dependency)"
	@echo "    make stop-web    - Stop web service"
	@echo "    make restart-web - Restart web service"
	@echo "    make run-db      - Start database service"
	@echo "    make stop-db     - Stop database service"
	@echo ""
	@echo "  Database:"
	@echo "    make generate-db-init - Generate database initialization file"
	@echo "    make debug-db         - Debug database connection"
	@echo "    make db-shell         - Access MySQL shell"
	@echo ""
	@echo "  Development:"
	@echo "    make shell       - Access container shell"
	@echo "    make log         - View container logs"
	@echo "    make ps          - Show running containers"
	@echo ""
	@echo "  Testing:"
	@echo "    make test              - Run basic Django tests (fast)"
	@echo "    make test-with-db      - Run tests with database"
	@echo "    make test-verbose      - Run tests with verbose output"
	@echo "    make test-coverage     - Run tests with coverage report"
	@echo "    make test-app APP=name - Run tests for specific app"
	@echo "    make test-file FILE=path - Run specific test file/class"
	@echo "    make coverage-report   - Display coverage report"
	@echo "    make coverage-html     - Generate HTML coverage report"
	@echo "    make clean-test        - Clean test-related files"
	@echo ""
	@echo "  Git Operations:"
	@echo "    make git-status        - Show git status and recent commits"
	@echo "    make create-branch     - Create and switch to new feature branch"
	@echo "    make merge-to-main     - Merge current branch to main (manual)"
	@echo "    make finish-branch     - Complete feature branch (merge + cleanup)"
	@echo ""
	@echo "  Examples:"
	@echo "    make test-app APP=sao"
	@echo "    make test-file FILE=sao.tests.test_models.TestTimecard"
	@echo ""
	@echo "  Quick Start (Development):"
	@echo "    1. make build"
	@echo "    2. make generate-db-init"
	@echo "    3. make run-web"


# Git Operations
git-status:
	@echo "=== Git Status ==="
	@git status --short
	@echo ""
	@echo "=== Current Branch ==="
	@git branch --show-current
	@echo ""
	@echo "=== Recent Commits ==="
	@git log --oneline -5

create-branch:
	@read -p "Enter new branch name: " branch; \
	git checkout -b "$$branch" && \
	echo "Created and switched to branch: $$branch"

merge-to-main:
	@echo "=== Current Branch Status ==="
	@current_branch=$$(git branch --show-current); \
	if [ "$$current_branch" = "main" ]; then \
		echo "Already on main branch. Nothing to merge."; \
		exit 1; \
	fi; \
	echo "Current branch: $$current_branch"; \
	echo ""; \
	@git status --porcelain | wc -l | xargs -I {} test {} -eq 0 || (echo "Uncommitted changes found. Please commit or stash first." && exit 1)
	@echo "=== Switching to main branch ==="
	@git checkout main
	@echo "=== Merging feature branch ==="
	@git merge --no-ff $(shell git branch --show-current 2>/dev/null || echo "main")
	@echo "=== Pushing to remote ==="
	@git push origin main
	@echo "=== Merge completed successfully! ==="

finish-branch:
	@echo "=== Finishing current feature branch ==="
	@current_branch=$$(git branch --show-current); \
	if [ "$$current_branch" = "" ]; then \
		echo "❌ 現在のブランチ名が取得できません。git statusで確認してください。"; \
		exit 1; \
	fi; \
	if [ "$$current_branch" = "main" ]; then \
		echo "Cannot finish main branch."; \
		exit 1; \
	fi; \
	echo "Finishing branch: $$current_branch"; \
	$(MAKE) merge-to-main; \
	echo "=== Cleaning up local branch ==="
	git branch -d "$$current_branch" && \
	echo "Branch $$current_branch has been merged and deleted."