"""An unknown key in a field's or a link type's global entry, and an unknown keyword in
its ``schema``, is reported and ignored (#2206).

A misspelt key (``dervie``, ``derive_by_tpye``, ``target_type``) used to leave the entry
as if it were not there: a field meant to be derived stayed authorable, a link type meant
to be restricted was not, and the build was green. A misspelt schema keyword (``enmu``)
stopped the whole build instead, while the same keyword in a need type's own entry only
refused that entry. Each is now one ``needs.config`` warning per key, naming the entry, the
key and the keys that are known; the key is ignored and the entry kept.
"""

from __future__ import annotations

import io
import json
import textwrap
from pathlib import Path
from typing import Any

import pytest

from sphinx_needs.config import LinkOptionsType, NeedField, NeedFields, NeedLinksConfig
from sphinx_needs_testkit import build_warnings

FIELD_KEYS = (
    "default, derive, derive_by_type, description, nullable, parse_dynamic_functions, "
    "parse_variants, predicates, schema"
)
EXTRA_OPTION_KEYS = "derive, derive_by_type, description, name, schema"
LINK_KEYS = (
    "allow_dead_links, color, copy, default, derive, derive_by_type, description, "
    "incoming, outgoing, parse_conditions, parse_dynamic_functions, parse_variants, "
    "predicates, schema, style, style_end, style_part, style_start, target_types"
)
EXTRA_LINK_KEYS = (
    "allow_dead_links, color, copy, default, derive, derive_by_type, description, "
    "incoming, option, outgoing, parse_conditions, parse_dynamic_functions, "
    "parse_variants, predicates, schema, style, style_end, style_part, style_start, "
    "target_types"
)
STRING_KEYWORDS = "const, enum, format, maxLength, minLength, pattern, type"
LINK_KEYWORDS = "contains, items, maxContains, maxItems, minContains, minItems, type"
LINK_ITEM_KEYWORDS = "maxLength, minLength, pattern, type"


def _project(conf: str, index: str, files: dict[str, str] | None = None) -> dict:
    return {
        "buildername": "needs",
        "files": [
            (Path("conf.py"), textwrap.dedent(conf)),
            (Path("index.rst"), "Case\n====\n\n" + textwrap.dedent(index)),
            *(
                (Path(name), textwrap.dedent(text))
                for name, text in (files or {}).items()
            ),
        ],
    }


def _needs(app: Any) -> dict[str, dict[str, Any]]:
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    return data["versions"][data["current_version"]]["needs"]


def _config_warnings(app: Any) -> list[str]:
    return [w for w in build_warnings(app) if w.endswith("[needs.config]")]


def test_the_known_keys_are_those_of_the_typed_dicts() -> None:
    """The key sets the messages name are the configuration's own TypedDicts, so a key
    added to one of them is known at once, and the messages cannot drift from them."""
    for klass, expected in (
        (NeedFields, FIELD_KEYS),
        (NeedField, EXTRA_OPTION_KEYS),
        (NeedLinksConfig, LINK_KEYS),
        (LinkOptionsType, EXTRA_LINK_KEYS),
    ):
        keys = klass.__required_keys__ | klass.__optional_keys__
        assert ", ".join(sorted(keys)) == expected, klass


UNKNOWN_KEYS_CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_fields = {
    "total": {
        "schema": {"type": "integer"},
        "nullable": True,
        "dervie": {"kind": "count", "over": "links"},
    },
    "status": {"bogus": 1},
}
needs_extra_options = [
    {"name": "legacy", "description": "Legacy", "nullable": False},
]
needs_links = {
    "verifies": {"target_type": ["req"], "outgoing": "verifies"},
}
needs_extra_links = [{"option": "old", "bogus": 2}]
"""

UNKNOWN_KEYS_INDEX = """\
.. req:: A
   :id: REQ_1
   :total: 3
   :legacy: x

.. spec:: B
   :id: SPEC_1
   :verifies: SPEC_1
