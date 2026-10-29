"""An entry narrowing an extension's need type takes every key of a need type's entry.

A ``needs_types`` entry naming a need type an extension registers narrows it (#2371),
and the per-type keys a project type's entry takes (#2395) behave on it exactly as on a
type the project declares: a ``severity`` on its declaration of a field, a count of the
links it receives (``back_links``), the shape of its ids (``id_regex``). None of them is
an unknown key or a near name (#2388), and a field the extension declares on the type
alone is written nullable in needs.json whatever the severity (both writers' rules).

The narrowing only narrows: an entry that would widen the extension's declaration of a
field -- loosen a schema keyword, make it nullable, re-type it -- is refused by the same
check that refuses it on a project type (``narrowing_problems``), since a type's
declaration starts from the extension's. The tests at the end pin that.

The extension is a stub in the project's ``conf.py``, so the suite needs no sibling
package (the release's compat cell has none, #2369).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs_testkit import build_warnings

#: the stub extension: adds ``story``, and declares ``points`` (not nullable, with a
#: default, constrained) and ``must`` (not nullable, no default) on it alone, from a
#: handler of the event and priority given
STUB = """\
extensions = ["sphinx_needs"]
needs_from_toml = "ubproject.toml"
needs_build_json = True

def _register(app, *_args):
    from sphinx_needs.api import add_field, add_need_type
    add_need_type(app, "story", "Story", "ST_", "#00ff00", "card")
    add_field(
        "points",
        "Story points",
        types=["story"],
        schema={{"type": "integer", "maximum": 5, "enum": [1, 2, 3, 5]}},
        nullable=False,
        default=1,
    )
    add_field(
        "tags2",
        "Labels",
        types=["story"],
        schema={{"type": "array", "items": {{"type": "string"}}, "maxItems": 2}},
    )
    add_field(
        "must",
        "Required",
        types=["story"],
        schema={{"type": "string"}},
        nullable=False,
    )

def setup(app):
    app.connect({event!r}, _register, priority={priority})
"""

#: when the stub registers: as sphinx-test-reports does (500), and once the builder
#: exists
WHEN = {
    "config-inited-500": ("config-inited", 500),
    "builder-inited": ("builder-inited", 500),
}

#: the project's own type, and the shape of the entry narrowing ``story``: bare, or
#: with a title and a prefix (the keys the per-type tables are added to)
SHAPES = {
    "bare": "",
    "full": 'title = "Story"\nprefix = "ST_"\n',
}

TYPES = """\
[needs.types.req]
title = "Requirement"
prefix = "R_"

[needs.types.story]
{shape}{story}
"""


def _project(
    when: str, shape: str, config: str, index: str, story: str = ""
) -> dict[str, Any]:
    event, priority = WHEN[when]
    return {
        "buildername": "needs",
        "files": [
            (Path("conf.py"), STUB.format(event=event, priority=priority)),
            (
                Path("ubproject.toml"),
                TYPES.format(shape=SHAPES[shape], story=story) + "\n" + config,
            ),
            (Path("index.rst"), "Case\n====\n\n" + index),
        ],
    }


def _params(config: str, index: str) -> list[Any]:
    return [
        pytest.param(_project(when, shape, config, index), id=f"{shape}-{when}")
        for shape in SHAPES
        for when in WHEN
    ]


def _version(app: Any) -> dict[str, Any]:
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    return data["versions"][data["current_version"]]


def _violations(app: Any) -> list[tuple[str, str, str | None, str]]:
    report = json.loads(
        Path(app.outdir, "schema_violations.json").read_text(encoding="utf-8")
    )
    return sorted(
        (
            need_id,
            violation["subtype"],
            violation["details"].get("field"),
            violation["type"],
        )
        for need_id, violations in report["validation_warnings"].items()
        for violation in violations
    )


def _codes(app: Any) -> list[str]:
    """The ``[type.subtype]`` of every warning of the build."""
    return [w.rsplit(" ", 1)[-1] for w in build_warnings(app)]


# --- (b) the per-type keys on a narrowed extension type ------------------------------

SEVERITY = """\
[needs.types.story.fields.points]
schema = { maximum = 3 }
severity = "warning"

[needs.types.story.fields.must]
severity = "warning"
"""

SEVERITY_INDEX = """\
.. req:: A requirement
   :id: R_00001

.. story:: Too many points
   :id: ST_00001
   :points: 5
   :must: x

.. story:: Without the required field
   :id: ST_00002
