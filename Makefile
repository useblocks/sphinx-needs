SRC_FILES = sphinx_needs/ tests/ performance/ noxfile.py

.PHONY: list
list:
	@$(MAKE) -pRrq -f $(lastword $(MAKEFILE_LIST)) : 2>/dev/null | awk -v RS= -F: '/^# File/,/^# Finished Make data base/ {if ($$1 !~ "^[#.]") {print $$1}}' | sort | egrep -v -e '^[^[:alnum:]]' -e '^$@$$'

.PHONY: lint
lint:
	pre-commit run --all-files

.PHONY: test
test:
	poetry run pytest -n auto -m "not jstest" --tb=long --ignore=tests/benchmarks tests/

.PHONY: test
test-short:
	poetry run pytest -n auto -m "not jstest" --tb=long --ignore-glob="*official*" --ignore=tests/benchmarks tests/

.PHONY: benchmark-time
benchmark-time:
	nox --non-interactive --session benchmark_time -- --full-trace

.PHONY: benchmark-memory
benchmark-memory:
	nox --non-interactive --session benchmark_memory -- --full-trace

.PHONY: test-matrix
test-matrix:
	nox

.PHONY: docs-html
docs-html:
	poetry run sphinx-build -a -E -j auto -b html docs/ docs/_build

.PHONY: docs-html
docs-html-fast:
	poetry run sphinx-build -j auto -b html docs/ docs/_build

.PHONY: needs
needs:
	poetry run sphinx-build -a -E -j auto -b needs docs/ docs/_build

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
