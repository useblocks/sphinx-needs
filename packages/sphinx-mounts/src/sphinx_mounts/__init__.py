"""sphinx-mounts: mount external RST source trees into a Sphinx build."""

__version__ = "0.3.1"

from sphinx_mounts.extension import setup

__all__ = [
    "__version__",
    "setup",
]
