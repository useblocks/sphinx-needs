Contributing
============

This page provides a guide for developers wishing to contribute to **Sphinx-Needs**.

Bugs, Features and  PRs
-----------------------

For **bug reports** and well-described **technical feature requests**, please use our issue tracker:
|br| https://github.com/useblocks/sphinx-needs/issues

For **feature ideas** and **questions**, please use our discussion board:
|br| https://github.com/useblocks/sphinx-needs/discussions

If you have already created a **PR**, you can send it in. Our CI workflow will check (test and code styles) and
a maintainer will perform a review, before we can merge it.
Your PR should conform with the following rules:

* A meaningful description or link, which describes the change
* The changed code (for sure :) )
* Test cases for the change (important!)
* Updated documentation, if behavior gets changed or new options/directives are introduced.
* Update of ``docs/changelog.rst``.
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

   # Build HTML pages
   make docs-html

or

.. code-block:: bash

   # Build PDF pages
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

Running JavaScript Tests in Python Test Files
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Setup Cypress Locally**

* Install Node JS on your computer and ensure it can be accessed through the CMD.
* Install Cypress using the npm package manager by running npm install cypress. Read more from this link https://docs.cypress.io/guides/getting-started/installing-cypress#npm-install.
* Verify if Cypress is installed correctly and is executable by running: npx cypress verify. Read more from this link https://docs.cypress.io/guides/guides/command-line.
* If everything is successful then we can use Cypress.

**Enable Cypress Test in Python Test Files**

* First, create a test folder to store your Cypress JS test files (files should end with: ``*.cy.js``). For each Cypress JS test file, you will need to write the Cypress JS test cases in the file. You can read more from the `Cypress Docs <https://docs.cypress.io/>`_. You can also refer to the ``tests/js_test/js-test-sn-collapse-button.cy.js`` file as reference.
* In your Python test files, you must mark every JS related test case with the marker - ``jstest`` and you also need to pass the ``spec_pattern`` key-value pair as part of the ``test_app`` fixture parameter. For example, your test case could look like the below:
    .. code-block:: python

        # test_js_code

        import pytest


        @pytest.mark.jstest
        @pytest.mark.parametrize(
            "test_app",
            [
                {
                    "buildername": "html",
                    "srcdir": "doc_test/variant_doc",
                    "tags": ["tag_a"],
                    "spec_pattern": "js_test/js-test-sn-collapse-button.cy.js"
                }
            ],
            indirect=True,
        )
        def test_collapse_button_in_docs(test_app):
            ...

    .. note::

        The ``spec_pattern`` key is required to ensure Cypress locates your test files or folder. Visit this link for more info on how to set the `spec_pattern <https://docs.cypress.io/guides/guides/command-line#cypress-run-spec-lt-spec-gt>`_.

* After you have set the ``spec_pattern`` key-value pair as part of the ``test_app`` fixture parameter, you can call the ``app.test_js()`` in your Python test case to run the JS test for the ``spec_pattern`` you provided. For example, you can use it like below:
    .. code-block:: python

        # test_js_code

        import pytest


        @pytest.mark.jstest
        @pytest.mark.parametrize(
            "test_app",
            [
                {
                    "buildername": "html",
                    "srcdir": "doc_test/variant_doc",
                    "tags": ["tag_a"],
                    "spec_pattern": "js_test/js-test-sn-collapse-button.cy.js"
                }
            ],
            indirect=True,
        )
        def test_collapse_button_in_docs(test_app):
            """Check if the Sphinx-Needs collapse button works in the provided documentation source."""
            app = test_app
            app.build()

            # Call `app.test_js()` to run the JS test for a particular specPattern
            js_test_result = app.test_js()

            # Check the return code and stdout
            assert js_test_result["returncode"] == 0
            assert "All specs passed!" in js_test_result["stdout"].decode("utf-8")

    .. note::

        ``app.test_js()`` will return a dictionary object containing the ``returncode``, ``stdout``, and ``stderr``. Example:

        .. code-block:: python

            return {
                "returncode": 0,
                "stdout": "Test passed string",
                "stderr": "Errors encountered,
            }

Linting & Formatting
--------------------

**Sphinx-Needs** uses `black <https://github.com/psf/black>`_ and
`isort <https://pycqa.github.io/isort/>`_ to format its source code.

.. code-block:: bash

    make lint

Benchmarks
----------
**Sphinx-Needs** own documentation is used for creating a benchmark for each PR.
If the runtime takes 10% longer as the previous ones, the benchmark test will fail.

Benchmark test cases are available under ``tests/benchmarks``.
And they can be locally executed via ``make benchmark``.

The results for each PR/commit get added to a chart, which is available under
http://useblocks.com/sphinx-needs/bench/index.html.

The benchmark data is stored on the `benchmarks` branch, which is also used by github-pages as
source.


Running Test Matrix
-------------------

This project provides a test matrix for running the tests across a range
of Python and Sphinx versions. This is used primarily for continuous integration.

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


Publishing a new release
------------------------
There is a release pipeline installed for the CI.

This gets triggered automatically, if a tag is created and pushed.
The tag must follow the format: ``[0-9].[0-9]+.[0-9]``. Otherwise the release jobs won't trigger.

The release jobs will build the source and wheel distribution and try to upload them
to ``test.pypi.org`` and ``pypy.org``.


.. Include our contributors and maintainers.
.. include:: ../AUTHORS
