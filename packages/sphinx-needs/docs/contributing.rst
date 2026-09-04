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

To develop **Sphinx-Needs**, use `uv <https://docs.astral.sh/uv/>`__ to install the
project and its development dependencies into an isolated environment:

.. code-block:: bash

   uv sync

.. note::

   Run it from the repository root. This repository is a uv workspace: the test tooling is a
   dependency group of the workspace root, which is included in the root's default ``dev``
   group, so no group has to be named. Syncing from inside ``packages/sphinx-needs`` instead
   installs the package alone, without ``pytest``.

   The interpreter comes from the ``.python-version`` file at the repository root, so every
   contributor gets the same one; uv downloads it if the machine does not have it. If you use
   pyenv, run ``pyenv install 3.13`` once, or its shims will report the version as missing
   inside this repository.

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
``uv run poe typecheck-needs`` is one of those tasks: it installs the ``typing`` dependency
group — the oldest supported Sphinx and Docutils, plus ty itself — into ``.venvs/typing``
and checks against it, which is what CI and the prek ``ty`` hook do too.
Running ``ty`` by hand, or through an editor extension, uses ``.venvs/typing`` as well,
because ``[tool.ty.environment] python`` names it; run the task once to create it.

Set ``UV_PYTHON`` to choose the interpreter a task runs on, for example
``UV_PYTHON=3.12 uv run --no-sync poe test-needs-sphinx8``.
uv downloads an interpreter it does not have, so no separate version manager is needed.
Give the outer ``uv run`` the ``--no-sync`` flag in that form: without it, uv also rebuilds
the default ``.venv`` on that interpreter (``uv sync --python 3.13`` puts it back).

Build docs
----------

To build the **Sphinx-Needs** documentation stored under ``/packages/sphinx-needs/docs``, run:

.. code-block:: bash

   # Build HTML pages with the furo theme
   uv run poe docs-needs

   # ... and first remove all old build files
   uv run poe docs-needs-clean

The other themes have a task each — ``docs-needs-alabaster``, ``docs-needs-im``, ``docs-needs-pds``
and ``docs-needs-rtd`` — and the link checker is its own task:

.. code-block:: bash

   # Check links in the documentation
   uv run poe docs-needs-linkcheck


Running Tests
-------------

Run the tests against the newest supported sphinx with:

.. code-block:: bash

   uv run poe test-needs

The CI matrix tests three sphinx versions, and each is a task of its own —
``test-needs-sphinx7``, ``test-needs-sphinx8``, ``test-needs-sphinx9``.
Every one of them is exactly what CI runs, so a failing cell can be reproduced locally:

.. code-block:: bash

   UV_PYTHON=3.12 uv run --no-sync poe test-needs-sphinx8 tests/test_basic_doc.py

Note some tests use `syrupy <https://github.com/tophat/syrupy>`__ to perform snapshot testing.
These snapshots can be updated by running:

.. code-block:: bash

   uv run poe test-needs --snapshot-update

Running the browser tests
~~~~~~~~~~~~~~~~~~~~~~~~~

The tests marked ``jstest`` drive a real browser through
`pytest-playwright <https://playwright.dev/python/docs/intro>`__; ``poe test-needs``
excludes them. The browser binary is not a Python package, so download it once per machine:

.. code-block:: bash

   uv run poe install-browser

That is ``playwright install chromium``, which lands in ``~/.cache/ms-playwright``
(``~/Library/Caches/ms-playwright`` on macOS), or in ``PLAYWRIGHT_BROWSERS_PATH`` if your
environment sets one -- some prepared container images do, and then a browser they baked in
is only found if its revision is the one this playwright pins. Then:

.. code-block:: bash

   uv run poe test-needs-js

To skip the download altogether and drive a Chrome that is already on the machine, pass
pytest-playwright's own flag: ``uv run poe test-needs-js --browser-channel chrome``.

A browser test builds its project with the usual ``test_app`` fixture, opens the built page
over ``file://`` -- nothing on the page fetches, so no server is involved -- and asserts on
it with Playwright's ``expect``:

.. code-block:: python

    # tests/test_sn_collapse_button.py

    from pathlib import Path

    import pytest
    from playwright.sync_api import Page, expect


    @pytest.mark.jstest
    @pytest.mark.parametrize(
        "test_app",
        [{"buildername": "html", "srcdir": "doc_test/doc_basic"}],
        indirect=True,
    )
    def test_something(test_app, page: Page):
        test_app.build()
        page.goto(Path(test_app.outdir, "index.html").as_uri())
        expect(page.locator("table.need")).to_have_count(2)  # locators are sets

Register ``page.on("pageerror", ...)`` before ``page.goto`` if the test should also assert
that the page raised nothing.

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
