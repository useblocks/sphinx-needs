"""``resolve_need_option``: the option a need type's directive takes for a name, as the
directive itself matches it, from the moment sphinx-needs has built this build's
schema."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from sphinx.testing.util import SphinxTestApp

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs_testkit import build_warnings

PROBE_EXT = '''\
"""Asks ``resolve_need_option`` the same questions at several events, and keeps the
answers on the application (never pickled)."""

from sphinx_needs.api import resolve_need_option

#: (need type, name) asked at each event
QUESTIONS = [
    ("req", "asil"),
    ("req", "verifies"),
    ("spec", "asil"),
    ("req", "prio"),
    ("req", "status"),
    ("req", "hide"),
    ("req", "owner"),
    ("req", "OWNER"),
    ("req", "Owner"),
    ("req", "nosuch"),
    ("req", "added"),
    ("nosuchtype", "status"),
]


def ask(event):
    def handler(app, *args):
        answers = {}
        for need_type, name in QUESTIONS:
            try:
                answers[need_type, name] = resolve_need_option(app, need_type, name)
            except (RuntimeError, ValueError) as err:
                answers[need_type, name] = (type(err).__name__, str(err))
        app.__dict__.setdefault("resolve_answers", {})[event] = answers
    return handler


def setup(app):
    app.connect("builder-inited", ask("builder-inited"))
    app.connect("env-before-read-docs", ask("env-before-read-docs@499"), priority=499)
    app.connect("env-before-read-docs", ask("env-before-read-docs@501"), priority=501)
    app.connect("env-updated", ask("env-updated"))
    return {"parallel_read_safe": True}
'''

CONF = """\
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.modules.pop("probe_ext", None)
extensions = ["sphinx_needs", "probe_ext"]
needs_fields = {"Owner": {"nullable": True}, "prio": {"nullable": True}}
needs_types = {
    "req": {
        "title": "Requirement",
        "prefix": "R_",
        "fields": {"asil": {"schema": {"type": "string"}}%(added)s},
        "links": {"verifies": {"outgoing": "verifies"}},
    },
    "spec": {"title": "Specification", "prefix": "S_"},
}
"""

#: a need directive writing an option of each kind: a type-local field and link type, a
#: global field, two core options, and a field declared with a capital, written in
#: capitals (reStructuredText lowercases it: the directive sees ``owner``)
INDEX = """\
Options
=======

.. req:: Target
   :id: R_TARGET

.. req:: Main
   :id: R_MAIN
   :asil: B
   :verifies: R_TARGET
   :prio: high
   :status: open
   :hide:
   :OWNER: me
"""

TOO_EARLY = (
    "RuntimeError",
    "resolve_need_option is available once sphinx-needs has built this build's "
    "schema, in its own 'env-before-read-docs' handler (priority 500): call it from "
    "an 'env-before-read-docs' handler at a priority above 500, or at a later event",
)


def _write(srcdir: Path, *, added: bool = False) -> None:
    srcdir.mkdir(parents=True, exist_ok=True)
    (srcdir / "conf.py").write_text(
        CONF % {"added": ', "added": {"schema": {"type": "string"}}' if added else ""},
        encoding="utf-8",
    )
    (srcdir / "probe_ext.py").write_text(PROBE_EXT, encoding="utf-8")
    (srcdir / "index.rst").write_text(INDEX, encoding="utf-8")


def _build(
    make_app: Callable[..., SphinxTestApp], srcdir: Path, **kwargs: Any
) -> SphinxTestApp:
    app = make_app("html", srcdir=srcdir, **kwargs)
    app.build()
    assert build_warnings(app) == []
    return app


@pytest.fixture
def fresh(make_app: Callable[..., SphinxTestApp], tmp_path: Path) -> SphinxTestApp:
    _write(tmp_path / "src")
    return _build(make_app, tmp_path / "src", freshenv=True)


def test_it_answers_as_the_directive_matches(fresh: SphinxTestApp):
    """From a handler after sphinx-needs' own (501), and later: a type-local field and
    link type, a global field, core options, a capitalised field in any case, as
    declared; ``None`` for no such option; ``ValueError`` for no such need type."""
    for event in ("env-before-read-docs@501", "env-updated"):
        answers = fresh.resolve_answers[event]
        assert answers == {
            ("req", "asil"): "asil",
            ("req", "verifies"): "verifies",
            # a field another type declares alone is an option of every need
            # directive, as the directive matches it: it then reports the value as not
            # declared on the type (``needs.undeclared_for_type``)
            ("spec", "asil"): "asil",
            ("req", "prio"): "prio",
            ("req", "status"): "status",
            ("req", "hide"): "hide",
            ("req", "owner"): "Owner",
            ("req", "OWNER"): "Owner",
            ("req", "Owner"): "Owner",
            ("req", "nosuch"): None,
            ("req", "added"): None,
            ("nosuchtype", "status"): (
                "ValueError",
                "'nosuchtype' is no need type of the project",
            ),
        }, event


def test_the_directive_stores_each_option_under_the_name_it_resolves_to(
    fresh: SphinxTestApp,
):
    """The fence of the one candidate set: each option the need directive was written
    with is held by the need under the name ``resolve_need_option`` gives for it."""
    answers = fresh.resolve_answers["env-before-read-docs@501"]
    need = SphinxNeedsData(fresh.env).get_needs_view()["R_MAIN"]
    written = {
        "asil": "B",
        "verifies": ["R_TARGET"],
        "prio": "high",
        "status": "open",
        "hide": True,
        "owner": "me",
    }
    held = {answers["req", name]: value for name, value in written.items()}
    assert None not in held
    assert {name: need[name] for name in held} == held


def test_a_call_before_the_schema_is_built_raises_on_a_fresh_build(
    fresh: SphinxTestApp,
):
    """At ``builder-inited``, and in an ``env-before-read-docs`` handler before
    sphinx-needs' own, the error names the event to use."""
    for event in ("builder-inited", "env-before-read-docs@499"):
        assert set(fresh.resolve_answers[event].values()) == {TOO_EARLY}, event


def test_a_call_before_the_schema_is_built_raises_on_an_incremental_build(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
):
    """On an incremental build the environment still holds the previous build's
    schema at ``builder-inited``: it is never answered from; and a ``conf.py`` change
    adding a type-local field is answered from the new schema."""
    srcdir = tmp_path / "src"
    _write(srcdir)
    _build(make_app, srcdir, freshenv=True).cleanup()
    _write(srcdir, added=True)
    app = make_app("html", srcdir=srcdir, freshenv=False)
    # the previous build's schema is there, pickled, before this build builds its own
    assert SphinxNeedsData(app.env).get_schema() is not None
    app.build()
    assert build_warnings(app) == []
    for event in ("builder-inited", "env-before-read-docs@499"):
        assert set(app.resolve_answers[event].values()) == {TOO_EARLY}, event
    assert app.resolve_answers["env-before-read-docs@501"]["req", "added"] == "added"
