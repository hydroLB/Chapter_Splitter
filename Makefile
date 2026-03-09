SHELL := /bin/bash
.DEFAULT_GOAL := help

VENV311_BIN := .venv311/bin
VENV_BIN := .venv/bin

ifeq ($(wildcard $(VENV311_BIN)/python),$(VENV311_BIN)/python)
BIN_DIR := $(VENV311_BIN)
else ifeq ($(wildcard $(VENV_BIN)/python),$(VENV_BIN)/python)
BIN_DIR := $(VENV_BIN)
else
BIN_DIR :=
endif

MODE ?= gui
PYTHON ?= $(if $(BIN_DIR),$(BIN_DIR)/python,python3)
export PYTHONPATH := $(CURDIR)/Chapter_Splitter$(if $(PYTHONPATH),:$(PYTHONPATH))
PIP := $(PYTHON) -m pip
RUFF := $(PYTHON) -m ruff
MYPY := $(PYTHON) -m mypy
COVERAGE := $(PYTHON) -m coverage
BANDIT := $(PYTHON) -m bandit
PIP_AUDIT := $(PYTHON) -m pip_audit

.PHONY: help install-dev hooks dev lint typecheck boundaries deps-policy repo-hygiene docstrings test security build release-check check

help: ## Show available targets.
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "%-14s %s\n", $$1, $$2}'

install-dev: ## Install pinned runtime and development dependencies.
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt -r requirements-dev.txt
	$(PIP) install -e .
	$(MAKE) hooks

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

deps-policy: ## Enforce dependency lockfile and Dependabot policy consistency.
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
	$(PIP_AUDIT) -r requirements.txt -r requirements-dev.txt

build: ## Build source and wheel distributions.
	rm -rf build dist
	$(PYTHON) -m build

release-check: ## Enforce release discipline checks.
	$(PYTHON) scripts/check_release_discipline.py

check: lint typecheck boundaries deps-policy repo-hygiene docstrings test security build release-check ## Run all local quality gates.
