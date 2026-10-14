"""Sphinx needs extension for managing needs/requirements and specifications"""

__version__ = "9.0.0"


def setup(app):
    from sphinx_needs.needs import setup as needs_setup

    return needs_setup(app)
