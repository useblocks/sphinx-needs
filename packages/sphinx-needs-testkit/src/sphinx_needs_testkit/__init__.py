"""Shared pytest fixtures and helpers for this workspace's suites.

Never released. It is a workspace member so that its code is IMPORTABLE -- a
``conftest.py`` can share fixtures and hooks and nothing else, while half of what is
shared here (the warning normalisation, the renderer resolution) is a plain function that
a ``make_app`` caller, a subprocess test or another package's suite calls directly.

Two surfaces:

* **the plugin**, ``sphinx_needs_testkit.fixtures``, which a suite loads with one line in
  its own ``tests/conftest.py``::

      pytest_plugins = ["sphinx.testing.fixtures", "sphinx_needs_testkit.fixtures"]

* **the functions re-exported here**, which are imported by name::

      from sphinx_needs_testkit import assert_no_warnings, build_warnings

  The modules they live in are private (``_warnings``, ``_plantuml``, ``_srcdir``,
  ``_snapshots``, ``_subprocess``): where a helper sits is this package's business, and
  one import path is one thing to rewrite when that changes. This module deliberately does
  NOT import the plugin: a consumer's ``conftest.py`` imports the package by name, and
  pytest can only rewrite assertions in a plugin module it imports first -- importing it
  here would earn every session a ``PytestAssertRewriteWarning`` instead.

Nothing here imports a sibling: this must load for sphinx-mounts' and sphinx-codelinks'
suites too, so anything that knows about needs stays in sphinx-needs' own conftest.
"""

from __future__ import annotations

from ._plantuml import (
    make_plantuml_inert,
    plantuml_conf,
    require_plantuml_extension,
    resolve_plantuml_command,
    workspace_plantuml_jar,
)
from ._snapshots import DoctreeSnapshotExtension
from ._srcdir import (
    copy_srcdir_to_tmpdir,
    copy_test_utils,
    create_src_files_in_tmpdir,
    generate_random_string,
)
from ._subprocess import assert_no_bare_sphinx_build, sphinx_build_command
from ._warnings import assert_no_warnings, build_warnings, warning_count

# never released, so there is nothing for the number to track -- but
# `tools/src/sn_tools/check_workspace.py` check (5) holds it equal to `[project] version`
# in `pyproject.toml` all the same, because that check is on every non-virtual member and
# this one claims no exemption
__version__ = "0"

__all__ = [
    "DoctreeSnapshotExtension",
    "assert_no_bare_sphinx_build",
    "assert_no_warnings",
    "build_warnings",
    "copy_srcdir_to_tmpdir",
    "copy_test_utils",
    "create_src_files_in_tmpdir",
    "generate_random_string",
    "make_plantuml_inert",
    "plantuml_conf",
    "require_plantuml_extension",
    "resolve_plantuml_command",
    "sphinx_build_command",
    "warning_count",
    "workspace_plantuml_jar",
]
