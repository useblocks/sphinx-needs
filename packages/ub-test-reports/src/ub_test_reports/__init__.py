"""ub-test-reports: test results as needs, without Sphinx.

The report parsers, the result vocabulary, the deterministic case IDs, the
``[test_reports]`` model of ``ubproject.toml``, the needs.json converter behind the
``test-reports`` command, and the pytest plugin (``-p ub_test_reports.pytest_plugin``).
The modules are the API; this file only carries the version.

**Nothing in this package may import Sphinx, sphinx-needs or docutils** -- not at module
level and not in a function body. sphinx-test-reports, the Sphinx extension, depends on
this package, never the other way round.
"""

__all__ = ["__version__"]

#: Checked against ``[project] version`` by ``check_workspace.py`` and stamped by
#: ``poe bump``.
__version__ = "1.0.0"
