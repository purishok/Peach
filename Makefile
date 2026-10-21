AWS_REGION ?= eu-north-1
AUTH_AWS_REGION ?= us-east-1
FRONTEND_BUCKET ?= peach-frontend-misha1
CLOUDFRONT_DISTRIBUTION_ID ?= E10CBQMS98RSZQ
FRONTEND_URL ?= https://dqvalqr0apze.cloudfront.net

.PHONY: auth-deploy auth-outputs configure-ecs-auth deploy-lab4 deploy-frontend deploy-backend github-role reports-deploy report-now reports-list reports-logs reports-test
.PHONY: llm-hello parse ai-deploy

export TEXT

llm-hello:
	cd backend && UV_CACHE_DIR=/tmp/peach-ai-uv-cache uv run python -m app.ai.cli hello

parse:
	cd backend && UV_CACHE_DIR=/tmp/peach-ai-uv-cache uv run python -m app.ai.cli parse

ai-deploy:
	./scripts/deploy-ai.sh

auth-deploy:
	AUTH_AWS_REGION="$(AUTH_AWS_REGION)" \
	FRONTEND_URL="$(FRONTEND_URL)" \
	CLOUDFRONT_DISTRIBUTION_ID="$(CLOUDFRONT_DISTRIBUTION_ID)" \
	./scripts/deploy-cognito.sh

auth-outputs:
	@set -a; test ! -f .env || . ./.env; set +a; \
	aws cloudformation describe-stacks \
		--region "$(AUTH_AWS_REGION)" \
		--stack-name "$${AUTH_STACK_NAME:-$${PROJECT_NAME:-peach}-auth}" \
		--query 'Stacks[0].Outputs[].{Name:OutputKey,Value:OutputValue}' \
		--output table

configure-ecs-auth:
	AWS_REGION="$(AWS_REGION)" ./scripts/configure-ecs-cognito.sh

deploy-lab4:
	$(MAKE) auth-deploy
	$(MAKE) configure-ecs-auth
	$(MAKE) deploy-frontend

deploy-frontend:
	AWS_REGION="$(AWS_REGION)" \
	FRONTEND_URL="$(FRONTEND_URL)" \
	FRONTEND_BUCKET="$(FRONTEND_BUCKET)" \
	CLOUDFRONT_DISTRIBUTION_ID="$(CLOUDFRONT_DISTRIBUTION_ID)" \
	./scripts/deploy-frontend.sh

deploy-backend:
	AWS_REGION="$(AWS_REGION)" ./scripts/deploy-backend.sh

github-role:
	AWS_REGION="$(AWS_REGION)" ./scripts/github-role.sh

reports-deploy:
	AWS_REGION="$(AWS_REGION)" ./scripts/deploy-reports.sh

report-now:
	AWS_REGION="$(AWS_REGION)" WEEK="$(WEEK)" ./scripts/report-now.sh

reports-list:
	@set -a; test ! -f .env || . ./.env; set +a; \
	bucket="$$(aws cloudformation describe-stacks --region "$(AWS_REGION)" \
		--stack-name "$${REPORTS_STACK_NAME:-$${PROJECT_NAME:-peach}-reports}" \
		--query "Stacks[0].Outputs[?OutputKey=='ReportsBucketName'].OutputValue | [0]" \
		--output text)"; \
	aws s3 ls "s3://$$bucket/reports/" --recursive --region "$(AWS_REGION)"

reports-logs:
	@set -a; test ! -f .env || . ./.env; set +a; \
	aws logs tail "/aws/lambda/$${PROJECT_NAME:-peach}-report-builder" \
		--region "$(AWS_REGION)" --since 1h --follow

reports-test:
	docker compose up -d db
	cd backend && DATABASE_URL="postgresql+asyncpg://$${POSTGRES_USER:-peach}:$${POSTGRES_PASSWORD:-peach}@127.0.0.1:$${POSTGRES_PORT:-5433}/$${POSTGRES_DB:-peach}" \
		APP_ENV=test UV_CACHE_DIR=/tmp/peach-reports-uv-cache \
		uv run pytest tests/test_weekly_report.py tests/test_report_handlers.py
