"""Preset rules the corpus cannot carry, and the Sphinx-side mechanics of §3.5."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from sphinx.testing.util import SphinxTestApp

from sphinx_needs_testkit import build_warnings
from sphinx_ub_directives import _presets

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
    (root / "conf.py").write_text(CONF_PY, encoding="utf-8", newline="")
    (root / "ubproject.toml").write_text(toml, encoding="utf-8", newline="")
    (root / "index.rst").write_text(
        "Case\n====\n\n" + page, encoding="utf-8", newline=""
    )
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
    """§3.4.7 (L6): bases are snapshotted when the presets are registered (with sphinx-needs,
    ``env-before-read-docs`` at priority 600); an extension that registers a self-preset's
    directive again after that drops the self-preset, and the build says so."""
    (tmp_path / "late.py").write_text(
        "from docutils.parsers.rst.directives.admonitions import Note\n"
        "class Late(Note):\n    pass\n"
        "def _late(app, *_args):\n    app.add_directive('note', Late, override=True)\n"
        "def setup(app):\n    app.connect('env-before-read-docs', _late, priority=650)\n",
        encoding="utf-8",
    )
    conf = (
        "import os, sys\nsys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\n"
        + CONF_PY
        + "extensions = [*extensions, 'late']\n"
    )
    toml = '[parse.directive_presets.note]\nbase = "note"\noptions = { class = "d" }\n'
    tmp_path.mkdir(exist_ok=True)
    (tmp_path / "conf.py").write_text(conf, encoding="utf-8", newline="")
    (tmp_path / "ubproject.toml").write_text(toml, encoding="utf-8", newline="")
    (tmp_path / "index.rst").write_text(
        "Case\n====\n\n.. note::\n\n   Body.\n", encoding="utf-8", newline=""
    )
    app = make_app("needs", srcdir=tmp_path, freshenv=True)
    app.build()
    assert [
        w for w in build_warnings(app) if "ub_directives.preset_base_replaced" in w
    ], build_warnings(app)


def test_a_build_without_presets_does_not_see_a_previous_builds(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """D12: the registered self-presets are process state, reset by every build -- one
    without presets included -- so a later project is never told about an earlier one's."""
    first = tmp_path / "first"
    first.mkdir()
    (first / "late.py").write_text(
        "from docutils.parsers.rst.directives.admonitions import Note\n"
        "class Late(Note):\n    pass\n"
        "def _late(app, *_args):\n    app.add_directive('note', Late, override=True)\n"
        "def setup(app):\n    app.connect('env-before-read-docs', _late, priority=650)\n",
        encoding="utf-8",
    )
    conf = (
        "import os, sys\nsys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\n"
        + CONF_PY
        + "extensions = [*extensions, 'late']\n"
    )
    (first / "conf.py").write_text(conf, encoding="utf-8", newline="")
    (first / "ubproject.toml").write_text(
        '[parse.directive_presets.note]\nbase = "note"\noptions = { class = "d" }\n',
        encoding="utf-8",
    )
    (first / "index.rst").write_text("Case\n====\n", encoding="utf-8", newline="")
    app = make_app("needs", srcdir=first, freshenv=True)
    app.build()
    assert [w for w in build_warnings(app) if "preset_base_replaced" in w]
    second = _build(make_app, tmp_path / "second", "[needs]\n", "Text.\n")
    assert not [w for w in build_warnings(second) if "preset_base_replaced" in w], (
        build_warnings(second)
    )


# --- a need type's options (§3.3.3, §3.5) ---------------------------------------------


def test_need_meta_options_are_the_need_directives_own() -> None:
    """Q2 fence: the need directive's own options (its options that are no field or link)
    are copied here; a change to sphinx-needs' list is a red test in the same change. It
    goes once ``sphinx_needs.api.resolve_need_option`` answers for both."""
    need = pytest.importorskip("sphinx_needs.directives.need")
    own = getattr(need, "NEED_DIRECTIVE_OPTIONS", None)
    if own is None:
        pytest.skip("this sphinx-needs predates NEED_DIRECTIVE_OPTIONS")
    assert own == _presets.NEED_META_OPTIONS


