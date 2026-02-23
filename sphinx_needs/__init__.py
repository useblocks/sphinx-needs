"""Sphinx needs extension for managing needs/requirements and specifications"""

__version__ = "7.0.0"


def setup(app):  # type: ignore[no-untyped-def]
    from sphinx_needs.needs import setup as needs_setup

    return needs_setup(app)
