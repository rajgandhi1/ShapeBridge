.PHONY: setup clean lint fmt type test test-cov run mcp install-dev help
.DEFAULT_GOAL := help

# Colors for output
BOLD := \033[1m
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
RESET := \033[0m

help: ## Show this help message
	@echo "$(BOLD)ShapeBridge Development Commands$(RESET)"
	@echo
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "$(GREEN)%-15s$(RESET) %s\n", $$1, $$2}'

setup: ## Set up development environment
	@echo "$(YELLOW)Setting up development environment...$(RESET)"
	python -m pip install --upgrade pip
	pip install -e .[dev]
	pre-commit install
	@echo "$(GREEN)✓ Development environment ready$(RESET)"

clean: ## Clean up temporary files and caches
	@echo "$(YELLOW)Cleaning up...$(RESET)"
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf dist/ build/
	@echo "$(GREEN)✓ Cleanup complete$(RESET)"

lint: ## Run ruff linter
	@echo "$(YELLOW)Running linter...$(RESET)"
	ruff check src tests

fmt: ## Format code with ruff and black
	@echo "$(YELLOW)Formatting code...$(RESET)"
	ruff format src tests
	black src tests
	ruff check --fix src tests
	@command -v toml-sort >/dev/null 2>&1 && toml-sort pyproject.toml || echo "$(YELLOW)⚠ toml-sort not found, skipping$(RESET)"

type: ## Run mypy type checker
	@echo "$(YELLOW)Running type checker...$(RESET)"
	mypy src

test: ## Run pytest
	@echo "$(YELLOW)Running tests...$(RESET)"
	pytest -v

test-cov: ## Run pytest with coverage
	@echo "$(YELLOW)Running tests with coverage...$(RESET)"
	pytest --cov=src --cov-report=term-missing --cov-report=html

test-fast: ## Run tests excluding slow/integration tests
	@echo "$(YELLOW)Running fast tests only...$(RESET)"
	pytest -v -m "not slow and not integration and not occt"

run: ## Run CLI help
	@echo "$(YELLOW)ShapeBridge CLI:$(RESET)"
	python -m shapebridge.cli --help

mcp: ## Start MCP server in stdio mode
	@echo "$(YELLOW)Starting MCP server (stdio mode)...$(RESET)"
	@echo "$(GREEN)Use Ctrl+C to stop$(RESET)"
	python -m shapebridge_mcp.server

install-dev: ## Install development dependencies only
	pip install -e .[dev]

# Quality checks for CI
check: lint type test ## Run all quality checks

# Development workflow
dev: clean fmt check ## Complete development workflow

# Release preparation
release-check: clean fmt check test-cov ## Full release preparation checks
	@echo "$(GREEN)✓ Release checks passed$(RESET)"