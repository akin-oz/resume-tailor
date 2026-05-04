.PHONY: install install-web dev api web test lint format format-check typecheck check previews eval build-web deploy-web deploy-api bootstrap-gcp

install:
	uv sync --all-extras
	cd web && npm install

install-web:
	cd web && npm install

api:
	uv run uvicorn app.main:app --reload --app-dir api --port 8000

previews:
	uv run python scripts/build_previews.py

web:
	cd web && npm run dev

# Runs both servers in parallel. Stop with Ctrl-C; make kills both.
dev:
	$(MAKE) -j 2 api web

# Production build of the frontend. Set VITE_API_BASE to point at the
# deployed backend so the bundle hardcodes the right URL.
build-web:
	cd web && npm run build

# Deploy frontend to Cloudflare Workers Static Assets. Requires
# CLOUDFLARE_API_TOKEN in the environment (or `wrangler login` first).
deploy-web: build-web
	cd web && npx wrangler deploy

# One-time IAM setup. Cloud Build runs as the project's Compute SA;
# in April 2024 GCP stripped its default permissions, so the very
# first `make deploy-api` fails with `storage.objects.get denied`.
# This grants the minimal role set the SA needs to build via Cloud
# Build, push to Artifact Registry, and deploy to Cloud Run.
# Run once per project; safe to re-run (idempotent).
bootstrap-gcp:
	@if [ -z "$(GCP_PROJECT)" ]; then echo "Set GCP_PROJECT=your-project-id"; exit 1; fi
	@PROJECT_NUMBER=$$(gcloud projects describe $(GCP_PROJECT) --format='value(projectNumber)'); \
	SA="$${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"; \
	echo "Granting deploy roles to $${SA}…"; \
	for role in cloudbuild.builds.builder run.developer iam.serviceAccountUser; do \
	  gcloud projects add-iam-policy-binding $(GCP_PROJECT) \
	    --member="serviceAccount:$${SA}" --role="roles/$${role}" \
	    --condition=None --quiet > /dev/null && echo "  + $${role}"; \
	done; \
	echo "Done. Now: GCP_PROJECT=$(GCP_PROJECT) make deploy-api"

# Deploy backend to Google Cloud Run from source. Cloud Run handles
# the Docker build via Buildpacks/our Dockerfile and pushes to Artifact
# Registry. Set GCP_PROJECT; GCP_REGION defaults to europe-west1
# (Belgium — Tier 1 pricing, central EMEA latency).
# Memory cap of 512Mi keeps us well under the always-free tier.
# Run `make bootstrap-gcp` once per project before this.
deploy-api:
	@if [ -z "$(GCP_PROJECT)" ]; then echo "Set GCP_PROJECT=your-project-id"; exit 1; fi
	gcloud run deploy resume-tailor-api \
		--source . \
		--project $(GCP_PROJECT) \
		--region $(or $(GCP_REGION),europe-west1) \
		--allow-unauthenticated \
		--memory 512Mi \
		--cpu 1 \
		--max-instances 5 \
		--port 8080

test:
	uv run pytest

# Standalone runner for the bullet-pool contract eval against the worked
# example. The same checks also run as pytest under `make test`; this
# target exists for the human-readable PASS/FAIL report.
eval:
	uv run python evals/check_provenance.py

lint:
	uv run ruff check .

format:
	uv run ruff format .

format-check:
	uv run ruff format --check .

typecheck:
	uv run mypy

check: lint format-check typecheck test
