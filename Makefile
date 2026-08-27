SHELL := /bin/bash
.DEFAULT_GOAL := help

VENV_DIR ?= .venv
BIN_DIR := $(VENV_DIR)/bin

MODE ?= gui
PYTHON ?= $(BIN_DIR)/python
PIP := $(PYTHON) -m pip
RUFF := $(PYTHON) -m ruff
MYPY := $(PYTHON) -m mypy
COVERAGE := $(PYTHON) -m coverage
BANDIT := $(PYTHON) -m bandit
PIP_AUDIT := $(PYTHON) -m pip_audit

.PHONY: help venv install-dev install-desktop hooks dev lint typecheck boundaries deps-policy repo-hygiene docstrings test security build release-check check

help: ## Show available targets.
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "%-14s %s\n", $$1, $$2}'

venv: ## Create the shared local Python environment when needed.
	bash scripts/bootstrap_venv.sh "$(CURDIR)/$(VENV_DIR)"

install-dev: venv ## Install pinned runtime and development dependencies.
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements-dev.txt
	$(PIP) install -e .
	$(MAKE) hooks

install-desktop: install-dev ## Install the optional Qt desktop runtime for local GUI work.
	$(PIP) install -e '.[desktop]'

hooks: ## Install repo-owned git hooks into the local clone.
	git config core.hooksPath .githooks
	chmod +x .githooks/pre-commit .githooks/pre-push

dev: ## Run the local application workflow (MODE=gui or MODE=split).
	CHAPTER_SPLITTER_MODE=$(MODE) ./start

lint: ## Run format and lint checks.
	$(RUFF) format --check .
	$(RUFF) check .

typecheck: ## Run strict static typing checks.
	$(MYPY) --config-file pyproject.toml

boundaries: ## Enforce module dependency direction rules.
	$(PYTHON) scripts/check_import_boundaries.py

deps-policy: ## Enforce dependency pin and Dependabot policy consistency.
	$(PYTHON) scripts/check_dependency_policy.py

repo-hygiene: ## Enforce tracked-file hygiene for public recovery-ready repositories.
	$(PYTHON) scripts/check_repo_hygiene.py

docstrings: ## Enforce standardized Python docstring headings.
	$(PYTHON) scripts/check_docstring_standards.py

test: ## Run deterministic test suite with coverage threshold.
	$(COVERAGE) run -m pytest -W error
	$(COVERAGE) report --fail-under=90

security: ## Run static and dependency security scans.
	$(BANDIT) -c pyproject.toml -r Chapter_Splitter/chapter_splitter
	$(PIP_AUDIT) -r requirements.txt -r requirements-dev.txt -r requirements-bundle.txt

build: ## Build source and wheel distributions.
	rm -rf build dist
	$(PYTHON) -m build

release-check: ## Enforce release discipline checks.
	$(PYTHON) scripts/check_release_discipline.py

check: lint typecheck boundaries deps-policy repo-hygiene docstrings test security build release-check ## Run all local quality gates.
