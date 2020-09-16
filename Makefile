.DEFAULT_GOAL := all

test:
	poetry run nosetests -w tests

test_matrix:
	poetry run nox --session test

lint:
	poetry run nox --session lint

all:
	poetry run nox
