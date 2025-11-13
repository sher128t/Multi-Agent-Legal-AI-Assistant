SHELL := /usr/bin/env bash
.PHONY: up down dev backend frontend test lint typecheck

up:
	docker compose up -d

down:
	docker compose down -v

backend:
	cd backend && uvicorn api.main:app --reload

frontend:
	cd frontend && pnpm dev

dev:
	(cd backend && uvicorn api.main:app --reload &) \
	 && (cd frontend && pnpm dev)

test:
	cd backend && pytest

lint:
	cd backend && ruff check . && mypy .

typecheck:
	cd frontend && pnpm lint

