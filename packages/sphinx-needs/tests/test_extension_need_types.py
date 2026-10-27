"""A ``needs_types`` entry naming a need type an extension registers narrows it (#2371).

An extension registers a need type with ``add_need_type`` from a handler of its own,
usually at ``config-inited`` priority 500 -- after sphinx-needs resolves ``needs_types``
at priority 12 -- and a project's entry naming that type, bare or full, is a narrowing
of it: the keys the entry gives win, the ``title``, ``prefix``, ``color`` and ``style``
it leaves out are the extension's, and its ``fields``, ``links`` and ``inherits`` apply
as on any type the project declares. When the extension registers the type does not
matter. A bare entry does not count as declaring types (the default types are kept
beside it); a bare entry that no extension's type claims by the time the schema is
built is reported, with the spelling that attaches a rule to such a type.

The extension here is a stub in the project's ``conf.py``, so the suite needs no
sibling package (the release's compat cell has none, #2369).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from sphinx_needs.api import add_need_type, get_need_types
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.exceptions import NeedsApiConfigException
from sphinx_needs_testkit import build_warnings

#: the stub extension: adds ``story`` from a handler of the event and priority given
STUB = """\
extensions = ["sphinx_needs"]
needs_from_toml = "ubproject.toml"
needs_build_json = True

def _add_story(app, *_args):
    from sphinx_needs.api import add_need_type
    add_need_type(app, "story", "Story", "ST_", "#00ff00", "card")

def setup(app):
    app.connect({event!r}, _add_story, priority={priority})
"""

#: when the stub registers the type: before sphinx-needs resolves ``needs_types``
#: (priority 11, the TOML already read), as sphinx-test-reports does (500), after every
#: sphinx-needs handler (950), and once the builder exists
WHEN = {
    "before-resolution": ("config-inited", 11),
    "config-inited-500": ("config-inited", 500),
    "config-inited-950": ("config-inited", 950),
    "builder-inited": ("builder-inited", 500),
}

#: a bare entry narrowing the extension's ``story``: its colour, a field the type alone
#: declares, a rule on a global field, and a link type the type alone declares
BARE = """\
[needs.fields.x]
schema = { type = "string" }

[needs.types.story]
color = "#123456"

[needs.types.story.fields.points]
schema = { type = "integer", maximum = 5 }

[needs.types.story.fields.x]
derive = { kind = "copy", field = "title" }

[needs.types.story.links.refines]
target_types = ["req"]
"""

INDEX = """\
.. req:: A requirement
   :id: R_00001

.. story:: A story
   :id: ST_00001
   :points: 8
   :refines: R_00001
"""


def _project(when: tuple[str, int], config: str, index: str = INDEX) -> dict[str, Any]:
    event, priority = when
    return {
        "buildername": "needs",
        "files": [
            (Path("conf.py"), STUB.format(event=event, priority=priority)),
            (Path("ubproject.toml"), config),
            (Path("index.rst"), "Case\n====\n\n" + index),
        ],
    }


def _needs(app: Any) -> dict[str, dict[str, Any]]:
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    return data["versions"][data["current_version"]]["needs"]


def _type(app: Any, directive: str) -> dict[str, Any]:
    (entry,) = [
        t for t in NeedsSphinxConfig(app.config).types if t["directive"] == directive
    ]
    return dict(entry)


def _violations(app: Any) -> list[tuple[str, str, str | None]]:
    report = json.loads(
        Path(app.outdir, "schema_violations.json").read_text(encoding="utf-8")
    )
    return sorted(
        (need_id, violation["subtype"], violation["details"].get("field"))
        for need_id, violations in report["validation_warnings"].items()
        for violation in violations
    )


@pytest.mark.parametrize(
    "test_app",
    [pytest.param(_project(when, BARE), id=name) for name, when in WHEN.items()],
    indirect=True,
)
def test_a_bare_entry_narrows_the_extensions_type(test_app: Any) -> None:
    """The extension's title, prefix and style stay, the entry's colour wins, and the
    entry's fields and links apply to the type's needs alone, whenever the extension
    registers it. The bare entry declares no type: the default types are kept."""
    app = test_app
    app.build()
    # the one finding is the type's schema at work (below)
    assert [w.rsplit(" ", 1)[-1] for w in build_warnings(app)] == [
        "[sn_schema_violation.field_fail]"
    ]
    assert get_need_types(app) == ["req", "spec", "impl", "test", "need", "story"]
    story = _type(app, "story")
    assert {k: v for k, v in story.items() if k not in ("fields", "links")} == {
        "directive": "story",
        "title": "Story",
        "prefix": "ST_",
        "color": "#123456",
        "style": "card",
    }
    needs = _needs(app)
    assert needs["ST_00001"]["type_name"] == "Story"
    assert needs["ST_00001"]["x"] == "A story"
    assert needs["ST_00001"]["points"] == 8
    assert needs["ST_00001"]["refines"] == ["R_00001"]
    # the type-local field and link type are absent from (null, no links on) the others
    assert needs["R_00001"]["x"] is None
    assert needs["R_00001"]["points"] is None
    assert needs["R_00001"]["refines"] == []
    # the type's schema applies: 8 is above its maximum
    assert _violations(app) == [("ST_00001", "field_fail", "points")]


#: a full entry for the extension's ``story``: its title and prefix win, the colour and
#: style it leaves out are the extension's, and it declares the project's types
FULL = """\
[needs.types.story]
title = "My story"
prefix = "MS_"

