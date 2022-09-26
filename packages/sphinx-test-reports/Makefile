SRC_FILES = sphinxcontrib/ tests/ noxfile.py

.PHONY: list
list:
	@$(MAKE) -pRrq -f $(lastword $(MAKEFILE_LIST)) : 2>/dev/null | awk -v RS= -F: '/^# File/,/^# Finished Make data base/ {if ($$1 !~ "^[#.]") {print $$1}}' | sort | egrep -v -e '^[^[:alnum:]]' -e '^$@$$'

.PHONY: lint
lint:
	pre-commit run --all-files

.PHONY: test
test:
	pytest -n auto --tb=long tests/

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
