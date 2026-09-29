"""Deprecated: the old name of :mod:`sphinx_test_reports.jsonparser`, removed in 4.0.

Importing it gives the real module -- the same object, so classes, ``mock.patch``
targets and warning filters written against the old path keep working -- and one
:class:`FutureWarning` attributed to the importing line. See this package's
``__init__`` for why these names, and only these, are aliased.
"""

import sys
import warnings

from sphinx_test_reports import jsonparser as _module

warnings.warn(
    "sphinxcontrib.test_reports.jsonparser has moved to sphinx_test_reports.jsonparser; "
    "import it from there. The old name stops working in sphinx-test-reports 4.0.",
    FutureWarning,
    # 2 is the importer: `warnings` skips importlib's own frames on the way up
    stacklevel=2,
)

# Replaced, not re-exported: importlib hands back whatever sys.modules holds under
# this name once the file has run, and leaves the real module's `__spec__` alone.
sys.modules[__name__] = _module
