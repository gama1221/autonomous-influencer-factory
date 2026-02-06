# Makefile
# Project Chimera - Build and Development Automation

.PHONY: help setup test validate spec-check format lint security-check docker-build docker-test deploy terraform mcp-start clean

# ====================
# Colors for Output
# ====================
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[1;33m
BLUE := \033[0;34m
NC := \033[0m # No Color

# ====================
# Configuration
# ====================
PROJECT_NAME := chimera-factory
PYTHON := python3.11
UV := uv
DOCKER := docker
DOCKER_COMPOSE := docker-compose
TERRAFORM := terraform

# ====================
# Help
# ====================
help:
	@echo "$(BLUE)Project Chimera - Autonomous Influencer Factory$(NC)"
	@echo ""
	@echo "$(YELLOW)Available commands:$(NC)"
	@echo ""
	@echo "$(GREEN)Development:$(NC)"
	@echo "  make setup           Install dependencies and setup environment"
	@echo "  make dev             Start development server"
	@echo "  make shell           Open Python shell with project context"
	@echo ""
	@echo "$(GREEN)Code Quality:$(NC)"
	@echo "  make format          Format code with Black and isort"
	@echo "  make lint            Run linters (flake8, mypy, bandit)"
	@echo "  make spec-check      Validate code against specifications"
	@echo "  make validate        Run all validation checks"
	@echo "  make security-check  Run security scanners"
	@echo ""
	@echo "$(GREEN)Testing:$(NC)"
	@echo "  make test            Run all tests"
	@echo "  make test-unit       Run unit tests only"
	@echo "  make test-integration Run integration tests"
	@echo "  make test-contract   Run contract tests"
	@echo "  make coverage        Generate test coverage report"
	@echo "  make docker-test     Run tests in Docker container"
	@echo ""
	@echo "$(GREEN)Docker:$(NC)"
	@echo "  make docker-build    Build Docker images"
	@echo "  make docker-up       Start Docker containers"
	@echo "  make docker-down     Stop Docker containers"
	@echo "  make docker-logs     View Docker container logs"
	@echo ""
	@echo "$(GREEN)Infrastructure:$(NC)"
	@echo "  make terraform-init  Initialize Terraform"
	@echo "  make terraform-plan  Show Terraform execution plan"
	@echo "  make terraform-apply Apply Terraform configuration"
	@echo "  make terraform-destroy Destroy Terraform resources"
	@echo ""
	@echo "$(GREEN)MCP & Telemetry:$(NC)"
	@echo "  make mcp-start       Start MCP servers"
	@echo "  make mcp-status      Check MCP server status"
	@echo "  make telemetry-export Export telemetry data"
	@echo ""
	@echo "$(GREEN)Deployment:$(NC)"
	@echo "  make deploy-dev      Deploy to development"
	@echo "  make deploy-staging  Deploy to staging"
	@echo "  make deploy-prod     Deploy to production"
	@echo ""
	@echo "$(GREEN)Utilities:$(NC)"
	@echo "  make clean           Clean build artifacts and caches"
	@echo "  make docs            Generate documentation"
	@echo "  make pre-commit      Run all pre-commit hooks"
	@echo "  make migrate         Run database migrations"
	@echo "  make seed            Seed database with test data"
	@echo ""

# ====================
# Environment Setup
# ====================
setup:
	@echo "$(BLUE)Setting up Project Chimera...$(NC)"
	
	@# Check for required tools
	@echo "$(YELLOW)Checking required tools...$(NC)"
	@command -v $(PYTHON) >/dev/null 2>&1 || { echo >&2 "$(RED)Python 3.11 is required but not installed.$(NC)"; exit 1; }
	@command -v $(UV) >/dev/null 2>&1 || { echo >&2 "$(RED)uv is required but not installed. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh$(NC)"; exit 1; }
	@command -v $(DOCKER) >/dev/null 2>&1 || { echo >&2 "$(RED)Docker is required but not installed.$(NC)"; exit 1; }
	
	@# Install dependencies
	@echo "$(YELLOW)Installing dependencies...$(NC)"
	$(UV) sync --all-extras
	
	@# Setup environment
	@echo "$(YELLOW)Setting up environment...$(NC)"
	@if [ ! -f .env ]; then \
		echo "$(YELLOW)Creating .env file from template...$(NC)"; \
		cp .env.example .env; \
		echo "$(GREEN)Please edit .env file with your configuration$(NC)"; \
	else \
		echo "$(GREEN).env file already exists$(NC)"; \
	fi
	
	@# Install pre-commit hooks
	@echo "$(YELLOW)Installing pre-commit hooks...$(NC)"
	$(UV) run pre-commit install --install-hooks
	
	@# Setup git hooks
	@echo "$(YELLOW)Setting up git hooks...$(NC)"
	git config core.hooksPath .githooks 2>/dev/null || true
	
	@# Create required directories
	@echo "$(YELLOW)Creating required directories...$(NC)"
	mkdir -p logs data/migrations/versions mcp/logs media
	
	@echo "$(GREEN)✅ Setup complete!$(NC)"
	@echo "$(YELLOW)Next steps:$(NC)"
	@echo "1. Edit the .env file with your configuration"
	@echo "2. Run 'make dev' to start the development server"
	@echo "3. Run 'make test' to verify everything works"

# ====================
# Development
# ====================
dev:
	@echo "$(BLUE)Starting development server...$(NC)"
	$(UV) run uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

shell:
	@echo "$(BLUE)Opening Python shell with project context...$(NC)"
	$(UV) run python -m IPython

# ====================
# Code Quality
# ====================
format:
	@echo "$(BLUE)Formatting code...$(NC)"
	$(UV) run black .
	$(UV) run isort .

lint:
	@echo "$(BLUE)Running linters...$(NC)"
	@echo "$(YELLOW)Running flake8...$(NC)"
	$(UV) run flake8 .
	@echo "$(YELLOW)Running mypy...$(NC)"
	$(UV) run mypy .
	@echo "$(GREEN)✅ Linting complete!$(NC)"

spec-check:
	@echo "$(BLUE)Validating against specifications...$(NC)"
	$(UV) run python -c "from utils.validation.spec_validator import validate_project; import json; result = validate_project(); print(json.dumps(result['summary'], indent=2))"

validate: spec-check lint test

security-check:
	@echo "$(BLUE)Running security checks...$(NC)"
	@echo "$(YELLOW)Running bandit...$(NC)"
	$(UV) run bandit -r . -x tests
	@echo "$(YELLOW)Running detect-secrets...$(NC)"
	$(UV) run detect-secrets scan . --baseline .secrets.baseline
	@echo "$(GREEN)✅ Security checks complete!$(NC)"

# ====================
# Testing
# ====================
test:
	@echo "$(BLUE)Running all tests...$(NC)"
	$(UV) run pytest tests/ -v --tb=short

test-unit:
	@echo "$(BLUE)Running unit tests...$(NC)"
	$(UV) run pytest tests/unit/ -v --tb=short

test-integration:
	@echo "$(BLUE)Running integration tests...$(NC)"
	$(UV) run pytest tests/integration/ -v --tb=short

test-contract:
	@echo "$(BLUE)Running contract tests...$(NC)"
	$(UV) run pytest tests/contract/ -v --tb=short -m contract

coverage:
	@echo "$(BLUE)Generating test coverage report...$(NC)"
	$(UV) run pytest tests/ --cov=. --cov-report=html --cov-report=term-missing
	@echo "$(GREEN)Coverage report generated at htmlcov/index.html$(NC)"

docker-test:
	@echo "$(BLUE)Running tests in Docker...$(NC)"
	$(DOCKER_COMPOSE) -f infrastructure/docker/docker-compose.test.yml up --build --abort-on-container-exit

# ====================
# Docker
# ====================
docker-build:
	@echo "$(BLUE)Building Docker images...$(NC)"
	$(DOCKER) build -t $(PROJECT_NAME):latest -f infrastructure/docker/Dockerfile .
	$(DOCKER) build -t $(PROJECT_NAME)-agent:latest -f infrastructure/docker/Dockerfile.agent .

docker-up:
	@echo "$(BLUE)Starting Docker containers...$(NC)"
	$(DOCKER_COMPOSE) -f infrastructure/docker/docker-compose.yml up -d

docker-down:
	@echo "$(BLUE)Stopping Docker containers...$(NC)"
	$(DOCKER_COMPOSE) -f infrastructure/docker/docker-compose.yml down

docker-logs:
	@echo "$(BLUE)Showing Docker container logs...$(NC)"
	$(DOCKER_COMPOSE) -f infrastructure/docker/docker-compose.yml logs -f

# ====================
# Infrastructure
# ====================
terraform-init:
	@echo "$(BLUE)Initializing Terraform...$(NC)"
	cd infrastructure/terraform && $(TERRAFORM) init

terraform-plan:
	@echo "$(BLUE)Showing Terraform execution plan...$(NC)"
	cd infrastructure/terraform && $(TERRAFORM) plan

terraform-apply:
	@echo "$(BLUE)Applying Terraform configuration...$(NC)"
	@read -p "$(YELLOW)Are you sure you want to apply Terraform changes? (yes/no): $(NC)" confirm; \
	if [ "$$confirm" = "yes" ]; then \
		cd infrastructure/terraform && $(TERRAFORM) apply -auto-approve; \
	else \
		echo "$(RED)Terraform apply cancelled.$(NC)"; \
	fi

terraform-destroy:
	@echo "$(BLUE)Destroying Terraform resources...$(NC)"
	@read -p "$(RED)WARNING: This will destroy all Terraform-managed resources. Are you sure? (yes/no): $(NC)" confirm; \
	if [ "$$confirm" = "yes" ]; then \
		cd infrastructure/terraform && $(TERRAFORM) destroy -auto-approve; \
	else \
		echo "$(GREEN)Terraform destroy cancelled.$(NC)"; \
	fi

# ====================
# MCP & Telemetry
# ====================
mcp-start:
	@echo "$(BLUE)Starting MCP servers...$(NC)"
	$(UV) run python -m mcp.cli --config mcp/servers.yaml

mcp-status:
	@echo "$(BLUE)Checking MCP server status...$(NC)"
	$(UV) run python scripts/telemetry/check_mcp_status.py

telemetry-export:
	@echo "$(BLUE)Exporting telemetry data...$(NC)"
	$(UV) run python scripts/telemetry/export_logs.py

# ====================
# Deployment
# ====================
deploy-dev:
	@echo "$(BLUE)Deploying to development...$(NC)"
	@echo "$(YELLOW)Building images...$(NC)"
	$(MAKE) docker-build
	@echo "$(YELLOW)Tagging images...$(NC)"
	$(DOCKER) tag $(PROJECT_NAME):latest $(DOCKER_REGISTRY)/$(PROJECT_NAME):dev-latest
	@echo "$(YELLOW)Pushing images...$(NC)"
	$(DOCKER) push $(DOCKER_REGISTRY)/$(PROJECT_NAME):dev-latest
	@echo "$(GREEN)✅ Development deployment complete!$(NC)"

deploy-staging:
	@echo "$(BLUE)Deploying to staging...$(NC)"
	@echo "$(RED)This is a placeholder for staging deployment$(NC)"
	@echo "$(YELLOW)Typically, this would trigger a CI/CD pipeline$(NC)"

deploy-prod:
	@echo "$(BLUE)Deploying to production...$(NC)"
	@echo "$(RED)WARNING: Production deployment requires manual approval$(NC)"
	@read -p "$(YELLOW)Are you sure you want to deploy to production? (yes/no): $(NC)" confirm; \
	if [ "$$confirm" = "yes" ]; then \
		echo "$(YELLOW)Starting production deployment...$(NC)"; \
		$(MAKE) terraform-apply; \
		$(MAKE) deploy-dev; \
		echo "$(GREEN)✅ Production deployment initiated!$(NC)"; \
	else \
		echo "$(RED)Production deployment cancelled.$(NC)"; \
	fi

# ====================
# Utilities
# ====================
clean:
	@echo "$(BLUE)Cleaning build artifacts and caches...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".tox" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".nox" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".hypothesis" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".uv" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".venv" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "venv" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ *.whl *.tar.gz logs/*.log 2>/dev/null || true
	@echo "$(GREEN)✅ Clean complete!$(NC)"

docs:
	@echo "$(BLUE)Generating documentation...$(NC)"
	$(UV) run pdoc --html --output-dir docs/api api
	$(UV) run mkdocs build
	@echo "$(GREEN)Documentation generated at docs/_build/$(NC)"

pre-commit:
	@echo "$(BLUE)Running pre-commit hooks...$(NC)"
	$(UV) run pre-commit run --all-files

migrate:
	@echo "$(BLUE)Running database migrations...$(NC)"
	$(UV) run alembic upgrade head

seed:
	@echo "$(BLUE)Seeding database with test data...$(NC)"
	$(UV) run python scripts/seed_database.py

# ====================
# CI/CD Helpers
# ====================
ci-test:
	@echo "$(BLUE)Running CI test suite...$(NC)"
	$(MAKE) validate
	$(MAKE) security-check
	$(MAKE) coverage

ci-build:
	@echo "$(BLUE)Building for CI...$(NC)"
	$(MAKE) docker-build
	$(DOCKER) scan $(PROJECT_NAME):latest

ci-deploy:
	@echo "$(BLUE)CI deployment...$(NC)"
	@if [ "$$ENVIRONMENT" = "production" ]; then \
		$(MAKE) deploy-prod; \
	elif [ "$$ENVIRONMENT" = "staging" ]; then \
		$(MAKE) deploy-staging; \
	else \
		$(MAKE) deploy-dev; \
	fi