[needs.types.story.fields.points]
schema = { type = "integer" }
"""


@pytest.mark.parametrize(
    "test_app",
    [
        pytest.param(
            _project(when, FULL, ".. story:: A story\n   :points: 3\n"), id=name
        )
        for name, when in WHEN.items()
    ],
    indirect=True,
)
def test_a_full_entry_narrows_the_extensions_type(test_app: Any) -> None:
    """A full entry is a narrowing too, rather than a ``NeedsApiConfigException``
    from the extension's ``add_need_type``: the keys it gives win, the ones it leaves
    out are the extension's. Giving a title and a prefix, it declares the project's
    types, so the default types are dropped, as for any such entry."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    assert get_need_types(app) == ["story"]
    story = _type(app, "story")
    assert {k: v for k, v in story.items() if k != "fields"} == {
        "directive": "story",
        "title": "My story",
        "prefix": "MS_",
        "color": "#00ff00",
        "style": "card",
    }
    (need,) = _needs(app).values()
    assert need["id"].startswith("MS_")
    assert (need["type_name"], need["points"]) == ("My story", 3)


#: a bare entry naming a type no extension registers
UNCLAIMED = """\
[needs.fields.x]
schema = { type = "string" }

[needs.types.epic.fields.x]
derive = { kind = "copy", field = "title" }
"""

#: the finding of a bare entry no extension's type claims
UNCLAIMED_WARNING = (
    "WARNING: needs_types['epic'] has no 'title' and no 'prefix'; the entry is "
    "ignored: it names no need type an extension registers, and to attach a rule to "
    "a type the project does not declare, use `derive_by_type` on the field or link "
    "type [needs.config]"
)


@pytest.mark.parametrize(
    "test_app",
    [_project(WHEN["config-inited-500"], UNCLAIMED, ".. req:: A\n   :id: R_00001\n")],
    indirect=True,
)
def test_a_bare_entry_no_extension_claims_is_reported_with_the_hint(
    test_app: Any,
) -> None:
    """A bare entry naming no default type and no type an extension registers is
    ignored, as before, and reported once the schema is built (no earlier: the
    extension may register the type late), with the spelling that attaches a rule to
    a type the project does not declare."""
    app = test_app
    app.build()
    assert build_warnings(app) == [UNCLAIMED_WARNING]
    assert "epic" not in get_need_types(app)
    assert _needs(app)["R_00001"]["x"] is None


def test_add_need_type_still_refuses_a_default_type_no_entry_names(
    make_app: Any, tmp_path: Path
) -> None:
    """The default types are not entries: an extension adding ``req`` to a project
    that configures no ``needs_types`` is refused, as before; one the project's own
    entry names is narrowed by it instead."""
    (tmp_path / "conf.py").write_text(
        'extensions = ["sphinx_needs"]\n', encoding="utf-8"
    )
    (tmp_path / "index.rst").write_text("Case\n====\n", encoding="utf-8")
    app = make_app("needs", srcdir=tmp_path)
    with pytest.raises(NeedsApiConfigException, match="req already exists"):
        add_need_type(app, "req", "Theirs", "TH_")
    named = tmp_path / "named"
    named.mkdir()
    (named / "conf.py").write_text(
        'extensions = ["sphinx_needs"]\n'
        'needs_types = [{"directive": "req", "title": "Mine", "prefix": "M_"}]\n',
        encoding="utf-8",
    )
    (named / "index.rst").write_text("Case\n====\n", encoding="utf-8")
    app = make_app("needs", srcdir=named)
    add_need_type(app, "req", "Theirs", "TH_", "#ff0000")
    assert _type(app, "req") == {
        "directive": "req",
        "title": "Mine",
        "prefix": "M_",
        "color": "#ff0000",
        "style": "node",
    }


#: a bare entry naming the need type of a configured GitHub service
SERVICE = """\
[needs.services.github-issues]

[needs.types.issue]
color = "#000000"
"""


@pytest.mark.parametrize(
    "test_app",
    [_project(WHEN["config-inited-500"], SERVICE, ".. req:: A\n   :id: R_00001\n")],
    indirect=True,
)
def test_a_bare_entry_naming_a_service_type_is_reported_as_such(test_app: Any) -> None:
    """A GitHub service's need type is not narrowed: a bare entry for it is ignored,
    and the finding says it names the service's type, which only an entry with a
    title and a prefix replaces -- not that no extension registers it."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "WARNING: needs_types['issue'] has no 'title' and no 'prefix'; the entry is "
        "ignored: it names a GitHub service's need type, which only an entry with a "
        "'title' and a 'prefix' replaces, and to attach a rule to a type the project "
        "does not declare, use `derive_by_type` on the field or link type "
        "[needs.config]"
    ]
    assert _type(app, "issue")["color"] != "#000000"


@pytest.mark.parametrize("priority", [11, 500])
def test_add_need_type_refuses_a_default_type_whenever_it_is_called(
    make_app: Any, tmp_path: Path, priority: int
) -> None:
    """A default type no entry names is refused however early the extension adds it:
    before ``needs_types`` is resolved, the list it resolves to is read, so a project
    whose bare entries keep the default types refuses ``req`` at priority 11 as at
    500, rather than accepting it there and shadowing it with the default."""
    (tmp_path / "conf.py").write_text(
        'extensions = ["sphinx_needs"]\n'
        'needs_types = {"spec": {"color": "#000000"}}\n'
        "def _add(app, config):\n"
        "    from sphinx_needs.api import add_need_type\n"
        '    add_need_type(app, "req", "Theirs", "TH_")\n'
        "def setup(app):\n"
        f'    app.connect("config-inited", _add, priority={priority})\n',
        encoding="utf-8",
    )
    (tmp_path / "index.rst").write_text("Case\n====\n", encoding="utf-8")
    with pytest.raises(Exception, match="req already exists as need type"):
        make_app("needs", srcdir=tmp_path)
