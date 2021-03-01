# Contributing

## Installing Dependencies

Sphinxcontrib-Needs requires only [Poetry](https://python-poetry.org/) to be installed as a system dependency, the rest of the dependencies are installed in an isolated environment by Poetry.

1. [Install Poetry](https://python-poetry.org/docs/#installation)
2. Install project dependencies
   
        poetry install


## Running Tests

in order to run the tests-

    poetry run nosetests -w tests

a Makefile is also provided

    make test

## Running Test Matrix

This project also provides a test matrix for running the tests across a range of python and sphinx versions.

[Nox](https://nox.thea.codes/en/stable/) is used as a test runner.

Running the matrix tests requires additional system-wide dependencies

- [Install Nox](https://nox.thea.codes/en/stable/tutorial.html#installation)
- [Install Nox-Poetry](https://pypi.org/project/nox-poetry/)
- You will also need multiple Python versions available. You can manage these using [Pyenv](https://github.com/pyenv/pyenv)

you can run the test matrix by using the `nox` command

    nox

for a full list of available options, refer to the Nox documentation, and the local [noxfile](./noxfile.py)

## Running Commands

See the Poetry documentation for a list of commands

In order to run custom commands inside the isolated environment, they should be prefixed with "poetry run" (ie. `poetry run <command>`).

## 