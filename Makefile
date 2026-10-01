AWS_REGION ?= eu-central-1
FRONTEND_BUCKET ?= peach-frontend-misha1
CLOUDFRONT_DISTRIBUTION_ID ?= E10CBQMS98RSZQ

.PHONY: deploy-frontend deploy-backend github-role

deploy-frontend:
	cd frontend && npm ci && npm run build
	aws s3 sync frontend/out/ s3://$(FRONTEND_BUCKET) --delete --region $(AWS_REGION)
	aws cloudfront create-invalidation \
		--distribution-id $(CLOUDFRONT_DISTRIBUTION_ID) \
		--paths "/*"

deploy-backend:
	AWS_REGION="$(AWS_REGION)" ./scripts/deploy-backend.sh

github-role:
	AWS_REGION="$(AWS_REGION)" ./scripts/github-role.sh
