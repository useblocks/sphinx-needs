from rich.console import Console
from rich.text import Text
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
