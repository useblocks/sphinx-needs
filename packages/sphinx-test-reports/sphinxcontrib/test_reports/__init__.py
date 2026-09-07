"""Sphinx-Test-Reports.

``setup`` is resolved lazily (PEP 562) so that importing a submodule of this
package does not import Sphinx: :mod:`sphinxcontrib.test_reports.projectconfig`
is read by consumers that are not a documentation build, in environments where
the documentation toolchain is not installed, and every import of it runs this
file first. Sphinx still finds ``setup`` through normal attribute access when it
loads this package as an extension.
"""

__all__ = ["setup"]


def __getattr__(name: str) -> object:
    if name == "setup":
        try:
            from sphinxcontrib.test_reports.test_reports import setup
        except ImportError as error:
            # Sphinx wraps an ImportError from importing the *package* in a
            # clean "Could not import extension" message, but fetches `setup`
            # with getattr(), which only tolerates AttributeError. Resolving
            # lazily would let a missing sphinx-needs escape as a raw
            # traceback, so the message Sphinx would have produced is raised
            # here instead -- when Sphinx is there to receive it. The wrapped
            # exception goes in the second argument only: ExtensionError.__str__
            # renders it as "(exception: ...)", so spelling it out in the
            # message too would print it twice.
            try:
                from sphinx.errors import ExtensionError
            except ImportError:
                raise error from None
            raise ExtensionError(
                f"Could not import extension {__name__}", error
            ) from error

        return setup
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
