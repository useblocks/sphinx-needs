"""Preset rules the corpus cannot carry, and the Sphinx-side mechanics of §3.5."""

from __future__ import annotations

import json
import re
import warnings
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


def test_a_need_type_option_is_never_read_from_an_earlier_schema(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """N4/S2: before this build's ``create_schema`` the schema is missing (a fresh build) or
    the previous build's (an incremental one), so sphinx-needs' ``resolve_need_option``,
    and so the one helper, refuses to answer then;
    once the build has it (from ``env-before-read-docs`` above 500, as the presets ask),
    the rule is the need directive's: exact, then ignoring case, answered by the
    DECLARED name."""
    toml = '[needs.fields.Priority]\nschema = { type = "string" }\n'
    root = tmp_path / "p"
    root.mkdir()
    (root / "conf.py").write_text(CONF_PY, encoding="utf-8", newline="")
    (root / "ubproject.toml").write_text(toml, encoding="utf-8", newline="")
    (root / "index.rst").write_text("Case\n====\n", encoding="utf-8", newline="")
    app = make_app("html", srcdir=root, freshenv=True)
    with pytest.raises(RuntimeError):
        _presets._need_option(app, "req", "status")
    names = ("status", "STATUS", "priority", "Priority", "nope")
    answers: dict[str, str | None] = {}

    def ask(app: SphinxTestApp, *_args: object) -> None:
        answers.update({n: _presets._need_option(app, "req", n) for n in names})

    app.connect("env-before-read-docs", ask, priority=650)
    app.build()
    assert answers == {
        "status": "status",
        "STATUS": "status",
        "priority": "Priority",
        "Priority": "Priority",
        "nope": None,
    }
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


def test_need_type_presets_need_resolve_need_option(
    make_app: Callable[..., SphinxTestApp],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """S3: with a sphinx-needs that has no public ``resolve_need_option`` (before 9.2), a
    need-type preset is refused at load with one finding saying why; a preset of any other
    base and a declared template keep working."""
    api = pytest.importorskip("sphinx_needs.api")
    monkeypatch.delattr(api, "resolve_need_option")
    toml = (
        '[parse.directive_presets.drafted]\nbase = "req"\noptions = { status = "draft" }\n\n'
        '[parse.directive_presets.callout]\nbase = "note"\noptions = { class = "c" }\n\n'
        '[parse.directive_templates.row]\nbody = "Row text."\n'
    )
    tmp_path.mkdir(exist_ok=True)
    (tmp_path / "conf.py").write_text(CONF_PY, encoding="utf-8", newline="")
    (tmp_path / "ubproject.toml").write_text(toml, encoding="utf-8", newline="")
    (tmp_path / "index.rst").write_text(
        "Case\n====\n\n.. callout::\n\n   Body.\n\n.. row::\n",
        encoding="utf-8",
        newline="",
    )
    app = make_app("html", srcdir=tmp_path, freshenv=True)
    app.build()
    warnings = build_warnings(app)
    refused = [
        w for w in warnings if "ub_directives.directive_preset_unknown_base" in w
    ]
    assert len(refused) == 1, warnings
    assert "need-type presets need sphinx-needs 9.2 or later" in refused[0]
    assert "drafted" in refused[0]
    html = (Path(app.outdir) / "index.html").read_text(encoding="utf-8")
    # the class order of an admonition differs across Sphinx versions
    classes = [set(c.split()) for c in re.findall(r'<div class="([^"]*)"', html)]
    assert {"admonition", "note", "c"} in [
        c & {"admonition", "note", "c"} for c in classes
    ]
    assert "Row text." in html


#: An extension that registers ``myname`` itself, at ``{event}`` priority {priority}.
_MYNAME = (
    "from docutils.parsers.rst.directives.admonitions import Note\n"
    "class Mine(Note):\n    pass\n"
    "def _mine(app, *_args):\n    app.add_directive('myname', Mine, override=True)\n"
    "def setup(app):\n    app.connect({event!r}, _mine, priority={priority})\n"
)


@pytest.mark.parametrize(
    ("needs", "event", "priority"),
    [
        pytest.param(False, "builder-inited", 900, id="without-sphinx-needs"),
        pytest.param(True, "env-before-read-docs", 650, id="with-sphinx-needs"),
    ],
)
def test_a_preset_replaced_by_a_later_extension_warns(
    make_app: Callable[..., SphinxTestApp],
    tmp_path: Path,
    needs: bool,
    event: str,
    priority: int,
) -> None:
    """S5 (§3.4.7): a preset of a NEW name that another extension registers over after
    the presets were is reported, not lost silently -- in both registration modes (§3.5):
    without sphinx-needs the presets register at ``builder-inited``, so a later handler
    there replaces them; with it, at ``env-before-read-docs`` 600."""
    # a module name of its own per case: Python caches an imported module by name
    module = f"mine_{'needs' if needs else 'plain'}"
    extensions = (
        f'["sphinx_needs", "sphinx_ub_directives", "{module}"]'
        if needs
        else f'["sphinx_ub_directives", "{module}"]'
    )
    conf = (
        "import os, sys\nsys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\n"
        f"extensions = {extensions}\nshow_warning_types = True\n"
        + ('needs_from_toml = "ubproject.toml"\n' if needs else "")
    )
    tmp_path.mkdir(exist_ok=True)
    (tmp_path / "conf.py").write_text(conf, encoding="utf-8", newline="")
    (tmp_path / f"{module}.py").write_text(
        _MYNAME.format(event=event, priority=priority), encoding="utf-8", newline=""
    )
    (tmp_path / "ubproject.toml").write_text(
        '[parse.directive_presets.myname]\nbase = "note"\noptions = { class = "c" }\n',
        encoding="utf-8",
        newline="",
    )
    (tmp_path / "index.rst").write_text(
        "Case\n====\n\n.. myname::\n\n   Body.\n", encoding="utf-8", newline=""
    )
    app = make_app("html", srcdir=tmp_path, freshenv=True)
    app.build()
    warnings = build_warnings(app)
    replaced = [w for w in warnings if "ub_directives.preset_base_replaced" in w]
    assert len(replaced) == 1, warnings
    assert "this preset is not used" in replaced[0]


def test_need_type_output_uses_no_deprecated_sphinx_api(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """V5-2: a need-type preset's use and a need in template output reach the build's
    application without ``env.app``, which Sphinx 9 deprecates (a ``RemovedInSphinx…``
    warning on every directive lookup in output and every preset use)."""
    toml = (
        '[parse.directive_presets.req-draft]\nbase = "req"\noptions = { status = "draft" }\n\n'
        '[parse.directive_templates.emit]\nbody = ".. req:: Out\\n   :id: REQ_OUT\\n"\n'
    )
    page = ".. req-draft:: A\n   :id: REQ_DEP\n   :Status: open\n\n.. emit::\n"
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        app = _build(make_app, tmp_path, toml, page)
    # this package's own use only: sphinx-needs may still read ``env.app`` itself
    deprecated = [
        f"{w.filename}:{w.lineno}: {w.message}"
        for w in caught
        if type(w.message).__name__.startswith("RemovedIn")
        and "sphinx_ub_directives" in w.filename
    ]
    assert deprecated == []
    assert not [w for w in build_warnings(app) if "ub_directives." in w], (
        build_warnings(app)
    )


def test_the_same_application_built_twice_judges_its_presets_afresh(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """V5-1: building one application twice (a tool or a suite may) registers the
    presets again, in either mode: the second build must not find its own presets of the
    first build as taken names, nor keep their old classes, so a changed preset applies."""
    toml = (
        '[parse.directive_presets.callout]\nbase = "note"\noptions = { class = "first" }\n\n'
        '[parse.directive_presets.req-draft]\nbase = "req"\noptions = { status = "draft" }\n\n'
        '[parse.directive_presets.note]\nbase = "note"\noptions = { class = "self-first" }\n\n'
        '[parse.directive_presets."py:function"]\nbase = "py:function"\n'
        'options = { module = "modfirst" }\n'
    )
    page = (
        ".. callout::\n\n   Body.\n\n.. req-draft:: A\n   :id: REQ_TWICE\n\n"
        ".. note::\n\n   Plain.\n\n.. py:function:: f(x)\n"
    )
    app = _build(make_app, tmp_path, toml, page)
    assert not [w for w in build_warnings(app) if "ub_directives." in w], (
        build_warnings(app)
    )
    presets = app.config.ub_directives_resolved["directive_presets"]
    presets["callout"]["options"]["class"] = "second"
    presets["req-draft"]["options"]["status"] = "open"
    presets["note"]["options"]["class"] = "self-second"
    presets["py:function"]["options"]["module"] = "modsecond"
    warning_stream = getattr(app, "_warning")  # noqa: B009
    warning_stream.seek(0)
    warning_stream.truncate(0)
    # an outdated page, so it is read again (a build re-reads only what changed)
    (tmp_path / "index.rst").write_text(
        "Case\n====\n\n" + page + "\nAgain.\n", encoding="utf-8", newline=""
    )
    app.build()
    assert not [w for w in build_warnings(app) if "ub_directives." in w], (
        build_warnings(app)
    )
    doctree = app.env.get_doctree("index").pformat()
    data = json.loads((Path(app.outdir) / "needs.json").read_text(encoding="utf-8"))
    assert (
        data["versions"][data["current_version"]]["needs"]["REQ_TWICE"]["status"]
        == "open"
    )
    assert "second" in doctree and "first" not in doctree
    # the self-preset wraps the ORIGINAL note, not the first build's preset of it
    assert "self-second" in doctree and "self-first" not in doctree
    # and so does a domain directive's: the build's domain serves one preset of it
    assert "modsecond" in doctree
    served = app.env.get_domain("py").directives["function"]
    assert [c.__name__ for c in served.__mro__].count("Preset_py_function") == 1


#: need types ``req`` and ``step``; ``step`` is never written bare (its directive_name)
QUALIFIED_TYPES = """\
[[needs.types]]
directive = "req"
title = "Requirement"
prefix = "R_"

[[needs.types]]
directive = "step"
title = "Step"
prefix = "ST_"
directive_name = "qualified"
"""


def _needs(app: SphinxTestApp) -> dict[str, dict[str, object]]:
    data = json.loads((Path(app.outdir) / "needs.json").read_text(encoding="utf-8"))
    return data["versions"][data["current_version"]]["needs"]


@pytest.mark.parametrize(
    "base",
    [
        pytest.param("need:req", id="qualified-base"),
        pytest.param("need:step", id="qualified-base-of-a-qualified-type"),
        pytest.param("step", id="bare-base-of-a-qualified-type"),
    ],
)
def test_a_need_type_base_qualified_or_not(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path, base: str
) -> None:
    """A base ``need:<type>`` is that need type (its options are the need's), and so is
    a bare base naming a need type whose bare directive is not the need's
    (``directive_name = "qualified"``): the need the ``need`` domain serves."""
    toml = (
        QUALIFIED_TYPES
        + f'\n[parse.directive_presets.my-preset]\nbase = "{base}"\n'
        + 'options = { status = "draft" }\n'
    )
    app = _build(make_app, tmp_path, toml, ".. my-preset:: A\n   :id: X_001\n")
    assert build_warnings(app) == []
    need = _needs(app)["X_001"]
    assert (need["type"], need["status"]) == (base.removeprefix("need:"), "draft")


def test_a_qualified_name_is_taken(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """A new preset name ``need:<type>`` is taken by the need type, as its bare name
    is: a preset of that name would replace the need."""
    toml = (
        QUALIFIED_TYPES
        + '\n[parse.directive_presets."need:req"]\nbase = "note"\n'
        + '\n[parse.directive_presets."NEED:step"]\nbase = "note"\n'
    )
    app = _build(make_app, tmp_path, toml, ".. need:req:: A\n   :id: R_001\n")
    refused = [w for w in build_warnings(app) if "directive_preset_name_taken" in w]
    assert len(refused) == 2, build_warnings(app)
    assert _needs(app)["R_001"]["type"] == "req"


def test_a_qualified_base_takes_the_need_type_s_options(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """A base ``need:req`` is the need type ``req`` (§3.3.3), not just the directive the
    ``need`` domain serves: a key the type's directive does not match is refused, as for
    the bare base ``req``, where a directive taking any option would accept it."""
    toml = (
        QUALIFIED_TYPES
        + '\n[parse.directive_presets.my-preset]\nbase = "need:req"\n'
        + 'options = { nosuch = "x" }\n'
    )
    app = _build(make_app, tmp_path, toml, ".. need:req:: A\n   :id: R_001\n")
    refused = [w for w in build_warnings(app) if "directive_preset_unknown_option" in w]
    assert len(refused) == 1, build_warnings(app)
    assert "[parse.directive_presets.my-preset.options.nosuch]" in refused[0]


#: need type ``dropdown`` (sphinx-design's directive name too), and ``step`` (no other
#: directive's); each test appends the types' ``directive_name`` and one self-preset
DROPDOWN_TYPES = """\
[[needs.types]]
directive = "dropdown"
title = "Dropdown"
prefix = "DD_"
directive_name = "{dropdown}"

[[needs.types]]
directive = "step"
title = "Step"
prefix = "ST_"
directive_name = "{step}"
"""


@pytest.mark.parametrize(
    ("modes", "preset", "page", "codes", "needs", "doctree"),
    [
        pytest.param(
            {"dropdown": "claim", "step": "claim"},
            '[parse.directive_presets.step]\nbase = "step"\noptions = { status = "zz" }\n',
            ".. step:: A\n   :id: ST_001\n",
            [],
            {"ST_001": "zz"},
            None,
            id="claim-the-need",
        ),
        pytest.param(
            {"dropdown": "yield", "step": "claim"},
            '[parse.directive_presets.dropdown]\nbase = "dropdown"\n'
            'options = { class-container = "zzcls" }\n',
            ".. dropdown:: A\n\n   Body.\n",
            [],
            {},
            "zzcls",
            id="yield-the-other-directive",
        ),
        pytest.param(
            {"dropdown": "yield", "step": "claim"},
            '[parse.directive_presets.dropdown]\nbase = "dropdown"\n'
            'options = { status = "zz" }\n',
            ".. dropdown:: A\n\n   Body.\n",
            ["directive_preset_unknown_option"],
            {},
            None,
            id="yield-a-need-option-is-the-other-directive-s-unknown-option",
        ),
        pytest.param(
            {"dropdown": "claim", "step": "qualified"},
            '[parse.directive_presets.step]\nbase = "step"\noptions = { status = "zz" }\n',
            ".. need:step:: A\n   :id: ST_001\n",
            ["directive_preset_unknown_base"],
            {"ST_001": None},
            None,
            id="qualified-no-directive",
        ),
    ],
)
def test_a_self_preset_of_a_need_type_s_bare_name(
    make_app: Callable[..., SphinxTestApp],
    tmp_path: Path,
    modes: dict[str, str],
    preset: str,
    page: str,
    codes: list[str],
    needs: dict[str, object],
    doctree: str | None,
) -> None:
    """§3.2.3: a self-preset gives the directive its name resolves to project-wide
    defaults. The bare name of a need type whose ``directive_name`` leaves it to another
    directive (``yield``) is that directive, so the self-preset is that directive's, and
    the need stays out of the bare name; under ``qualified`` the bare name is no
    directive at all, so the self-preset has no base. Only where the bare name is the
    need (``claim``) is it a self-preset of the need type."""
    toml = DROPDOWN_TYPES.format(**modes) + "\n" + preset
    app = _build(make_app, tmp_path, toml, page)
    found = [
        code
        for w in build_warnings(app)
        for code in re.findall(r"\[ub_directives\.([a-z_]+)\]", w)
    ]
    assert found == codes, build_warnings(app)
    assert {k: v["status"] for k, v in _needs(app).items()} == needs
    if doctree is not None:
        assert doctree in app.env.get_doctree("index").pformat()


@pytest.mark.parametrize(
    ("preset", "page", "expected"),
    [
        pytest.param(
            '[parse.directive_presets."need:req"]\nbase = "need:req"\n'
            'options = { status = "zz" }\n',
            ".. need:req:: A\n   :id: R_001\n",
            "zz",
            id="need-req",
        ),
        pytest.param(
            '[parse.directive_presets."py:function"]\nbase = "py:function"\n'
            'options = { module = "zzmod" }\n',
            ".. py:function:: f(x)\n",
            "zzmod",
            id="py-function",
        ),
    ],
)
def test_a_self_preset_of_a_domain_directive_applies(
    make_app: Callable[..., SphinxTestApp],
    tmp_path: Path,
    preset: str,
    page: str,
    expected: str,
) -> None:
    """§3.2.3: a self-preset of a domain's directive (``need:req``, ``py:function``)
    gives it project-wide defaults, as a self-preset of any directive does. The domain's
    instance already serves the directive when the presets are registered, so the preset
    must reach it there, not only Sphinx's registry of domain directives."""
    app = _build(make_app, tmp_path, QUALIFIED_TYPES + "\n" + preset, page)
    assert build_warnings(app) == []
    if expected == "zz":
        assert _needs(app)["R_001"]["status"] == "zz"
    else:
        assert expected in app.env.get_doctree("index").pformat()