"""


@pytest.mark.parametrize(
    "test_app", [_project(UNKNOWN_KEYS_CONF, UNKNOWN_KEYS_INDEX)], indirect=True
)
def test_an_unknown_key_in_an_entry_is_reported_and_ignored(test_app: Any) -> None:
    """One warning per unknown key, in each of the four global spellings; the entry is
    kept as if the key were not there: the misspelt ``derive`` leaves ``total``
    authorable, the misspelt ``target_types`` leaves ``verifies`` unrestricted, and a
    core field's entry with an unknown key still specialises it."""
    app = test_app
    app.build()
    assert _config_warnings(app) == [
        f"WARNING: needs_extra_options['legacy'] has an unknown key 'nullable'; known keys "
        f"are {EXTRA_OPTION_KEYS}; the key is ignored [needs.config]",
        f"WARNING: needs_fields['total'] has an unknown key 'dervie'; known keys are "
        f"{FIELD_KEYS}; the key is ignored [needs.config]",
        f"WARNING: needs_fields['status'] has an unknown key 'bogus'; known keys are "
        f"{FIELD_KEYS}; the key is ignored [needs.config]",
        f"WARNING: needs_links['verifies'] has an unknown key 'target_type'; known keys "
        f"are {LINK_KEYS}; the key is ignored [needs.config]",
        f"WARNING: needs_extra_links['old'] has an unknown key 'bogus'; known keys are "
        f"{EXTRA_LINK_KEYS}; the key is ignored [needs.config]",
    ]
    needs = _needs(app)
    assert needs["REQ_1"]["total"] == 3
    assert needs["REQ_1"]["legacy"] == "x"
    assert needs["SPEC_1"]["verifies"] == ["SPEC_1"]


TOML_CONF = """\
extensions = ["sphinx_needs"]
needs_from_toml = "ubproject.toml"
needs_build_json = True
"""

TOML = """\
[needs.fields.total]
schema = { type = "integer" }
nullable = true
derive_by_tpye = { req = { kind = "count", over = "links" } }

[needs.links.verifies]
outgoing = "verifies"
target_type = ["req"]
"""


@pytest.mark.parametrize(
    "test_app",
    [_project(TOML_CONF, UNKNOWN_KEYS_INDEX, {"ubproject.toml": TOML})],
    indirect=True,
)
def test_an_unknown_key_in_a_toml_table_is_reported_and_ignored(test_app: Any) -> None:
    """The ``ubproject.toml`` tables are the same entries, and reported the same way."""
    app = test_app
    app.build()
    assert _config_warnings(app) == [
        f"WARNING: needs_fields['total'] has an unknown key 'derive_by_tpye'; known keys "
        f"are {FIELD_KEYS}; the key is ignored [needs.config]",
        f"WARNING: needs_links['verifies'] has an unknown key 'target_type'; known keys "
        f"are {LINK_KEYS}; the key is ignored [needs.config]",
    ]
    assert _needs(app)["REQ_1"]["total"] == 3


KEYWORDS_CONF = """\
from sphinx_needs.api import add_field

extensions = ["sphinx_needs"]
needs_build_json = True
needs_fields = {
    "asil": {"schema": {"type": "string", "enmu": ["A", "B"]}, "nullable": True},
    "level": {"schema": {"type": "string", "minimum": 1}, "nullable": True},
    "labels": {
        "schema": {
            "type": "array",
            "items": {"type": "string", "enmu": ["a"]},
            "contains": {"type": "string", "enmu": ["b"]},
        },
        "nullable": True,
    },
    "status": {"schema": {"enmu": ["open"]}},
}
needs_links = {
    "verifies": {
        "schema": {
            "uniqueItems": True,
            "items": {"enum": ["X"]},
            "contains": {"enum": ["Y"], "minLength": 1},
        },
    },
}


def setup(app):
    add_field("ext", "An extension's field", schema={"type": "string", "bogus": 1})
"""