"""


@pytest.mark.parametrize("test_app", _params(SEVERITY, SEVERITY_INDEX), indirect=True)
def test_a_severity_on_a_narrowed_extension_type(test_app: Any) -> None:
    """``severity = "warning"`` on the entry's declaration of an extension's field is
    the severity of every constraint of the type's declaration, the extension's
    included, as on a project type: a value above the narrowed maximum is a warning,
    and a need without the extension's not-nullable field is created, null, and
    reported at that severity. No key of the entry is unknown or a near name."""
    app = test_app
    app.build()
    assert _codes(app) == [
        "[sn_schema_warning.field_fail]",
        "[sn_schema_warning.field_fail]",
    ]
    assert _violations(app) == [
        ("ST_00001", "field_fail", "points", "sn_schema_warning"),
        ("ST_00002", "field_fail", "must", "sn_schema_warning"),
    ]
    needs = _version(app)["needs"]
    assert (needs["ST_00001"]["points"], needs["ST_00002"]["must"]) == (5, None)
    assert needs["R_00001"]["must"] is None


BACK_LINKS = """\
[needs.types.story.back_links.links]
schema = { minItems = 1 }
"""

BACK_LINKS_INDEX = """\
.. req:: A requirement
   :id: R_00001
   :links: ST_00001

.. story:: Linked to
   :id: ST_00001
   :must: x

.. story:: Not linked to
   :id: ST_00002
   :must: x
"""


@pytest.mark.parametrize(
    "test_app", _params(BACK_LINKS, BACK_LINKS_INDEX), indirect=True
)
def test_a_back_links_count_on_a_narrowed_extension_type(test_app: Any) -> None:
    """``[needs.types.story.back_links.links]`` counts the links each need of the
    extension's type receives, as on a project type: the story no need links to is a
    ``link_fail`` of ``links_back``."""
    app = test_app
    app.build()
    assert _codes(app) == ["[sn_schema_violation.link_fail]"]
    assert _violations(app) == [
        ("ST_00002", "link_fail", "links_back", "sn_schema_violation")
    ]
    schema = SphinxNeedsData(app.env).get_schema()
    assert "links_back" in schema.for_type("story").back_links()
    assert not schema.for_type("req").back_links()


ID_REGEX = 'id_regex = "^ST_0000[12]$"\n'

ID_REGEX_INDEX = """\
.. req:: A requirement
   :id: R_00003

.. story:: Matches
   :id: ST_00001
   :must: x

.. story:: Does not match
   :id: ST_00003
   :must: x
"""


@pytest.mark.parametrize(
    "test_app",
    [
        pytest.param(
            _project(when, shape, "", ID_REGEX_INDEX, story=ID_REGEX),
            id=f"{shape}-{when}",
        )
        for shape in SHAPES
        for when in WHEN
    ],
    indirect=True,
)
def test_an_id_regex_on_a_narrowed_extension_type(test_app: Any) -> None:
    """``id_regex`` on the entry narrowing the extension's type is matched against the
    ids of its needs, as on a project type: a need whose id does not match is not
    created; the project's own type is not affected."""
    app = test_app
    app.build()
    (warning,) = build_warnings(app)
    assert warning.endswith(
        "WARNING: Need could not be created: Given ID 'ST_00003' does not match the "
        "id_regex '^ST_0000[12]$' of need type 'story' [needs.create_need]"
    ), warning
    assert sorted(_version(app)["needs"]) == ["R_00003", "ST_00001"]


# --- (a) needs.json: both writers' nullable rules on an extension's field ------------

NULLABLE_INDEX = """\
.. req:: A requirement
   :id: R_00001

.. story:: A story
   :id: ST_00001
   :must: x
"""


@pytest.mark.parametrize(
    "test_app",
    [
        pytest.param(
            _project("config-inited-500", "bare", config, NULLABLE_INDEX), id=name
        )
        for name, config in {
            "violation": "",
            "warning": '[needs.types.story.fields.must]\nseverity = "warning"\n',
        }.items()
    ],
    indirect=True,
)
def test_an_extensions_type_local_field_is_written_nullable(test_app: Any) -> None:
    """The needs.json schema writes a field an extension declares on its types alone
    nullable (the other types' needs hold null), and so a field a need type declares
    not nullable below ``violation`` (#2395): the two rules meet on the extension's
    ``must``, written the same either way, with its null default, while ``points``
    keeps the extension's literal default."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    properties = _version(app)["needs_schema"]["properties"]
    assert properties["must"] == {
        "type": ["string", "null"],
        "description": "Required",
        "field_type": "extra",
        "default": None,
    }
    assert properties["points"] == {
        "type": ["integer", "null"],
        "description": "Story points",
        "field_type": "extra",
        "default": 1,
    }


# --- (c) the unknown-key and near-name checks see a narrowing entry ------------------

ALL_KEYS = """\
[needs.types.story.fields.points]
schema = { maximum = 3 }
severity = "info"

[needs.types.story.back_links.links]
schema = { maxItems = 3 }

