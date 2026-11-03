"""sphinx-ub-directives: directive presets and declared template directives, read from
``ubproject.toml``, for Sphinx.

The normative specification is ``design/directives-contract.md``; its executable half is
the two conformance corpora under ``tests/fixtures/``.
"""

from __future__ import annotations

from typing import Any

from sphinx.application import Sphinx

__version__ = "0.1.0"

__all__ = ["__version__", "setup"]


def setup(app: Sphinx) -> dict[str, Any]:
    """Register the extension with Sphinx."""
    from . import _config, _presets, _refusal, _templates, _ub_template

    _config.setup(app)
    _refusal.install()
    # after every extension's `config-inited`, before any document is read (contract §2.2);
    # with sphinx-needs, after its `create_schema` (priority 500) builds this build's schema
    # presets before declared templates in either phase, so a preset keeps its name
    app.connect("builder-inited", _presets.register_early)
    app.connect("builder-inited", _templates.register_early)
    app.connect("env-before-read-docs", _presets.register_with_needs, priority=600)
    app.connect("env-before-read-docs", _templates.register_with_needs, priority=610)
    app.connect("env-before-read-docs", _presets.check_replaced, priority=700)
    app.add_directive(_ub_template.NAME, _ub_template.UbTemplate)
    return {
        "version": __version__,
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
