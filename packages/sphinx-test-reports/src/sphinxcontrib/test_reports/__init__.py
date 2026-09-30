"""The pre-3.0 name of sphinx-test-reports, kept working until 4.0.

The package is :mod:`sphinx_test_reports` now. Four old names still resolve, each
with a warning that names the new one:

* this package, as a Sphinx extension (``extensions = ["sphinxcontrib.test_reports"]``),
  which warns through Sphinx's logger, type ``test_reports.deprecated`` -- the channel a
  documentation build shows, fails under ``-W`` and silences with ``suppress_warnings``;
* ``pytest_plugin``, ``junitparser`` and ``jsonparser``, one file each next to this
  one, which put the REAL module into :data:`sys.modules` under the old name and raise
  one :class:`FutureWarning` per process (not a :class:`DeprecationWarning`, which
  Python's default filters hide outside ``__main__``). It is attributed to the
  ``import`` statement that names the module; ``importlib.import_module``, and pytest
  when it loads a ``-p`` or ``pytest_plugins`` name, are frames of their own and take
  the attribution instead.

Every other ``sphinxcontrib.test_reports.<module>`` fails as an ordinary import
error: there is deliberately no finder here that would alias the rest.

``setup`` is resolved lazily (PEP 562), so importing one of the module aliases does
not import Sphinx: ``junitparser`` and ``pytest_plugin`` are used where the
documentation toolchain is not installed, and every import of a submodule runs this
file first.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sphinx.application import Sphinx

__all__ = ["setup"]

#: The extension this name stands for.
_NEW_NAME = "sphinx_test_reports"


def __getattr__(name: str) -> object:
    if name != "setup":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return _setup


def _setup(app: Sphinx) -> dict[str, Any]:
    from sphinx.util import logging

    logging.getLogger(__name__).warning(
        f"the extension name {__name__!r} is deprecated: write {_NEW_NAME!r} in the "
        "extensions list of conf.py instead. The old name stops working in "
        "sphinx-test-reports 4.0.",
        type="test_reports",
        subtype="deprecated",
    )
    # After the warning, so a toolchain error from the real `setup` has the deprecation
    # line above it. Through Sphinx rather than by calling the real `setup`: a conf.py
    # that lists both names then registers the extension once, and the real package's
    # own lazy `setup` -- with its toolchain check -- is what runs.
    app.setup_extension(_NEW_NAME)
    extension = app.extensions[_NEW_NAME]
    # `Extension` pops these three out of the metadata it keeps; hand back all of it.
    return {
        **extension.metadata,
        "version": extension.version,
        "parallel_read_safe": extension.parallel_read_safe,
        "parallel_write_safe": extension.parallel_write_safe,
    }
