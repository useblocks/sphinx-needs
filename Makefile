SRC_FILES = sphinxcontrib/ tests/ noxfile.py

.PHONY: lint
lint:
	poetry run flake8 ${SRC_FILES}

.PHONY: test
test:
	poetry run nosetests -w tests

.PHONY: test-matrix
test-matrix:
	nox
