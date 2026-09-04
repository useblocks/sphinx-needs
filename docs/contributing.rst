Contributing
============

This page provides a guide for developers wishing to contribute to **Sphinx-Needs**.

Bugs, Features and PRs
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

To develop **Sphinx-Needs**, use `uv <https://docs.astral.sh/uv/>`__ to install the
project and its development dependencies into an isolated environment:

.. code-block:: bash

   uv sync

.. note::

   The ``docs`` extra requires Python >= 3.11.
   On Python 3.10 the extra still installs, but the documentation cannot be built.

``uv.lock`` is committed, so ``uv sync`` installs exactly the versions recorded in it,
and every contributor and CI job gets the same environment.
If you change the dependencies in ``pyproject.toml``, the ``uv-lock`` hook below updates
the lock for you (``uv lock`` does the same by hand); commit the result with your change.
Dependabot refreshes the locked versions once a month: minor and patch updates arrive
batched in one pull request, major updates one pull request each.

To run the formatting and linting suite, `prek <https://prek.j178.dev/>`__ is used:

.. code-block:: bash

   uv run prek install  # to auto-run on every commit
   uv run prek run --all-files  # to run manually

The hooks are declared in ``.pre-commit-config.yaml``, which prek reads unchanged,
so `pre-commit <https://pre-commit.com/>`__ itself still works if you prefer it.

Hook versions are bumped by the scheduled ``Prek update`` workflow, which opens a
pull request with the new revisions.

Testing and documentation building are run as `poe <https://poethepoet.natn.io>`__
tasks, declared in ``pyproject.toml``:

.. code-block:: bash

   uv run poe  # to see all tasks

Words written after a task name are appended to the command it runs, so ``pytest`` and
``sphinx-build`` options can be passed straight through.
A task that needs something other than the default environment — one sphinx version, a
documentation theme — installs into its own ``.venvs/`` directory, so tasks do not
overwrite each other's environment.
``uv run poe typecheck`` is one of those tasks: it installs the ``typing`` dependency
group — the oldest supported Sphinx and Docutils, plus ty itself — into ``.venvs/typing``
and checks against it, which is what CI and the prek ``ty`` hook do too.
Running ``ty`` by hand, or through an editor extension, uses ``.venvs/typing`` as well,
because ``[tool.ty.environment] python`` names it; run the task once to create it.

Set ``UV_PYTHON`` to choose the interpreter a task runs on, for example
``UV_PYTHON=3.12 uv run --no-sync poe test-sphinx8``.
uv downloads an interpreter it does not have, so no separate version manager is needed.
Give the outer ``uv run`` the ``--no-sync`` flag in that form: without it, uv also rebuilds
the default ``.venv`` on that interpreter (``uv sync --python 3.13`` puts it back).

Build docs
----------

To build the **Sphinx-Needs** documentation stored under ``/docs``, run:

.. code-block:: bash

   # Build HTML pages with the furo theme
   uv run poe docs

   # ... and first remove all old build files
   uv run poe docs-clean

.. note::

   Building the documentation requires Python >= 3.11;
   set ``UV_PYTHON`` (with ``uv run --no-sync``) if your default interpreter is older.

The other themes have a task each — ``docs-alabaster``, ``docs-im``, ``docs-pds`` and
``docs-rtd`` — and the link checker is its own task:

.. code-block:: bash

   # Check links in the documentation
   uv run poe docs-linkcheck


Running Tests
-------------

Run the tests against the newest supported sphinx with:

.. code-block:: bash

   uv run poe test

The CI matrix tests three sphinx versions, and each is a task of its own —
``test-sphinx7``, ``test-sphinx8``, ``test-sphinx9``.
Every one of them is exactly what CI runs, so a failing cell can be reproduced locally:

.. code-block:: bash

   UV_PYTHON=3.12 uv run --no-sync poe test-sphinx8 tests/test_basic_doc.py

Note some tests use `syrupy <https://github.com/tophat/syrupy>`__ to perform snapshot testing.
These snapshots can be updated by running:

.. code-block:: bash

   uv run poe test --snapshot-update

Running JS Testcases with PyTest
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Setup Cypress Locally**

* Install Node JS on your computer and ensure it can be accessed through the CMD.
* Install Cypress using the npm package manager by running ``npm install cypress``. Visit this link for more information on `how to install Cypress <https://docs.cypress.io/guides/getting-started/installing-cypress>`_.
* Verify if Cypress is installed correctly and is executable by running: ``npx cypress verify``. Get out this page for more information about `Cypress commandline <https://docs.cypress.io/guides/guides/command-line>`_.
* If everything is successful then we can use Cypress.

**Enable Cypress Test in Python Test Files**

Under the ``js_test`` folder, you can save your Cypress JS test files (files should end with: ``*.cy.js``). For each Cypress JS test file, you will need to write the Cypress JS test cases in the file. You can read more from the `Cypress Docs <https://docs.cypress.io/>`_. You can also check the ``tests/js_test/sn-collapse-button.cy.js`` file as reference.

In your Python test files, you must mark every JS related test case with the marker - ``jstest`` and you must include the ``spec_pattern`` key-value pair as part of the ``test_app`` fixture parameter.
Also, you need to pass the ``test_server`` fixture to your test function for it to use the automated HTTP test server. For example, your test case could look like this:

.. code-block:: python

    # tests/test_sn_collapse_button.py

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
    def test_collapse_button_in_docs(test_app, test_server):
        ...

.. note::

    The ``spec_pattern`` key is required to ensure Cypress locates your test files or folder. Visit this link for more info on how to set the `spec_pattern <https://docs.cypress.io/guides/guides/command-line#cypress-run-spec-lt-spec-gt>`_.

After you set the ``spec_pattern`` key-value pair as part of the ``test_app`` fixture parameter, you can call ``app.test_js()`` in your Python test case to run a JS test for the ``spec_pattern`` you provided. For example, you can use ``app.test_js()`` like below:

.. code-block:: python

    # tests/test_sn_collapse_button.py

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
    def test_collapse_button_in_docs(test_app, test_server):
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

You can run the ``make test-js`` command to check all JS testcases.

.. note::

    The ``http_server`` process invoked by the ``make test-js`` command may not terminate properly in some instances.
    Kindly check your system's monitoring app to end the process if not terminated automatically.

Benchmarks
----------

**Sphinx-Needs** own documentation is used for creating a benchmark for each PR.
If the runtime takes 10% longer as the previous ones, the benchmark test will fail.

Benchmark test cases are available under ``tests/benchmarks``.

The results for each PR/commit get added to a chart, which is available under
http://useblocks.com/sphinx-needs/bench/index.html.

The benchmark data is stored on the ``benchmarks`` branch, which is also used by github-pages as
source.

Publishing a new release
------------------------
There is a release pipeline installed for the CI.

This gets triggered automatically, if a tag is created and pushed.
The tag must follow the format: ``[0-9].[0-9]+.[0-9]``. Otherwise the release jobs won't trigger.

The release jobs will build the source and wheel distribution and try to upload them.

.. Include our contributors and maintainers.
.. include:: ../AUTHORS
