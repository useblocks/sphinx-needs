Contributing
============

This page provides a guide for developers wishing to contribute to ``Sphinx-CodeLinks``.

Bugs, Features and PRs
----------------------

For **bug reports** and well-described **technical feature requests**, please use our issue tracker:
https://github.com/useblocks/sphinx-needs/issues -- Sphinx-CodeLinks is developed in the
``useblocks/sphinx-needs`` monorepo, under ``packages/sphinx-codelinks/``. Pick
``sphinx-codelinks`` from the issue form's *Package* dropdown.

If you have already created a PR, you can send it in. Our CI workflow will check (tests and code styles)
and a maintainer will perform a review before we can merge it.
Your PR should conform with the following rules:

- A meaningful description or link, which describes the change
- The changed code (for sure :) )
- Test cases for the change (important!)
- Updated documentation, if behavior gets changed or new options/directives are introduced.
- Update of docs/changelog.rst.

Install Dependencies
--------------------

Development tasks are `uv <https://docs.astral.sh/uv/>`_ and
`poethepoet <https://poethepoet.natn.io/>`_ tasks, run from the **repository root**.
One sync installs every package in the workspace and the shared test tooling:

.. code-block:: bash

   uv sync --frozen

Formatting, Linting and Typing
------------------------------

Formatting and linting are one hook set over the whole repository:

.. code-block:: bash

   uv run poe lint

Type checking runs ty against the oldest supported Sphinx:

.. code-block:: bash

   uv run poe typecheck

Build docs
----------

To build the documentation stored in ``packages/sphinx-codelinks/docs``, run:

.. code-block:: bash

   uv run poe docs-codelinks         # or docs-codelinks-clean to rebuild from scratch

Test Cases
----------

To run test cases locally:

.. code-block:: bash

   uv run poe test-codelinks

The task adds the ``codelinks-libclang`` dependency group, which is where the optional
preprocessor-aware C/C++ engine comes from -- without it 56 tests skip rather than run.
``test-codelinks-sphinx7``, ``-sphinx8`` and ``-sphinx9`` run one matrix cell each.

Note some tests use `syrupy <https://github.com/tophat/syrupy>`__ to perform snapshot testing.
These snapshots can be updated by running:

.. code-block:: bash

   uv run poe test-codelinks -- --snapshot-update
