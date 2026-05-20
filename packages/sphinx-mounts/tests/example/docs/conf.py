"""Minimal host project for the sphinx-mounts example.

All mount declarations live in ``ubproject.toml`` next to this file;
``conf.py`` only needs to register ``sphinx_mounts`` (and
``myst_parser`` for the Markdown bundle).
"""

project = "sphinx-mounts example"
author = "useblocks"
extensions = ["sphinx_mounts", "myst_parser"]
exclude_patterns: list[str] = ["_build"]
master_doc = "index"
