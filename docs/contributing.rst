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

To develop **Sphinx-Needs**  it can be installed, with development extras, into an existing Python environment using ``pip``:

.. code-block:: bash

   pip install sphinx-needs[test,benchmark,docs]

or using `uv <https://docs.astral.sh/uv/>`__ to install the dependencies into an isolated environment:

.. code-block:: bash

   uv sync

To run the formatting and linting suite, `pre-commit <https://pre-commit.com/>`__ is used:

.. code-block:: bash

   pre-commit install  # to auto-run on every commit
   pre-commit run --all-files  # to run manually

To run testing and documentation building, `tox <https://tox.readthedocs.io/>`__ is used:

.. code-block:: bash

   tox -av  # to see all environments

Note, it is recommended to also install the `tox-uv <https://github.com/tox-dev/tox-uv>`__ plugin, which will use ``uv`` to create isolated environments faster, and to use `pyenv <https://github.com/pyenv/pyenv>`__ to manage multiple Python versions.

Build docs
----------

To build the **Sphinx-Needs** documentation stored under ``/docs``, run:

.. code-block:: bash

   # Build HTML pages with the furo theme,
   # and first remove all old build files
   CLEAN=true tox -e docs-furo

or to build with a different builder:

.. code-block:: bash

   # Check links in the documentation
   CLEAN=true BUILDER=linkcheck tox -e docs-furo


Running Tests
-------------

You can either run the tests directly using ``pytest``, in an existing environment:

.. code-block:: bash

   pytest tests/

Or use tox (recommended):

.. code-block:: bash

   tox -e py310

Note some tests use `syrupy <https://github.com/tophat/syrupy>`__ to perform snapshot testing.
These snapshots can be updated by running:

.. code-block:: bash

   pytest tests/ --snapshot-update

.. hint::

   Please be sure to have the dependencies of the official documentation also installed:

   .. code-block:: bash

      pip install -r docs/requirements.txt

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
