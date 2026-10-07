AWS_REGION ?= eu-north-1
AUTH_AWS_REGION ?= us-east-1
FRONTEND_BUCKET ?= peach-frontend-misha1
CLOUDFRONT_DISTRIBUTION_ID ?= E10CBQMS98RSZQ
FRONTEND_URL ?= https://dqvalqr0apze.cloudfront.net

.PHONY: auth-deploy auth-outputs configure-ecs-auth deploy-lab4 deploy-frontend deploy-backend github-role

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
