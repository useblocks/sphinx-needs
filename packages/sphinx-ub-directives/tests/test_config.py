"""Reading the tables (contract §2)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from sphinx.testing.util import SphinxTestApp

from sphinx_needs_testkit import build_warnings
from sphinx_ub_directives import _config

from .corpus import CONF_PY

PRESET = '[parse.directive_presets.callout]\nbase = "note"\nappend_options = { class = "c" }\n'


def _app(
    make_app: Callable[..., SphinxTestApp], root: Path, toml: str, conf: str = CONF_PY
) -> SphinxTestApp:
    root.mkdir(parents=True, exist_ok=True)
    (root / "conf.py").write_text(conf, encoding="utf-8", newline="")
    (root / "ubproject.toml").write_text(toml, encoding="utf-8", newline="")
    (root / "index.rst").write_text(
        "Case\n====\n\n.. callout::\n\n   Body.\n", encoding="utf-8", newline=""
    )
    return make_app("html", srcdir=root, freshenv=True)


def test_an_extend_key_warns_once(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """§2.1: no `extend` chain is resolved, and a file that has one beside these tables
    says so once."""
    app = _app(make_app, tmp_path, 'extend = "../base.toml"\n\n' + PRESET)
    app.build()
    found = [w for w in build_warnings(app) if "ub_directives.extend_unsupported" in w]
    assert len(found) == 1, build_warnings(app)


def test_no_extend_warning_without_the_tables(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    app = _app(make_app, tmp_path, 'extend = "../base.toml"\n')
    app.build()
    assert not [w for w in build_warnings(app) if "extend_unsupported" in w]


def test_the_tables_are_a_rebuild_env_confval(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """§2.2: a change to the tables is a change to a `rebuild="env"` confval, so Sphinx
    re-reads every document, although `ubproject.toml` is outside `conf.py`."""
    app = _app(make_app, tmp_path, PRESET)
    assert app.config.values[_config.CONFVAL].rebuild == "env"
    assert app.config[_config.CONFVAL]["directive_presets"]["callout"]["base"] == "note"


def test_without_sphinx_needs_the_file_is_found_from_the_confdir(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """§2.1: sphinx-needs is optional; without it, ub-project finds the file."""
    conf = 'extensions = ["sphinx_ub_directives"]\n'
    app = _app(make_app, tmp_path, PRESET, conf=conf)
    app.build()
    html = (Path(app.outdir) / "index.html").read_text(encoding="utf-8")
    assert '<div class="c admonition note">' in html, html
    assert not [w for w in build_warnings(app) if "ub_directives" in w]
