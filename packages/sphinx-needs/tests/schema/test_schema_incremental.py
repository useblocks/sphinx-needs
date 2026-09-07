"""Regression tests for incremental builds with schema_definitions_from_json."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path

import pytest
from sphinx.testing.util import SphinxTestApp
from sphinx.util.console import strip_colors


@pytest.fixture
def schema_inc_srcdir(tmp_path: Path) -> Path:
    """Copy the doc_schema_incremental fixture into a fresh tmpdir."""
    src = Path(__file__).parent.parent / "doc_test" / "doc_schema_incremental"
    dst = tmp_path / "src"
    shutil.copytree(src, dst)
    return dst


def _build_and_get_status(
    make_app: Callable[..., SphinxTestApp], srcdir: Path, freshenv: bool
) -> str:
    """Run a single Sphinx build and return the captured stdout."""
    app = make_app(buildername="html", srcdir=srcdir, freshenv=freshenv)
    try:
        app.build()
        return strip_colors(app._status.getvalue())
    finally:
        app.cleanup()


def test_schema_definitions_from_json_does_not_trigger_full_rebuild(
    make_app: Callable[..., SphinxTestApp],
    schema_inc_srcdir: Path,
) -> None:
    """Second incremental build must reuse the env when nothing has changed.

    Regression: enabling ``needs_schema_definitions_from_json`` used to mutate
    the in-memory config dict during ``env-before-read-docs`` (injecting
    ``type`` keys via ``populate_field_type``). The pickled environment then
    held the mutated config, while the next build started with the unmutated
    JSON-loaded config, so Sphinx's config-change detection saw a difference
    on every run and rebuilt every document.
    """
    first = _build_and_get_status(make_app, schema_inc_srcdir, freshenv=True)
    # Sanity: the first build is necessarily a full build.
    assert "1 added, 0 changed, 0 removed" in first

    second = _build_and_get_status(make_app, schema_inc_srcdir, freshenv=False)
    # The pickled env must be reused -- no "config changed" should be reported,
    # and no documents should be added/changed/removed.
    assert "loading pickled environment" in second
    assert "config changed" not in second, (
        "Incremental build incorrectly detected a config change. "
        "needs_schema_definitions is being mutated after Sphinx's config "
        "comparison checkpoint.\n\nFull status output:\n" + second
    )
    assert "0 added, 0 changed, 0 removed" in second
