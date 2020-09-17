.DEFAULT_GOAL := all

# Test Targets

test:
	poetry run nosetests -w tests

test_matrix:
	poetry run nox --session test

# Lint Targets

lint: flake8 mypy

flake8:
	poetry run flake8 sphinxcontrib

mypy:
	poetry run mypy sphinxcontrib

all:
	poetry run nox
