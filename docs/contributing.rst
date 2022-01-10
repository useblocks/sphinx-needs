Contributing
============

The following provides a guide for developers wishing to contribute
to ``Sphinx-Needs``.

.. contents::
   :local:

Bugs, Features and  PRs
-----------------------

| For **bug reports** and technical well described feature requests please use our issue tracker:
| https://github.com/useblocks/sphinxcontrib-needs/issues

| For **feature ideas** and **questions** please use our discussion board:
| https://github.com/useblocks/sphinxcontrib-needs/discussions

If you have already created a **PR**, awesome! Just send it in. It will be checked by our CI (test and code styles) and
a maintainer needs to perform a review, before it can be merged.
Your PR should  contain the following parts:

* A meaningful description or link, which describes the change
* The changed code (for sure :) )
* Test cases for the change (important!)
* Updated documentation, if behavior gets changed or new options/directives are introduced.
* Update of ``docs/changelog.rst``.
* If this is your first PR, feel free to add your name in the ``AUTHORS`` file.

Installing Dependencies
-----------------------

``Sphinx-Needs`` requires only
`Poetry <https://python-poetry.org/>`__ to be installed as a system
dependency, the rest of the dependencies are ‘bootstrapped’ and
installed in an isolated environment by Poetry.

1. `Install Poetry <https://python-poetry.org/docs/#installation>`__

2. Install project dependencies

   ::

       poetry install

3. `Install Pre-Commit <https://pre-commit.com/>`__

4. Install the Pre-Commit hooks

   ::

      pre-commit install

5. For running tests install also the dependencies of our official documentation:
   ``pip install -r docs/requirements.txt``


List make targets
-----------------
``Sphinx-Needs`` uses ``make`` to invoke most development related actions.

Use ``make list`` to get a list of available targets.

.. program-output:: make --no-print-directory --directory ../ list

Build docs
----------
This will build the ``Sphinx-Needs`` documentation stored under ``/docs``.

It will always perform a **clean** build (calls ``make clean`` before the build).
If you want to avoid this, run the related sphinx-commands directly under ``/docs`` (e.g. ``make docs``).

::

    make docs-html

or::

    make docs-pdf

Check links in docs
~~~~~~~~~~~~~~~~~~~~
To check if all used links in the documentation are still valid, run::

    make docs-linkcheck


Running Tests
-------------
.. hint::

   Please be sure to have the dependencies of the official documentation installed:
   ``pip install -r docs/requirements.txt``


::

   make test

Linting & Formatting
--------------------

``Sphinx-Needs`` uses `black <https://github.com/psf/black>`_ and
`isort <https://pycqa.github.io/isort/>`_ to care about its source code formatting.

::

   make lint

Running Test Matrix
-------------------

This project provides a test matrix for running the tests across a range
of python and sphinx versions. This is used primarily for continuous
integration.

`Nox <https://nox.thea.codes/en/stable/>`__ is used as a test runner.

Running the matrix tests requires additional system-wide dependencies

1. `Install
   Nox <https://nox.thea.codes/en/stable/tutorial.html#installation>`__
2. `Install Nox-Poetry <https://pypi.org/project/nox-poetry/>`__
3. You will also need multiple Python versions available. You can manage
   these using `Pyenv <https://github.com/pyenv/pyenv>`__

You can run the test matrix by using the ``nox`` command

::

   nox

or using the provided Makefile

::

   make test-matrix

For a full list of available options, refer to the Nox documentation,
and the local :download:`noxfile <../noxfile.py>`.

.. dropdown:: Our noxfile.py

   .. literalinclude:: ../noxfile.py


Running Commands
----------------

See the Poetry documentation for a list of commands.

In order to run custom commands inside the isolated environment, they
should be prefixed with “poetry run” (ie. ``poetry run <command>``).


.. Include our contributors and maintainers.
.. include:: ../AUTHORS
