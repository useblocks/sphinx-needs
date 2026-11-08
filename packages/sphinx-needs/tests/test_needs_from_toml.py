import json
from pathlib import Path

import pytest
from syrupy.filters import props

from sphinx_needs_testkit import assert_no_warnings


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/needs_from_toml",
        }
    ],
    indirect=True,
)
def test_needs_from_toml(test_app, snapshot):
    app = test_app
    app.build()
    assert not app._warning.getvalue()
    data = json.loads(Path(app.outdir, "needs.json").read_text("utf8"))
    assert data == snapshot(
        exclude=props("created", "project", "creator", "needs_schema")
    )


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/needs_from_toml",
            "confoverrides": {"needs_reproducible_json": False},
        }
    ],
    indirect=True,
)
def test_needs_from_toml_respects_overrides(test_app):
    app = test_app
    app.build()
    assert not app._warning.getvalue()
    assert app.config.needs_reproducible_json is False


def test_needs_from_toml_reads_toml_1_1(make_app, tmp_path):
    """The file is read as TOML 1.1: an inline table ending in a trailing comma, which
    TOML 1.0 refuses, is read like any other."""
    srcdir = tmp_path / "src"
    srcdir.mkdir()
    (srcdir / "conf.py").write_text(
        'extensions = ["sphinx_needs"]\nneeds_from_toml = "ubproject.toml"\n',
        encoding="utf-8",
    )
    (srcdir / "ubproject.toml").write_text(
        "[needs]\n"
        "id_required = true\n"
        "types = [\n"
        '  { directive = "story", title = "User Story", prefix = "US_", },\n'
        "]\n",
        encoding="utf-8",
    )
    (srcdir / "index.rst").write_text(
        "Title\n=====\n\n.. story:: A story\n   :id: US_001\n", encoding="utf-8"
    )
    app = make_app(srcdir=srcdir, freshenv=True)
    app.build()
    assert_no_warnings(app)
    assert app.config.needs_id_required is True
    assert [t["directive"] for t in app.config.needs_types] == ["story"]
    assert "US_001" in Path(app.outdir, "index.html").read_text(encoding="utf-8")
