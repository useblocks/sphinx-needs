"""Sphinx-Test-Reports.

``setup`` is resolved lazily (PEP 562) so that importing a submodule of this
package does not import Sphinx: the ``test-reports`` command and
:mod:`sphinxcontrib.test_reports.projectconfig` are used where the
documentation toolchain is not installed -- it is the ``sphinx`` extra of the
package, not a dependency -- and every import of a submodule runs this file
first. Sphinx still finds ``setup`` through normal attribute access when it
loads this package as an extension.

Resolving ``setup`` is also where the toolchain is checked. An extra is opt-in,
so a project that installs the bare package into an environment already holding
an older Sphinx or sphinx-needs never shows pip the extra's version floors;
:mod:`sphinxcontrib.test_reports.toolchain` enforces them here instead, with
the install line in the message.
"""

__all__ = ["setup"]


def __getattr__(name: str) -> object:
    if name != "setup":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    from sphinxcontrib.test_reports.toolchain import INSTALL_HINT, unmet_requirements

    unmet = unmet_requirements()
    if unmet:
        # Before the import: an outdated sphinx-needs may well import and fail
        # only later, inside a directive, with a traceback that does not say
        # why. Sphinx fetches `setup` with getattr(), which only tolerates
        # AttributeError, so the error reaches the user as it is raised here.
        message = (
            f"Could not load extension {__name__}: {'; '.join(unmet)}. "
            f"Install the Sphinx extension's dependencies with: {INSTALL_HINT}"
        )
        try:
            from sphinx.errors import ExtensionError
        except ImportError:
            raise ImportError(message) from None
        raise ExtensionError(message)

    try:
        from sphinxcontrib.test_reports.test_reports import setup
    except ImportError as error:
        # Sphinx wraps an ImportError from importing the *package* in a clean
        # "Could not import extension" message, but fetches `setup` with
        # getattr(), which only tolerates AttributeError. Resolving lazily
        # would let a missing sphinx-needs escape as a raw traceback, so the
        # message Sphinx would have produced is raised here instead -- when
        # Sphinx is there to receive it -- naming the extra that installs the
        # toolchain, the likely cause. The wrapped exception goes in the second
        # argument only: ExtensionError.__str__ renders it as
        # "(exception: ...)", so spelling it out in the message too would print
        # it twice.
        try:
            from sphinx.errors import ExtensionError
        except ImportError:
            raise error from None
        raise ExtensionError(
            f"Could not import extension {__name__}; the Sphinx extension's "
            f"dependencies are an extra, install them with: {INSTALL_HINT}",
            error,
        ) from error

    return setup
