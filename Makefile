.PHONY: dev stop status api-migrate api-seed api-test api-lint dev-web lint-web typecheck-web

dev:
	./scripts/dev.sh

stop:
	./scripts/stop.sh

status:
	./scripts/status.sh

api-migrate:
	cd apps/api && .venv/bin/python -m alembic upgrade head

api-seed:
	cd apps/api && .venv/bin/python -m app.db.seed

api-test:
	cd apps/api && .venv/bin/python -m pytest tests

api-lint:
	cd apps/api && .venv/bin/python -m ruff check app tests

dev-web:
	pnpm --dir apps/web dev

lint-web:
	pnpm --dir apps/web lint

typecheck-web:
	pnpm --dir apps/web typecheck
