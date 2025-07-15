# =============================================================================
# AF Component Agent Makefile
# =============================================================================
# Application Framework Agent Component
# A template for constructing single or multi-agent flows using platforms
# such as CrewAI, LangGraph, LlamaIndex, and others.
#
# Author: DataRobot
# Version: 0.1.0
# =============================================================================

.PHONY: help install update-requirements

# Default target
.DEFAULT_GOAL := help

# Colors for output
BLUE := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
RESET := \033[0m

# =============================================================================
# Help
# =============================================================================

help: ## Show this help message
	@echo "$(BLUE)AF Component Agent - Available Commands:$(RESET)"
	@echo ""
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  $(GREEN)%-15s$(RESET) %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""

# =============================================================================
# Installation
# =============================================================================

install: ## Install development dependencies
	@echo "$(BLUE)Installing development dependencies...$(RESET)"
	uv sync --all-extras

update-requirements: ## Update requirements.in from pyproject.toml template
	@echo "$(BLUE)Updating requirements.in from pyproject.toml template...$(RESET)"
	$(MAKE) install
	@echo "$(BLUE)Creating temporary directory for template rendering...$(RESET)"
	mkdir -p template-rendered
	cp template/{{agent_app_name}}/pyproject.toml.jinja template-rendered/pyproject.toml.jinja
	@echo "$(BLUE)Rendering pyproject.toml from Jinja template...$(RESET)"
	uv run jinja2 -D agent_app_name=agent template-rendered/pyproject.toml.jinja -o template-rendered/pyproject.toml
	@echo "$(BLUE)Exporting dependencies to requirements.in...$(RESET)"
	uv pip compile template-rendered/pyproject.toml --extra codespaces --no-deps --no-annotate | \
	sed 's/==/~=/g' \
	> template/{{agent_app_name}}/docker_context/requirements.in
	@echo "$(BLUE)Syncing dependencies from requirements.in to requirements.txt...$(RESET)"
	cd template/{{agent_app_name}}/docker_context/ && \
	uv pip compile --verbose --no-annotate --no-emit-index-url --output-file=requirements.txt requirements.in
	@echo "$(BLUE)Cleaning up temporary files...$(RESET)"
	rm -rf template-rendered
	@echo "$(GREEN)Successfully updated requirements.in!$(RESET)"

	# uv pip compile --no-annotate --no-emit-index-url --output-file=requirements.txt requirements.in