[needs.types.req.fields.points]
"""


@pytest.mark.parametrize(
    "test_app",
    [
        pytest.param(
            _project(
                "config-inited-500",
                shape,
                ALL_KEYS,
                NULLABLE_INDEX,
                story='id_regex = "^ST_"\n',
            ),
            id=shape,
        )
        for shape in SHAPES
    ],
    indirect=True,
)
def test_a_narrowing_entry_is_no_unknown_key_and_no_near_name(test_app: Any) -> None:
    """Every key a narrowing entry of an extension's type may give -- ``id_regex``, a
    field's ``severity``, ``back_links`` -- and a project type's entry naming the
    extension's field (which declares it there) are known: the build is clean."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    assert SphinxNeedsData(app.env).get_schema().declaring_types("points") == {
        "story",
        "req",
    }


@pytest.mark.parametrize(
    "test_app",
    [
        pytest.param(
            _project(
                "config-inited-500",
                "bare",
                "[needs.types.story.fields.pionts]\nschema = { type = 'integer' }\n",
                NULLABLE_INDEX,
            ),
            id="bare",
        )
    ],
    indirect=True,
)
def test_a_misspelt_field_of_a_narrowing_entry_is_a_near_name(test_app: Any) -> None:
    """A field a narrowing entry declares alone whose name is close to the
    extension's field is reported, "did you mean", as on a project type."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "WARNING: needs_types['story'].fields['pionts'] declares a field of need types "
        "'story' alone; did you mean 'points'? [needs.type_near_name]"
    ]


# --- narrow only: an entry widening the extension's declaration is refused -----------

#: (the entry's declaration of an extension's field, the finding): each widens the
#: extension's declaration and is refused, the whole field entry ignored -- its
#: narrowing keys too -- exactly as on a project type narrowing a ``needs_fields`` entry
WIDENING = {
    "loosened-maximum": (
        "[needs.types.story.fields.points]\nschema = { maximum = 10, minimum = 1 }\n",
        "WARNING: needs_types['story'].fields['points'] widens the field: Child "
        "'maximum' 10 is greater than parent 'maximum' 5. [needs.type_widening]",
    ),
    "loosened-enum": (
        "[needs.types.story.fields.points]\nschema = { enum = [1, 2, 3, 5, 8] }\n",
        "WARNING: needs_types['story'].fields['points'] widens the field: Child 'enum' "
        "values [1, 2, 3, 5, 8] are not a subset of parent 'enum' values [1, 2, 3, 5]. "
        "[needs.type_widening]",
    ),
    "nullable": (
        "[needs.types.story.fields.points]\nnullable = true\nschema = { maximum = 3 }\n",
        "WARNING: needs_types['story'].fields['points'] widens the field: Cannot "
        "change 'nullable' from False to True in child. [needs.type_widening]",
    ),
    "raised-maxItems": (
        "[needs.types.story.fields.tags2]\nschema = { maxItems = 5, minItems = 1 }\n",
        "WARNING: needs_types['story'].fields['tags2'] widens the field: Child "
        "'maxItems' 5 is greater than parent 'maxItems' 2. [needs.type_widening]",
    ),
    "re-typed": (
        "[needs.types.story.fields.points]\nschema = { type = 'string' }\n",
        "WARNING: needs_types['story'].fields['points'] cannot be declared with type "
        "'string' (items None): its type is 'integer' (items None), as need type "
        "'story' declares it; the entry is ignored [needs.type_conflict]",
    ),
}

WIDENING_INDEX = """\
.. story:: A story
   :id: ST_00001
   :must: x
"""


@pytest.mark.parametrize(
    ("test_app", "finding"),
    [
        pytest.param(
            _project(when, "bare", config, WIDENING_INDEX),
            finding,
            id=f"{name}-{when}",
        )
        for name, (config, finding) in WIDENING.items()
        for when in WHEN
    ],
    indirect=["test_app"],
)
def test_an_entry_widening_an_extensions_field_is_refused(
    test_app: Any, finding: str
) -> None:
    """A narrowing entry cannot widen the extension's declaration of a field: a
    loosened schema keyword, ``nullable = true`` where the extension says not, a
    raised ``maxItems`` are ``needs.type_widening``, and a changed type
    ``needs.type_conflict``; the entry is ignored, and the type keeps the
    extension's declaration."""
    app = test_app
    app.build()
    assert build_warnings(app) == [finding]
    story = SphinxNeedsData(app.env).get_schema().for_type("story")
    points = story.get_extra_field("points")
    tags2 = story.get_extra_field("tags2")
    assert points is not None
    assert tags2 is not None
    assert (points.schema, points.nullable) == (
        {"type": "integer", "maximum": 5, "enum": [1, 2, 3, 5]},
        False,
    )
    assert tags2.schema == {
        "type": "array",
        "items": {"type": "string"},
        "maxItems": 2,
    }
