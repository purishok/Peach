# Spry repository specification

Status: proposed structure for the lab, written before implementation. The existing
Peach code does not yet implement this specification. Review this document before
generating the application. This document specifies structure and contracts only.

## Decision: one monorepo

Backend, frontend, database migrations, deployment configuration, and CI live in
one repository. A change to an API and its consumer can be reviewed and committed
atomically. An agent can inspect the route, schema, migration, and component in
the same context instead of guessing contracts across repositories. For a team of
four building its first slice, that context outweighs independent repositories
and independent release schedules. Each application retains its own dependencies
and Dockerfile; HTTP is the only interface between them.

## Scope and versions

The application has one meetings page with a list and a create form. Backend:
FastAPI, SQLAlchemy, Alembic, PostgreSQL. Frontend: React, Vite, TypeScript,
Tailwind, and locally owned shadcn/ui components. No authentication, task board,
cache, queue, workers, reverse-proxy container, or second database belongs to this
slice. Deployment uses the AWS services required by the lab.

Runtime image tags: `python:3.12-slim-bookworm`, `node:22-bookworm-slim`, and
`postgres:16-bookworm`. These fix runtime families and distributions; patch
contents can change. Record image digests during implementation for immutable
builds. Never use a `latest` tag.

Initial direct dependency pins (implementation must validate these together):

| Backend | Version | Frontend/tooling | Version |
| --- | --- | --- | --- |
| FastAPI | 0.115.12 | React / React DOM | 19.0.0 |
| Uvicorn | 0.34.2 | Vite | 6.3.5 |
| SQLAlchemy | 2.0.41 | TypeScript | 5.8.3 |
| asyncpg | 0.30.0 | @vitejs/plugin-react | 4.4.1 |
| Alembic | 1.15.2 | Tailwind / @tailwindcss/vite | 4.1.8 |
| Pydantic | 2.11.5 | ESLint / @eslint/js | 9.28.0 |
| pydantic-settings | 2.9.1 | typescript-eslint | 8.33.0 |
| Ruff | 0.11.12 | Prettier | 3.5.3 |
| pytest | 8.3.5 | class-variance-authority | 0.7.1 |
| pytest-asyncio | 0.26.0 | clsx | 2.1.1 |
| httpx | 0.28.1 | tailwind-merge | 3.2.0 |

shadcn/ui is checked-in component source, not a production component-library
service. Any additional required type packages, lint plugins, component primitives,
and transitive dependencies must have exact versions recorded in committed lock
files. Installation and CI consume locks without re-resolving dependencies.

## Repository layout

| Path | Purpose |
| --- | --- |
| `PROJECT.md` | Reviewed structural specification and contracts. |
| `README.md` | Setup, lab discussion notes, deployment, teardown, and verified submission links. |
| `.env.example` | Documented local defaults and names of deployment settings; no credentials. |
| `.gitignore` | Excludes credentials, virtual environments, dependencies, and generated builds; keeps application source and lock files tracked. |
| `docker-compose.yml` | The complete three-service local environment, with working defaults. |
| `Makefile` | Local checks and the shared frontend/backend deployment entry points. |
| `backend/` | Python application, locked dependencies, Dockerfile, and Alembic configuration. |
| `backend/app/` | Application factory, environment settings, engine, and session lifecycle. |
| `backend/app/api/` | HTTP routers: request parsing, responses, and health endpoints. |
| `backend/app/schemas/` | Pydantic request and response contracts. |
| `backend/app/models/` | SQLAlchemy table mappings and database constraints. |
| `backend/app/services/` | Meeting queries and creation logic independent of HTTP handlers. |
| `backend/migrations/` | Alembic environment and migration template. |
| `backend/migrations/versions/` | Ordered, reviewable schema revisions, including the meetings table. |
| `backend/scripts/` | Container startup: migrate, then start the HTTP server. |
| `backend/tests/` | API validation, PostgreSQL persistence, health, and migration checks against an isolated test database. |
| `frontend/` | Vite entry HTML, locked dependencies, TypeScript/lint/style configuration, and Dockerfile. |
| `frontend/src/` | React entry point, meetings page, and global styles. |
| `frontend/src/components/` | Meeting list, create form, loading, empty, and error states. |
| `frontend/src/components/ui/` | Only the shadcn/ui primitives actually used by the page. |
| `frontend/src/lib/` | Typed API client, date formatting, and component class-name helper. |
| `.github/` | Repository automation configuration. |
| `.github/workflows/` | Checks on every push and pull request; deployment after successful checks on main. |
| `infra/` | CloudFormation definitions for AWS networking/database, backend, frontend, and GitHub OIDC role. |
| `scripts/` | AWS setup/deploy/teardown commands called by Make; no separate CI deployment recipe. |

