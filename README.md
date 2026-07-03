# CrewPilot

CrewPilot is a shift and position planning system for cafes.

The implementation is intentionally MVP-first:

- Workspace-centered UI
- FastAPI backend
- Next.js frontend
- PostgreSQL persistence
- Command-based schedule editing
- Optimization proposals before applying AI changes

## Apps

- `apps/api`: FastAPI backend
- `apps/web`: Next.js frontend

## Local Development

Install dependencies before running the apps.

```bash
pnpm install
python3 -m venv apps/api/.venv
```

Run PostgreSQL, then apply migrations and seed data:

```bash
docker compose up -d postgres
make api-migrate
make api-seed
```

Start the full development environment:

```bash
cd ~/Documents/New\ project
make dev
```

`make dev` starts PostgreSQL, FastAPI, and Next.js together. Open:

```bash
http://localhost:3000
```

Stop everything:

```bash
make stop
```

Check what is running:

```bash
make status
```

Useful checks:

```bash
make api-test
make api-lint
pnpm --dir apps/web typecheck
```

## Public Deployment

To share CrewPilot by URL, deploy three pieces:

- PostgreSQL
- FastAPI API
- Next.js Web

This repo includes `render.yaml` plus Dockerfiles for Render Blueprint deployment.

1. Push this repository to GitHub.
2. In Render, create a new Blueprint from the repository.
3. Render will create:
   - `crewpilot-db`
   - `crewpilot-api`
   - `crewpilot-web`
4. After the first deploy, set these environment variables:

For `crewpilot-api`:

```bash
ALLOWED_ORIGINS=https://<crewpilot-web>.onrender.com
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_SAMESITE=none
CREWPILOT_LOGIN_PASSWORD=<shared-password>
```

For `crewpilot-web`:

```bash
NEXT_PUBLIC_API_BASE_URL=https://<crewpilot-api>.onrender.com
```

5. Redeploy both services.
6. Open the `crewpilot-web` URL and share that link.

The API container runs Alembic migrations on startup. `RUN_SEED_DATA=true` keeps demo login
users available when the database is empty. The initial users are:

- `admin@example.com`
- `manager@example.com`
- `viewer@example.com`

Only people who know `CREWPILOT_LOGIN_PASSWORD` can log in with those accounts.
