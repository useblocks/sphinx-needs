"""Sphinx-Test-Reports.

``setup`` is resolved lazily (PEP 562) so that importing a submodule of this
package does not import Sphinx. The converter CLI and the modules it uses must
stay usable as a build action, without the documentation toolchain installed;
Sphinx still finds ``setup`` through normal attribute access when it loads this
package as an extension.
"""

__all__ = ["setup"]


def __getattr__(name: str) -> object:
    if name == "setup":
        from sphinxcontrib.test_reports.test_reports import setup

        return setup
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
