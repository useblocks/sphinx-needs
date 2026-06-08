import logging
from typing import Protocol

from rich.console import Console
from rich.text import Text
from sphinx import version_info as _sphinx_version_info
from sphinx.util import logging as sphinx_logging
import typer


class Logger:
    __slots__ = ("console", "err_console", "quiet", "verbose")

    def __init__(self, *, verbose: bool = False, quiet: bool = False) -> None:
        self.verbose = verbose
        self.quiet = quiet
        self.console = Console()
        self.err_console = Console(stderr=True)

    def configure(self, verbose: bool = False, quiet: bool = False) -> None:
        self.verbose = verbose
        self.quiet = quiet

    def debug(
        self,
        *msg: str | Text,
        style: str | None = typer.colors.BRIGHT_BLACK,
        highlight: bool = False,
        markup: bool = False,
        console: Console | None = None,
    ) -> None:
        """Print a debug message.

        Will only be shown if verbose mode is enabled and not in quiet mode.
        """
        if self.verbose and not self.quiet:
            (console or self.console).print(
                *msg, style=style, highlight=highlight, markup=markup
            )

    def info(
        self,
        *msg: str | Text,
        style: str | None = None,
        highlight: bool = False,
        markup: bool = False,
        no_wrap: bool | None = None,
        console: Console | None = None,
    ) -> None:
        """Print an informational message.

        Will be suppressed in quiet mode.
        """
        if not self.quiet:
            (console or self.console).print(
                *msg, style=style, highlight=highlight, markup=markup, no_wrap=no_wrap
            )

    def result(
        self,
        *msg: str | Text,
        style: str | None = None,
        highlight: bool = False,
        markup: bool = False,
        console: Console | None = None,
    ) -> None:
        """Print a result message, like info but ignores quiet mode."""
        (console or self.console).print(
            *msg, style=style, highlight=highlight, markup=markup
        )

    def warning(
        self,
        *msg: str | Text,
        style: str | None = typer.colors.YELLOW,
        highlight: bool = False,
        markup: bool = False,
        console: Console | None = None,
    ) -> None:
        """Print a warning message."""
        (console or self.console).print(
            *msg, style=style, highlight=highlight, markup=markup
        )

    def error(
        self,
        *msg: str | Text,
        style: str | None = typer.colors.RED,
        highlight: bool = False,
        markup: bool = False,
        console: Console | None = None,
    ) -> None:
        """Print an error message."""
        (console or self.err_console).print(
            *msg, style=style, highlight=highlight, markup=markup
        )


logger = Logger()


# --------------------------------------------------------------------------- #
# Environment-aware logging facade
#
# The ``analyse`` layer is shared between the standalone CLI and the Sphinx
# extension. Instead of installing handlers on its own loggers (which leaks
# routine INFO progress onto stderr; see issue #72), the layer logs through
# :func:`get_logger`, and the active *frontend* selects where records go:
#
# * default (plain library)  -> stdlib logging with no handler installed, so
#   INFO is dropped silently and WARNING+ falls back to stderr via
#   ``logging.lastResort``.
# * CLI    -> the rich :data:`logger` above (INFO to stdout, WARNING to stderr,
#   honouring ``--verbose``/``--quiet``).
# * Sphinx -> ``sphinx.util.logging`` (respects verbosity, colour,
#   ``suppress_warnings`` and the Sphinx warning stream).
# --------------------------------------------------------------------------- #


class _Backend(Protocol):
    """Where the ``analyse`` layer's log records are routed.

    Arguments are positional-only so each backend may ignore (and underscore)
    the ones it does not need.
    """

    def debug(self, name: str, msg: str, location: str | None, /) -> None: ...

    def info(self, name: str, msg: str, location: str | None, /) -> None: ...

    def warning(
        self, name: str, msg: str, subtype: str, location: str | None, /
    ) -> None: ...