## HTTP contract

Both services exchange JSON over HTTP locally and HTTPS in AWS. There are no
source imports shared between frontend and backend.

Meeting fields:

| Field | Type | Rules |
| --- | --- | --- |
| `id` | string | Server-generated UUID; read-only. |
| `title` | string | Trimmed, 1–200 characters; whitespace-only input rejected. |
| `starts_at` | string | RFC 3339 datetime with an explicit UTC offset or Z. |
| `ends_at` | string | Same format; strictly after starts_at when compared as instants. |
| `attendee_count` | integer | Required, 0–2147483647; booleans and fractional values rejected. |

Database columns use UUID, varchar(200), timestamptz, and integer. Database
constraints enforce nonempty titles, nonnegative attendee counts, and end after
start. Responses normalize timestamps to UTC. The browser displays local times
and converts form values to ISO timestamps before sending them.

`GET /api/meetings` returns HTTP 200 and a JSON array of meeting objects, sorted
by starts_at ascending and id ascending as a deterministic tie-breaker. A new
database returns an empty array. No pagination or fabricated seed data.

`POST /api/meetings` accepts the four writable fields above and returns HTTP 201
with the persisted meeting, including its id. Commit succeeds before a success
response is sent. Extra fields, missing fields, and invalid values return HTTP
422 using FastAPI's validation detail list.

`GET /health` returns HTTP 200 with status equal to ok when the process answers.
`GET /health/ready` verifies a database query and the meetings table; success
returns HTTP 200 with status and database equal to ok. Database unavailability
returns HTTP 503 with a generic detail string and no connection credentials.
Database-dependent meeting requests also return 503 during an outage.

## Local service contract

Docker Desktop is the only required installation. From a fresh clone,
`docker compose up` builds missing images and starts everything with defaults;
`docker compose up --build` rebuilds after changes. Copying an env file, running
an installer, configuring cloud authentication, and migrating by hand are not
prerequisites.

| Service | Container / host port | Dependency and readiness |
| --- | --- | --- |
| `db` | 5432 / 127.0.0.1:5432 | No dependency. pg_isready checks configured user/database every 5 seconds, with a 5-second timeout and 12 retries. |
| `backend` | 8000 / 127.0.0.1:8000 | Depends on db with service_healthy. Startup applies Alembic migrations, then starts Uvicorn. Healthcheck requests /health/ready every 5 seconds, timeout 5 seconds, 12 retries, startup grace 30 seconds. |
| `frontend` | 5173 / 127.0.0.1:5173 | Depends on backend with service_healthy. Vite binds 0.0.0.0:5173; a local HTTP check verifies the page responds. |

Exactly one Compose file, a Dockerfile per application, one default Compose
network, and one named PostgreSQL data volume. A backend image defines how to
package/run Python; its production command starts Uvicorn. Compose overrides
that command to run migrations first. The frontend image provides Vite for local
development and a build stage that emits the static bundle for deployment.
Migrations never run during image builds.

Local default database/user/password are spry/spry/spry; these are disposable
development values. The backend resolves db through Compose DNS. The browser
uses VITE_API_URL=http://localhost:8000; CORS permits http://localhost:5173.
Settings allow overriding host ports and the matching API URL/CORS origin.

The database volume survives container recreation. Ordinary shutdown preserves
it; explicitly deleting volumes removes local meetings. Published database ports,
development credentials, and the Vite development server are local-only choices.

