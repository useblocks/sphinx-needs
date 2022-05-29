Contributing
============

This page provides a guide for developers wishing to contribute
to **Sphinx-Needs**.

Bugs, Features and  PRs
-----------------------

For **bug reports** and well-described **technical feature requests**, please use our issue tracker:
| https://github.com/useblocks/sphinxcontrib-needs/issues

For **feature ideas** and **questions**, please use our discussion board:
| https://github.com/useblocks/sphinxcontrib-needs/discussions

If you have already created a **PR**, you can send it in. Our CI workflow will check (test and code styles) and
a maintainer will perform a review, before we can merge it.
Your PR should conform with the following rules:

* A meaningful description or link, which describes the change
* The changed code (for sure :) )
* Test cases for the change (important!)
* Updated documentation, if you change a behavior or introduce a new option(s)/directive(s).
* Update of :ref:`changelog <Changelog & License>`.
* If this is your first PR, feel free to add your name in the ``AUTHORS`` file.

Installing Dependencies
-----------------------

**Sphinx-Needs** requires only
`Poetry <https://python-poetry.org/>`__ to be installed as a system
dependency, the rest of the dependencies are 'bootstrapped' and
installed in an isolated environment by Poetry.

1. `Install Poetry <https://python-poetry.org/docs/#installation>`__

2. Install project dependencies

.. code-block:: bash

    poetry install

3. `Install Pre-Commit <https://pre-commit.com/>`__

4. Install the Pre-Commit hooks

.. code-block:: bash

    pre-commit install

5. For running tests, install the dependencies of our official documentation:

.. code-block:: bash

   pip install -r docs/requirements.txt


List make targets
-----------------
**Sphinx-Needs** uses ``make`` to invoke most development related actions.

Use ``make list`` to get a list of available targets.

.. program-output:: make --no-print-directory --directory ../ list

Build docs
----------
To build the **Sphinx-Needs** documentation stored under ``/docs``, run:

.. code-block:: bash

    # HTML output
    make docs-html

or

.. code-block:: bash

    # PDF output
    make docs-pdf


It will always perform a **clean** build (calls ``make clean`` before the build).
If you want to avoid this, run the related sphinx-commands directly under ``/docs`` (e.g. ``make docs``).

Check links in docs
~~~~~~~~~~~~~~~~~~~~
To check if all used links in the documentation are still valid, run:

.. code-block:: bash

    make docs-linkcheck


Running Tests
-------------
.. hint::

   Please be sure to have the dependencies of the official documentation installed:

.. code-block:: bash

   pip install -r docs/requirements.txt
   make test

Linting & Formatting
--------------------

**Sphinx-Needs** uses `black <https://github.com/psf/black>`_ and
`isort <https://pycqa.github.io/isort/>`_ to format its source code.

.. code-block:: bash

    make lint

Running Test Matrix
-------------------

This project provides a test matrix for running the tests across a range
of Python and Sphinx versions. This is used primarily for continuous
integration.

`Nox <https://nox.thea.codes/en/stable/>`__ is used as a test runner.

Running the matrix tests requires additional system-wide dependencies

1. `Install
   Nox <https://nox.thea.codes/en/stable/tutorial.html#installation>`__
2. `Install Nox-Poetry <https://pypi.org/project/nox-poetry/>`__
3. You will also need multiple Python versions available. You can manage
   these using `Pyenv <https://github.com/pyenv/pyenv>`__

You can run the test matrix by using the ``nox`` command

.. code-block:: bash

    nox

or using the provided Makefile

.. code-block:: bash

    make test-matrix

For a full list of available options, refer to the Nox documentation,
and the local :download:`noxfile <../noxfile.py>`.

.. dropdown:: Our noxfile.py

   .. literalinclude:: ../noxfile.py


Running Commands
----------------

See the Poetry documentation for a list of commands.

In order to run custom commands inside the isolated environment, they
should be prefixed with ``poetry run`` (ie. ``poetry run <command>``).


.. Include our contributors and maintainers.
.. include:: ../AUTHORS

Publishing a new release
------------------------
There is a release pipeline installed for the CI.

This gets triggered automatically, if a tag is created and pushed.
The tag must follow the format: ``[0-9].[0-9]+.[0-9]``. Otherwise the release jobs won't trigger.

The release jobs will build the source and wheel distribution and try to upload them
to ``test.pypi.org`` and ``pypy.org``.

