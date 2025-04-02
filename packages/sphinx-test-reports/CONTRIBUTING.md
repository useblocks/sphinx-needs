# Contributing

## Formatting and linting

The easiest way to run the formatting and linting is to use the [pre-commit] tool.
Install it, then run:

```bash
pre-commit run --all
```

This will run formatting and linting on all files in the repository (principally using [ruff]).

To install as a pre-commit hook:

```bash
pre-commit install
```

## Managing the Python code

The pyproject.toml follows the [PEP621] standard.
To install all dependencies for local development you may use [uv]:

```bash
uv sync --all-groups --all-extras
```

A Makefile exits to execute common tasks:
```bash
make docs-html
make docs-linkcheck
make format
make lint
make test
make test-matrix
```

The test matrix is executed using [nox] and runs all tests in all supported Python versions.
The Python versions must be pre-installed on your system.

[pre-commit]: https://pre-commit.com/
[ruff]: https://docs.astral.sh/ruff/
[uv]: https://docs.astral.sh/uv/
[nox]: https://nox.thea.codes
[PEP621]: https://peps.python.org/pep-0621/
