# ─────────────────────────────────────────────────────────────────
# krag Makefile — Pre-commit checks for Python + TypeScript
# ─────────────────────────────────────────────────────────────────
.PHONY: check check-python check-krager help

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

check: check-python check-krager ## Run all pre-commit checks (Python + TypeScript)

check-python: ## Run Python checks (ruff format, ruff check, mypy, pytest)
	uv run ruff format --check .
	uv run ruff check .
	uv run mypy --config-file mypy.ini src/
	uv run pytest

check-krager: ## Run krager checks (svelte-check, biome lint, vitest)
	cd apps/krager && pnpm check
	cd apps/krager && pnpm lint
	cd apps/krager && pnpm test
