"""Minimal host Sphinx project for tests.

Tests append a ``mounts = [...]`` value to this file via
``tests.conftest.patch_conf_py``.
"""

project = "host"
author = "tests"
extensions = ["sphinx_mounts"]
exclude_patterns: list[str] = []
master_doc = "index"
