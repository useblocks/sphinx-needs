SRC_FILES = sphinxcontrib/ tests/ noxfile.py

.PHONY: list
list:
	@$(MAKE) -pRrq -f $(lastword $(MAKEFILE_LIST)) : 2>/dev/null | awk -v RS= -F: '/^# File/,/^# Finished Make data base/ {if ($$1 !~ "^[#.]") {print $$1}}' | sort | egrep -v -e '^[^[:alnum:]]' -e '^$@$$'

.PHONY: lint
lint:
	flake8 --config .flake8 ${SRC_FILES}

.PHONY: test
test:
	nosetests -v -w tests

.PHONY: test-matrix
test-matrix:
	nox

.PHONY: docs-html
docs-html:
	make --directory docs/ clean && make --directory docs/ html

.PHONY: docs-linkcheck
docs-linkcheck:
	make --directory docs/ linkcheck

.PHONY: format
format:
	black ${SRC_FILES}
	isort ${SRC_FILES}
