VENV := ./.venv


help:  ## Display help on all Makefile targets
	@@grep -h '^[a-zA-Z]' $(MAKEFILE_LIST) | awk -F ':.*?## ' 'NF==2 {printf "   %-20s%s\n", $$1, $$2}' | sort



dev: $(VENV)  ## Create a new dev environment
	$(VENV)/bin/python -m pip install --upgrade pip
	$(VENV)/bin/python -m pip install -e ".[dev]"


test: $(VENV)  ## Run the unit tests
	$(VENV)/bin/pytest


type-check: $(VENV)  ## Run static type check
	$(VENV)/bin/mypy


check: type-check test  ## Run all tests and quality checks


.PHONY: $(MAKECMDGOALS)


# Path-based rules

$(VENV):  # Create a bare virtual environment
	python -m venv $(VENV)
