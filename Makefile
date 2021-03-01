
.PHONY: test
test:
	poetry run nosetests -w tests

.PHONY: test-matrix
test-matrix:
	nox