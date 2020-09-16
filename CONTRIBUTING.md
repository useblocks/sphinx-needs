# Contributing

## Prerequisites

### For Development

- [Poetry](https://python-poetry.org/)

### For Running Test Matrix

- python 3.5
- python 3.7
- python 3.8

*multiple python interpreters can be installed and managed using [pyenv](https://github.com/pyenv/pyenv)*

## Tasks

Note that a [`Makefile`](./Makefile) is provided for common tasks

### Installing Dependencies

    make install

### Running tests

    make test

### Running Matrix Tests

*(requires multiple Python interpreters to be installed)*

    make test_matrix

### Lint

    make lint