class _StdlibBackend:
    """Default backend: emit through stdlib logging, install nothing.

    A library must not configure handlers on its own loggers. With no handler,
    INFO records are dropped and WARNING+ reaches stderr via ``lastResort``.
    """

    def debug(self, name: str, msg: str, _location: str | None, /) -> None:
        logging.getLogger(name).debug(msg)

    def info(self, name: str, msg: str, _location: str | None, /) -> None:
        logging.getLogger(name).info(msg)

    def warning(
        self, name: str, msg: str, _subtype: str, _location: str | None, /
    ) -> None:
        logging.getLogger(name).warning(msg)


class _CliBackend:
    """CLI backend: route through the rich :data:`logger`.

    The summary is INFO (stdout, hidden by ``--quiet``); the breakdown is DEBUG
    (stdout, shown only with ``--verbose``); warnings go to stderr.
    """

    def debug(self, _name: str, msg: str, _location: str | None, /) -> None:
        logger.debug(msg)

    def info(self, _name: str, msg: str, _location: str | None, /) -> None:
        logger.info(msg)

    def warning(
        self, _name: str, msg: str, _subtype: str, _location: str | None, /
    ) -> None:
        # reserve stderr for warnings/errors (the rich logger prints to stdout
        # by default; route this to the error console explicitly)
        logger.warning(msg, console=logger.err_console)


class _SphinxBackend:
    """Sphinx backend: route through ``sphinx.util.logging``.

    The summary is INFO (shown in a normal build's status stream); the breakdown
    is VERBOSE (shown only with ``sphinx-build -v``); warnings carry
    ``type="codelinks"`` plus a subtype so they are suppressible via
    ``suppress_warnings`` and rendered on the Sphinx warning stream.
    """

    # Sphinx >= 8 renders the warning type itself; older versions need it
    # appended to the message (mirrors sphinx-needs' logging helper).
    _show_warning_types = _sphinx_version_info >= (8,)

    def debug(self, name: str, msg: str, _location: str | None, /) -> None:
        sphinx_logging.getLogger(name).verbose(msg)

    def info(self, name: str, msg: str, _location: str | None, /) -> None:
        sphinx_logging.getLogger(name).info(msg)

    def warning(
        self, name: str, msg: str, subtype: str, location: str | None, /
    ) -> None:
        message = msg
        if not self._show_warning_types:
            message += f" [codelinks.{subtype}]" if subtype else " [codelinks]"
        sphinx_logging.getLogger(name).warning(
            message,
            type="codelinks",
            subtype=subtype,
            location=location,
        )


class _Dispatch:
    """Holds the active backend, swapped by the ``configure_*`` entry points."""

    def __init__(self) -> None:
        self.backend: _Backend = _StdlibBackend()


_dispatch = _Dispatch()


class CodelinksLogger:
    """Thin proxy used by the ``analyse`` layer.

    The active backend is resolved at *call* time so that an entry point may
    select the frontend after the ``analyse`` modules have been imported.
    """

    __slots__ = ("_name",)

    def __init__(self, name: str) -> None:
        self._name = name

    def debug(self, msg: str, *, location: str | None = None) -> None:
        _dispatch.backend.debug(self._name, msg, location)

    def info(self, msg: str, *, location: str | None = None) -> None:
        _dispatch.backend.info(self._name, msg, location)

    def warning(
        self, msg: str, *, subtype: str = "", location: str | None = None
    ) -> None:
        _dispatch.backend.warning(self._name, msg, subtype, location)


def get_logger(name: str) -> CodelinksLogger:
    """Return a logger that routes to whichever frontend is configured."""
    return CodelinksLogger(name)


def configure_cli(verbose: bool = False, quiet: bool = False) -> None:
    """Select the CLI frontend and configure the rich logger's verbosity."""
    logger.configure(verbose=verbose, quiet=quiet)
    _dispatch.backend = _CliBackend()


def configure_sphinx() -> None:
    """Select the Sphinx frontend (``sphinx.util.logging``)."""
    _dispatch.backend = _SphinxBackend()


def reset() -> None:
    """Restore the default (plain library) backend. Mainly for tests."""
    _dispatch.backend = _StdlibBackend()