def test_a_need_type_option_is_never_read_from_an_earlier_schema(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """N4: before this build's ``create_schema`` the schema is missing (a fresh build) or
    the previous build's (an incremental one), so the one helper refuses to answer then;
    once the build has it, the rule is the need directive's: exact, then ignoring case,
    answered by the DECLARED name."""
    toml = '[needs.fields.Priority]\nschema = { type = "string" }\n'
    root = tmp_path / "p"
    root.mkdir()
    (root / "conf.py").write_text(CONF_PY, encoding="utf-8", newline="")
    (root / "ubproject.toml").write_text(toml, encoding="utf-8", newline="")
    (root / "index.rst").write_text("Case\n====\n", encoding="utf-8", newline="")
    app = make_app("html", srcdir=root, freshenv=True)
    with pytest.raises(RuntimeError):
        _presets._need_option(app, "req", "status")
    app.build()
    assert _presets._need_option(app, "req", "status") == "status"
    assert _presets._need_option(app, "req", "STATUS") == "status"
    assert _presets._need_option(app, "req", "priority") == "Priority"
    assert _presets._need_option(app, "req", "Priority") == "Priority"
    assert _presets._need_option(app, "req", "nope") is None
    app.cleanup()
    # an incremental build has the previous build's schema in its environment from the
    # start: still no answer until this build's own is built
    again = make_app("html", srcdir=root, freshenv=False)
    with pytest.raises(RuntimeError):
        _presets._need_option(again, "req", "status")


def test_a_presets_options_follow_the_new_config_on_an_incremental_build(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """N4: on an incremental build (no ``-E``) the environment, and sphinx-needs' schema in
    it, is the previous build's until ``create_schema`` runs; presets are judged after it,
    so a field declared on the type since the last build is taken -- and one renamed away
    since is refused -- by the NEW configuration."""
    preset = (
        '[parse.directive_presets.scoped]\nbase = "req"\noptions = { reqonly = "v" }\n'
    )
    field = '[needs.types.req.fields.{name}]\nschema = {{ type = "string" }}\n\n'
    root = tmp_path / "p"
    root.mkdir()
    (root / "conf.py").write_text(CONF_PY, encoding="utf-8", newline="")
    (root / "index.rst").write_text(
        "Case\n====\n\n.. scoped:: A\n   :id: REQ_INC\n", encoding="utf-8", newline=""
    )

    def build(name: str, *, fresh: bool) -> tuple[list[str], dict[str, object]]:
        (root / "ubproject.toml").write_text(
            field.format(name=name) + preset, encoding="utf-8", newline=""
        )
        app = make_app("html", srcdir=root, freshenv=fresh)
        app.build()
        data = json.loads((Path(app.outdir) / "needs.json").read_text(encoding="utf-8"))
        needs = data["versions"][data["current_version"]]["needs"]
        refused = [
            w for w in build_warnings(app) if "directive_preset_unknown_option" in w
        ]
        app.cleanup()  # as a new process would: this build's directives are gone
        return refused, needs

    refused, needs = build("other", fresh=True)
    assert refused and "REQ_INC" not in needs
    refused, needs = build("reqonly", fresh=False)
    assert not refused and needs["REQ_INC"]["reqonly"] == "v"
    refused, needs = build("renamed", fresh=False)
    assert refused and "REQ_INC" not in needs


@pytest.mark.parametrize(
    ("page", "source"),
    [
        pytest.param(
            "index.rst",
            "Case\n====\n\n.. prio:: A\n   :id: REQ_PF1\n   :priority: high\n",
            id="rst",
        ),
        pytest.param(
            "index.md",
            "# Case\n\n```{prio} A\n:id: REQ_PF1\n:PRIORITY: high\n```\n",
            id="md",
        ),
    ],
)
def test_a_forced_option_replaces_a_written_one_in_another_case_whole(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path, page: str, source: str
) -> None:
    """N2: a forced ``Priority`` and a written ``:priority:`` / ``:PRIORITY:`` are one
    option, so the written spelling goes and the need directive sees the option once --
    not twice in two cases, which sphinx-needs reports (``needs.directive``) while still
    keeping the forced value. The corpus compares preset codes only, so this pins it."""
    toml = (
        '[needs.fields.Priority]\nschema = { type = "string" }\n\n'
        '[parse.directive_presets.prio]\nbase = "req"\nforce_options = { Priority = "low" }\n'
    )
    tmp_path.mkdir(exist_ok=True)
    (tmp_path / "conf.py").write_text(CONF_PY, encoding="utf-8", newline="")
    (tmp_path / "ubproject.toml").write_text(toml, encoding="utf-8", newline="")
    (tmp_path / page).write_text(source, encoding="utf-8", newline="")
    app = make_app("html", srcdir=tmp_path, freshenv=True)
    app.build()
    warnings = build_warnings(app)
    assert not [w for w in warnings if "needs.directive" in w], warnings
    assert [w for w in warnings if "preset_forced_option" in w], warnings
