# Developer shortcuts. Production: docker compose up -d
VENV ?= .venv
PY := $(abspath $(VENV))/bin/python

.PHONY: setup dev-backend dev-frontend test lint build migration regions docker

setup:            ## create venv + install backend & frontend deps
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install -e "backend[dev]"
	cd frontend && npm ci

dev-backend:      ## API on :8080 using .env.dev (see docs/development.md)
	set -a && . ./.env.dev && set +a && $(VENV)/bin/anamnesis serve --host 127.0.0.1 --port 8080

dev-frontend:     ## Vite on :5173 with /api proxied to :8080
	cd frontend && npm run dev

test:
	cd backend && $(PY) -m pytest -q

lint:
	cd backend && $(PY) -m ruff check .
	cd frontend && npm run typecheck

build:
	cd frontend && npm run build

migration:        ## after changing models: make migration m="add foo"
	cd backend && $(PY) -c "from anamnesis.scripts_dev import make_migration; make_migration('$(m)')"

regions:          ## regenerate regions.json from docs/regions.md
	python3 scripts/gen_regions.py

docker:
	docker build -t anamnesis:dev .
