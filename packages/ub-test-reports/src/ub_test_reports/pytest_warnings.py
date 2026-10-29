"""The warning class of the pytest plugin, in a module of its own.

``ignore::ub_test_reports.pytest_warnings.TestReportsConfigWarning`` is the
``filterwarnings`` line that silences the plugin's start-up notice. pytest resolves a
filter's category by importing the module it names, and from pytest 9.2 on it does so
BEFORE it loads the ``-p`` plugins. A filter naming the class through
:mod:`ub_test_reports.pytest_plugin` would import the plugin first, and ``-p`` would
then find it imported already and warn that it cannot rewrite its asserts -- which,
under ``filterwarnings = error``, stops pytest at start-up. So this module imports
pytest and nothing of the plugin; :mod:`ub_test_reports.pytest_plugin` re-exports the
class, the same object, so a filter written against the old path still names it.
"""

from __future__ import annotations

import pytest

__all__ = ["TestReportsConfigWarning"]


class TestReportsConfigWarning(pytest.PytestWarning):
    """A run configured such that the plugin cannot write the full XML shape.

    Issued once at start-up. Where the project turns warnings into errors
    (``filterwarnings = error``, ``-W error``) it becomes a clean usage error
    rather than a traceback;
    ``ignore::ub_test_reports.pytest_warnings.TestReportsConfigWarning``
    silences it.
    """