KEYWORDS_INDEX = """\
.. req:: A
   :id: REQ_1
   :asil: not-an-asil
   :level: x
   :labels: b
   :status: closed
   :ext: e
   :verifies: REQ_1
"""


@pytest.mark.parametrize(
    "test_app", [_project(KEYWORDS_CONF, KEYWORDS_INDEX)], indirect=True
)
def test_an_unknown_schema_keyword_is_reported_and_dropped(test_app: Any) -> None:
    """A keyword the schema of its type does not have is one warning, and dropped: the
    field keeps the rest of its schema, and the build goes on (it stopped the build,
    ``Invalid schema: Additional properties are not allowed``). That holds for a
    field's schema, its ``items`` and ``contains``, a core field's specialisation
    (whose type it inherits), a link type's schema, its ``items`` and ``contains``,
    and a field an extension registers. The configuration itself keeps them."""
    app = test_app
    app.build()
    assert _config_warnings(app) == [
        f"WARNING: needs_fields['status'].schema has an unknown keyword 'enmu'; known "
        f"keywords of a schema of type 'string' are {STRING_KEYWORDS}; the keyword is ignored "
        "[needs.config]",
        f"WARNING: add_field['ext'].schema has an unknown keyword 'bogus'; known "
        f"keywords of a schema of type 'string' are {STRING_KEYWORDS}; the keyword is ignored "
        "[needs.config]",
        f"WARNING: needs_fields['asil'].schema has an unknown keyword 'enmu'; known "
        f"keywords of a schema of type 'string' are {STRING_KEYWORDS}; the keyword is ignored "
        "[needs.config]",
        f"WARNING: needs_fields['level'].schema has an unknown keyword 'minimum'; known "
        f"keywords of a schema of type 'string' are {STRING_KEYWORDS}; the keyword is ignored "
        "[needs.config]",
        f"WARNING: needs_fields['labels'].schema.items has an unknown keyword 'enmu'; "
        f"known keywords of a schema of type 'string' are {STRING_KEYWORDS}; the keyword is "
        "ignored [needs.config]",
        f"WARNING: needs_fields['labels'].schema.contains has an unknown keyword "
        f"'enmu'; known keywords of a schema of type 'string' are {STRING_KEYWORDS}; the "
        "keyword is ignored [needs.config]",
        f"WARNING: needs_links['verifies'].schema has an unknown keyword 'uniqueItems'; "
        f"known keywords of a link type's schema are {LINK_KEYWORDS}; the keyword is "
        "ignored [needs.config]",
        f"WARNING: needs_links['verifies'].schema.items has an unknown keyword 'enum'; "
        f"known keywords of a link type's items are {LINK_ITEM_KEYWORDS}; the keyword "
        "is ignored [needs.config]",
        f"WARNING: needs_links['verifies'].schema.contains has an unknown keyword "
        f"'enum'; known keywords of a link type's contains are {LINK_ITEM_KEYWORDS}; the "
        "keyword is ignored [needs.config]",
    ]
    # the keywords are dropped from a copy: the configuration is not changed
    fields, links = app.config.needs_fields, app.config.needs_links
    assert fields["asil"]["schema"] == {"type": "string", "enmu": ["A", "B"]}
    assert fields["status"]["schema"]["enmu"] == ["open"]
    assert fields["labels"]["schema"]["items"]["enmu"] == ["a"]
    assert fields["labels"]["schema"]["contains"]["enmu"] == ["b"]
    assert links["verifies"]["schema"]["uniqueItems"] is True
    assert links["verifies"]["schema"]["items"]["enum"] == ["X"]
    assert links["verifies"]["schema"]["contains"]["enum"] == ["Y"]
    # nothing else is reported: the dropped keywords constrain nothing
    assert build_warnings(app) == _config_warnings(app)
    need = _needs(app)["REQ_1"]
    assert need["asil"] == "not-an-asil"
    assert need["level"] == "x"
    assert need["labels"] == ["b"]
    assert need["status"] == "closed"
    assert need["ext"] == "e"
    assert need["verifies"] == ["REQ_1"]


