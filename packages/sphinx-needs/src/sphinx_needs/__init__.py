"""Sphinx needs extension for managing needs/requirements and specifications"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sphinx.application import Sphinx

__version__ = "9.0.0"


def setup(app: Sphinx) -> dict[str, Any]:
    from sphinx_needs.needs import setup as needs_setup

    return needs_setup(app)
