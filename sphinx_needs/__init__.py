"""Sphinx needs extension for managing needs/requirements and specifications"""

__version__ = "4.1.0"


def setup(app):  # type: ignore[no-untyped-def]
    from sphinx_needs.needs import setup as needs_setup

    return needs_setup(app)
