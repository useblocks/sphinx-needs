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
