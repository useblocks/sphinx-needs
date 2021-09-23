SRC_FILES = sphinxcontrib/ tests/ performance/ noxfile.py

.PHONY: list
list:
	@$(MAKE) -pRrq -f $(lastword $(MAKEFILE_LIST)) : 2>/dev/null | awk -v RS= -F: '/^# File/,/^# Finished Make data base/ {if ($$1 !~ "^[#.]") {print $$1}}' | sort | egrep -v -e '^[^[:alnum:]]' -e '^$@$$'

.PHONY: lint
lint:
	poetry run flake8 ${SRC_FILES}

.PHONY: test
test:
	poetry run nosetests -v -w tests

.PHONY: test
test-short:
	poetry run nosetests -v -w tests -I .*official.*

.PHONY: test-matrix
test-matrix:
	nox

.PHONY: docs-html
docs-html:
	poetry run make --directory docs/ clean && make --directory docs/ html

.PHONY: docs-pdf
docs-pdf:
	poetry run make --directory docs/ clean && make --directory docs/ latexpdf


.PHONY: docs-linkcheck
docs-linkcheck:
	poetry run make --directory docs/ linkcheck

.PHONY: format
format:
	poetry run black ${SRC_FILES}
	poetry run isort ${SRC_FILES}
