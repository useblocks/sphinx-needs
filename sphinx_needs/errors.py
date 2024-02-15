from __future__ import annotations

try:
    # Sphinx 3.0
    from sphinx.errors import NoUri
except ImportError:
    # Sphinx < 3.0
    from sphinx.environment import NoUri  # type: ignore[no-redef, attr-defined]

__all__ = ["NoUri"]
