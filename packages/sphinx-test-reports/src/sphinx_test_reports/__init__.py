"""Sphinx-Test-Reports, the Sphinx extension.

The converter, the pytest plugin, the parsers and the ``[test_reports]`` model are
``ub-test-reports`` (:mod:`ub_test_reports`), which this package depends on; what is here
is the extension that turns the same reports into needs inside a Sphinx build. Its
dependencies -- Sphinx, docutils, sphinx-needs and the core -- are hard requirements, so
``setup`` is imported eagerly.
"""

__all__ = ["__version__", "setup"]

#: Checked against ``[project] version`` by ``check_workspace.py`` and stamped by
#: ``poe bump``; the extension's metadata reads it from here.
__version__ = "2.0.0"

# The order is load-bearing: `test_reports` imports `__version__` from this package while
# this import runs, so the literal above has to be assigned before it.
from sphinx_test_reports.test_reports import setup
