.DEFAULT_GOAL := help

# ── Setup ────────────────────────────────────────────────
.PHONY: setup
setup: ## Install all dependencies (Python + dashboard)
	uv sync
	@if command -v npm >/dev/null 2>&1 && [ -d dashboard ]; then \
		echo "Installing dashboard dependencies..."; \
		cd dashboard && npm install; \
	fi
	@echo "\n✓ Ready. Run 'uv run pt --help' or 'make run ID=1'"

# ── Run ──────────────────────────────────────────────────
.PHONY: run
run: ## Open dashboard: make run ID=1
	uv run pt dashboard open $(ID)

.PHONY: dev
dev: ## Dev server with HMR: make dev ID=1
	uv run pt dashboard dev $(ID) --vite

# ── Quality ──────────────────────────────────────────────
.PHONY: test
test: ## Run all tests
	uv run pytest

.PHONY: lint
lint: ## Run ruff linter
	uv run ruff check src/ tests/

.PHONY: fix
fix: ## Auto-fix lint issues
	uv run ruff check --fix src/ tests/

.PHONY: check
check: lint test ## Run lint + tests

# ── Dashboard ────────────────────────────────────────────
.PHONY: build
build: ## Build dashboard (Preact → single HTML)
	cd dashboard && npx vite build

# ── Help ─────────────────────────────────────────────────
.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'
