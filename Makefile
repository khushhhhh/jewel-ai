.PHONY: infra api web dev migrate seed clean

# ── Infrastructure ───────────────────────────────────────────
infra:
	docker compose up -d

infra-down:
	docker compose down

infra-logs:
	docker compose logs -f

# ── Backend ──────────────────────────────────────────────────
api:
	cd apps/api && source .venv/bin/activate && INNGEST_DEV=1 uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# ── Frontend ─────────────────────────────────────────────────
web:
	cd apps/web && npm run dev

# ── Both apps ────────────────────────────────────────────────
dev: infra
	@echo "Starting API and Web servers..."
	@make api & make web

# ── Database ─────────────────────────────────────────────────
migrate:
	cd apps/api && alembic upgrade head

migrate-new:
	cd apps/api && alembic revision --autogenerate -m "$(msg)"

seed:
	cd apps/api && python -m app.seed

# ── Cleanup ──────────────────────────────────────────────────
clean:
	docker compose down -v
	rm -rf apps/api/__pycache__ apps/api/app/__pycache__
