"""Sphinx project that mounts the Bazel genrule output.

Bazel writes outputs to ``<workspace>/bazel-bin/docs/`` (a symlink to the
real output base). sphinx-mounts reads those .rst files in place. The
mount mapping itself lives in ``ubproject.toml`` next to this file — see
that file for the declarative configuration.
"""

project = "bazel-mounted"
author = "tests"
extensions = ["sphinx_mounts"]
exclude_patterns: list[str] = []
master_doc = "index"
