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

.PHONY: docs-html
docs-html:
	poetry run make --directory docs/ html

.PHONY: docs-pdf
docs-pdf:
	poetry run make --directory docs/ latexpdf