TOML_KEYWORDS = """\
[needs.fields.efforts]
schema.type = "string"
schema.unknown = "unknown"

[needs.links.links]
outgoing = "links"
incoming = "linked by"
schema.unknown = "unknown"
"""


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            TOML_CONF,
            ".. req:: A\n   :id: REQ_1\n   :efforts: e\n   :links: REQ_1\n",
            {"ubproject.toml": TOML_KEYWORDS},
        )
    ],
    indirect=True,
)
def test_an_unknown_schema_keyword_in_a_toml_table_is_reported(test_app: Any) -> None:
    """The ``ubproject.toml`` tables are the same entries: the two cases that stopped the
    build (``Invalid field 'efforts'`` and ``Invalid link 'links'``, each ``Additional
    properties are not allowed ('unknown' was unexpected)``) are each one warning."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "WARNING: needs_fields['efforts'].schema has an unknown keyword 'unknown'; "
        f"known keywords of a schema of type 'string' are {STRING_KEYWORDS}; the "
        "keyword is ignored [needs.config]",
        "WARNING: needs_links['links'].schema has an unknown keyword 'unknown'; known "
        f"keywords of a link type's schema are {LINK_KEYWORDS}; the keyword is "
        "ignored [needs.config]",
    ]
    need = _needs(app)["REQ_1"]
    assert (need["efforts"], need["links"]) == ("e", ["REQ_1"])


OWN_NAME_CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_fields = {
    "asil": {"name": "asil", "schema": {"type": "string"}, "nullable": True},
    "level": {"name": "lvl", "schema": {"type": "string"}, "nullable": True},
}
needs_links = {
    "verifies": {"option": "verifies"},
    "blocks": {"option": "block"},
}
"""


@pytest.mark.parametrize(
    "test_app",
    [_project(OWN_NAME_CONF, ".. req:: A\n   :id: REQ_1\n   :level: x\n")],
    indirect=True,
)
def test_a_name_left_from_the_list_spelling_is_accepted_where_it_repeats(
    test_app: Any,
) -> None:
    """A ``name`` in a ``needs_fields`` entry, or an ``option`` in a ``needs_links``
    entry, is the key the list spelling (``needs_extra_options``,
    ``needs_extra_links``) names an entry by; the table spelling takes the name from
    its key, and has always ignored it. Repeating the entry's name, as a migrated entry
    does, it is accepted in silence; giving another name, it is reported, and ignored
    as before: the entry keeps its key's name."""
    app = test_app
    app.build()
    assert _config_warnings(app) == [
        "WARNING: needs_fields['level'] gives 'name' = 'lvl', which differs from the "
        "entry's name 'level'; it is ignored [needs.config]",
        "WARNING: needs_links['blocks'] gives 'option' = 'block', which differs from "
        "the entry's name 'blocks'; it is ignored [needs.config]",
    ]
    need = _needs(app)["REQ_1"]
    assert need["level"] == "x"
    assert "lvl" not in need
    assert need["blocks"] == []
    assert "block" not in need


def test_an_entry_that_is_not_a_table_gets_no_unknown_key_per_character(
    make_app: Any, tmp_path: Path
) -> None:
    """A ``needs_links`` entry that is a string fails as before (its reader cannot
    complete it), and is not first read as a mapping of its characters: no
    ``unknown key 'a'`` per character."""
    (tmp_path / "conf.py").write_text(
        'extensions = ["sphinx_needs"]\nneeds_links = {"rel": "abc"}\n'
    )
    (tmp_path / "index.rst").write_text("Case\n====\n")
    warning = io.StringIO()
    with pytest.raises(Exception):  # noqa: B017  -- the reader's own failure
        make_app(srcdir=tmp_path, freshenv=True, warning=warning)
    assert "unknown key" not in warning.getvalue()
