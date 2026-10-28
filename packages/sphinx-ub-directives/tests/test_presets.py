"""Preset rules the corpus cannot carry, and the Sphinx-side mechanics of §3.5."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from sphinx.testing.util import SphinxTestApp

from sphinx_needs_testkit import build_warnings

from .corpus import CONF_PY

STORY = """\
[[needs.types]]
directive = "Story"
title = "Story"
prefix = "S_"

[parse.directive_presets.story-draft]
base = "Story"
options = { status = "draft" }
"""


def _build(
    make_app: Callable[..., SphinxTestApp], root: Path, toml: str, page: str
) -> SphinxTestApp:
    root.mkdir(parents=True, exist_ok=True)
    (root / "conf.py").write_text(CONF_PY, encoding="utf-8")
    (root / "ubproject.toml").write_text(toml, encoding="utf-8")
    (root / "index.rst").write_text("Case\n====\n\n" + page, encoding="utf-8")
    app = make_app("needs", srcdir=root, freshenv=True)
    app.build()
    return app


def test_a_capitalised_need_type_is_refused_as_a_base(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """§3.2.6: a Sphinx build registers ``Story`` verbatim but looks every directive up in
    lower case, so the type is unusable; a preset of it would make it usable under
    another name only, which the other tool could not match. It is refused, saying why,
    and no need is made through it."""
    app = _build(make_app, tmp_path, STORY, ".. story-draft:: A\n   :id: S_001\n")
    warnings = build_warnings(app)
    refused = [w for w in warnings if "directive_preset_unknown_base" in w]
    assert len(refused) == 1, warnings
    assert "upper-case" in refused[0]
    assert "[parse.directive_presets.story-draft.base]" in refused[0]
    assert "S_001" not in (Path(app.outdir) / "needs.json").read_text(encoding="utf-8")


def test_a_forced_option_warning_is_located_at_the_use(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """§3.5: a plain docutils directive (``note``) has no ``get_location()``; the warning
    is at ``(docname, lineno)`` of the use."""
    toml = '[parse.directive_presets.locked]\nbase = "note"\nforce_options = { class = "x" }\n'
    app = _build(
        make_app, tmp_path, toml, "Text.\n\n.. locked::\n   :class: y\n\n   Body.\n"
    )
    forced = [w for w in build_warnings(app) if "preset_forced_option" in w]
    assert len(forced) == 1
    assert forced[0].startswith("<srcdir>/index.rst:6: WARNING: [locked]"), forced


def test_a_need_preset_keeps_accepting_every_need_option(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """[A2] corrected: with a forced option, the preset's option spec is a subclass of
    sphinx-needs' ``DummyOptionSpec``, so ``:id:`` and every field still reach the need
    (a plain ``dict`` copy is empty, and every option is "unknown")."""
    toml = '[parse.directive_presets.req-draft]\nbase = "req"\nforce_options = { status = "draft" }\n'
    app = _build(
        make_app, tmp_path, toml, ".. req-draft:: A\n   :id: REQ_001\n   :tags: x\n"
    )
    text = (Path(app.outdir) / "needs.json").read_text(encoding="utf-8")
    assert '"REQ_001"' in text
    assert not [w for w in build_warnings(app) if "nknown option" in w]


def test_a_self_preset_whose_base_is_replaced_later_warns(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """§3.4.7 (L6): bases are snapshotted at ``builder-inited``; an extension that registers
    a self-preset's directive again after that drops the self-preset, and the build says so."""
    (tmp_path / "late.py").write_text(
        "from docutils.parsers.rst.directives.admonitions import Note\n"
        "class Late(Note):\n    pass\n"
        "def _late(app):\n    app.add_directive('note', Late, override=True)\n"
        "def setup(app):\n    app.connect('builder-inited', _late, priority=900)\n",
        encoding="utf-8",
    )
    conf = (
        "import os, sys\nsys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\n"
        + CONF_PY
        + "extensions = [*extensions, 'late']\n"
    )
    toml = '[parse.directive_presets.note]\nbase = "note"\noptions = { class = "d" }\n'
    tmp_path.mkdir(exist_ok=True)
    (tmp_path / "conf.py").write_text(conf, encoding="utf-8")
    (tmp_path / "ubproject.toml").write_text(toml, encoding="utf-8")
    (tmp_path / "index.rst").write_text(
        "Case\n====\n\n.. note::\n\n   Body.\n", encoding="utf-8"
    )
    app = make_app("needs", srcdir=tmp_path, freshenv=True)
    app.build()
    assert [
        w for w in build_warnings(app) if "ub_directives.preset_base_replaced" in w
    ], build_warnings(app)