Startup ordering follows [Docker's readiness contract](https://docs.docker.com/compose/how-tos/startup-order/).
It cannot guarantee later availability. SQLAlchemy checks pooled connections
before reuse; failed transactions roll back. Requests fail promptly with 503,
and subsequent requests can recover after PostgreSQL returns. Writes are never
automatically replayed after an ambiguous failure.

## Frontend behavior

One page lists persisted meetings and provides title, start, end, and attendee
inputs. Show loading, empty, validation, submitting, failure, and retry states.
Disable duplicate form submission while pending. After success, refresh the list
from the API; reloading the page must preserve the meeting. Use accessible labels
and keyboard controls. Any week-over-week figures must derive from actual
meeting dates, with explicit handling of a zero previous-week baseline.

The Lab 1 screenshot is the styling reference when supplied. Until then, visual
fidelity to that screenshot is unverified; do not invent reference content.

## AWS and deployment contracts

Frontend: Vite's static dist output is stored in a private S3 bucket. CloudFront
uses [origin access control](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-s3.html)
and a distribution-scoped bucket policy. The frontend hostname points to the
distribution and redirects HTTP to HTTPS. Its ACM certificate is in us-east-1.
Build VITE_API_URL against the backend's HTTPS hostname.

Backend: push the same production container to ECR tagged with the full commit
SHA. ECS Fargate runs it with awsvpc networking; an Application Load Balancer
routes HTTPS to container port 8000 through an
[IP target group](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/alb.html).
Its ACM certificate is in the ALB region. Port 80 redirects to 443. Security
groups allow backend ingress only from the ALB. Health checks use /health/ready;
ECS replaces unhealthy tasks and failed rollouts must fail deployment.

Production PostgreSQL is a private RDS PostgreSQL 16 instance with persistent
storage, reachable only from backend tasks. Credentials live in Secrets Manager;
the ECS execution role supplies the database setting to containers. A one-off
task runs Alembic with the candidate image before updating the service. Failure
to migrate stops rollout. Migrations must remain compatible with the previous
application during the rolling update.

The infrastructure specification includes the required VPC/subnets, routing,
security groups, logs, execution/task roles, and database. A lab deployment may
use public task subnets with public egress and restricted inbound access to avoid
a NAT gateway; the database remains private. Document actual billable resources
and teardown steps without promising free operation.

ACM validation CNAMEs prove control of each hostname and remain for renewal.
Separate routing records connect app and api hostnames to CloudFront and ALB.
Actual domain, hosted zone, account, region, and repository identity are deployment
inputs, never invented submission URLs.

`make deploy-backend`: require configuration; build/push SHA image; register task
definition; run/wait/check migration task; update ECS; wait for service stability;
verify the requested revision and public readiness endpoint.

`make deploy-frontend`: require configuration; install from lock; build with the
HTTPS API URL; upload hashed assets with immutable caching while preserving old
assets; upload entry files with revalidation; invalidate CloudFront and wait.

Checks run Ruff, ESLint, Prettier, frontend typecheck/build, and backend tests.
Every push and pull request runs checks. Successful pushes to main deploy both
services using the same Make targets. Deployments are serialized so migrations
and releases do not race. Tagging latest is not a deployment strategy.

GitHub deployment uses aws-actions/configure-aws-credentials@v4 and job-level
id-token: write. AWS trust restricts aud to sts.amazonaws.com and sub to exactly
repo:OWNER/REPOSITORY:ref:refs/heads/main. Deployment permissions are scoped to
the application's resources; no static AWS keys are stored in GitHub. AWS setup
and GitHub repository variables supply the concrete resource identifiers.

## Review and submission gates

Before generating code, the owner reviews the structure, pins, exclusions,
contracts, and readiness behavior. Record the monorepo decision and scope changes
in the eventual commit description. Preserve course repository provenance and
push to the student's own repository, giving the lecturer access if private.

Before claiming completion: start a fresh local stack; create a meeting in the
browser; reload and verify persistence; capture a real screenshot; run checks;
demonstrate one intentional failing lint run and its subsequent fix; deploy by a
push to main; verify both custom HTTPS URLs. Submit the repository link,
screenshot, frontend URL, and backend URL. The assignment is not submitted merely
because the specification or deployment files exist.
