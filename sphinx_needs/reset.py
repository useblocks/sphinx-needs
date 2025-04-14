"""Reset global Sphinx Needs variables."""

from sphinx_needs.directives.need import NeedDirective


def sphinx_needs_reset() -> None:
    """Reset all global Sphinx Needs variables."""
    NeedDirective.reset()
