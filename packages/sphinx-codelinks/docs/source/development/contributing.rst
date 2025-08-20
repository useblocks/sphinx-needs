Contributing
============

This page provides a guide for developers wishing to contribute to ``Sphinx-CodeLinks``.

Bugs, Features and PRs
----------------------

For **bug reports** and well-described **technical feature requests**, please use our issue tracker:
https://github.com/useblocks/sphinx-codelinks/issues

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

``CodeLinks`` uses `rye <https://rye.astral.sh/>`_ to manage the repository.

For development, use the following command to install Python dependencies into the virtual environment.

.. code-block:: bash

   rye sync

Formatting, Linting and Typing
------------------------------

To run the formatting and linting, pre-commit is used:

.. code-block:: bash

   pre-commit install # to auto-run on every commit
   pre-commit run --all-files # to run manually

The CI also checks typing. Use the following command locally to see if your code is well-typed:

.. code-block:: bash

   rye run mypy:all

Build docs
----------

To build the documentation stored in ``docs``, run:

.. code-block:: bash

   rye run docs

Test Cases
----------

To run test cases locally:

.. code-block:: bash

   rye test -a

Note some tests use `syrupy <https://github.com/tophat/syrupy>`__ to perform snapshot testing.
These snapshots can be updated by running:

.. code-block:: bash

   pytest tests/ --snapshot-update
