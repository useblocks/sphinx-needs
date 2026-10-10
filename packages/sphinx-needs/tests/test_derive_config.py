"""Declared derived fields: how a ``derive`` rule is read, checked and enforced.

A field or link type whose ``needs_fields`` / ``needs_links`` entry carries a ``derive``
table is derived: an author cannot set it, in a need or by a ``needextend``
(``needs.derive_authored``, the value ignored), and it is marked ``readOnly`` in the
schema ``needs.json`` exports. A rule that cannot be read is one
``needs.derive_invalid`` warning, and the field stays derived, holding its empty value.
Their values are computed by the rules (``test_derive_kinds.py``).
"""

import dataclasses
import json
from pathlib import Path

import pytest

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.derive import DeriveInvalid, DeriveRule, parse_derive
from sphinx_needs.needs_schema import (
    FieldSchema,
    FieldsSchema,
    LinkDisplayConfig,
    LinkSchema,
)
from sphinx_needs_testkit import build_warnings

_CLOSED = (
    "the field cannot be set in a need or by a needextend, and holds its empty value"
)
_CLOSED_LINK = (
    "the link type cannot be set in a need or by a needextend, and holds no links"
)


def _invalid(name: str, reason: str) -> str:
    return (
        f"WARNING: Invalid derive of field {name!r}: {reason}; {_CLOSED} "
        "[needs.derive_invalid]"
    )


def _invalid_link(name: str, reason: str) -> str:
    return (
        f"WARNING: Invalid derive of link type {name!r}: {reason}; {_CLOSED_LINK} "
        "[needs.derive_invalid]"
    )


#: The findings of ``doc_derive_config``, in the order they are reported: the rules on
#: a core field or link type, then every field by name, then every link type by name,
#: then the authored values as the needs are read.
EXPECTED_WARNINGS = [
    "WARNING: Invalid derive of link type 'parent_needs': a core link type cannot "
    "carry a derive rule in this release; the rule is ignored [needs.derive_invalid]",
    "WARNING: Invalid derive of field 'status': a core field cannot carry a derive "
    "rule in this release; the rule is ignored [needs.derive_invalid]",
    _invalid("bad_after", "kind 'copy': the role 'after' must be \"derived\""),
    _invalid(
        "bad_all_result",
        "kind 'all' gives a boolean, which the field's schema (string) cannot hold",
    ),
    _invalid(
        "bad_any_both", "kind 'any' takes exactly one of the roles 'field' and 'test'"
    ),
    _invalid(
        "bad_any_type",
        "kind 'any': the role 'field' names 'hours' (number), which is not a boolean",
    ),
    _invalid(
        "bad_collect_result",
        "kind 'collect' gives an array of number, which the field's schema (an array "
        "of string) cannot hold",
    ),
    _invalid(
        "bad_copy_both",
        "kind 'copy' takes one of the roles 'from' and 'over', not both",
    ),
    _invalid(
        "bad_copy_type",
        "kind 'copy': the role 'field' names 'owner' (string), which the field's "
        "schema (number) cannot hold",
    ),
    _invalid(
        "bad_count_result",
        "kind 'count' gives an integer, which the field's schema (string) cannot hold",
    ),
    _invalid(
        "bad_cycle_a",
        "kind 'copy': the role 'field' reads 'bad_cycle_b', whose rule reads this field "
        "back (bad_cycle_a -> bad_cycle_b -> bad_cycle_a), so no need can compute it",
    ),
    _invalid(
        "bad_cycle_b",
        "kind 'copy': the role 'field' reads 'bad_cycle_a', whose rule reads this field "
        "back (bad_cycle_b -> bad_cycle_a -> bad_cycle_b), so no need can compute it",
    ),
    "WARNING: Invalid derive of field 'bad_default': kind 'copy': 'default' cannot be "
    "given beside derive, and is ignored; the rule applies [needs.derive_invalid]",
    # a rule that cannot be read is reported for that alone, not for its default
    _invalid(
        "bad_field_and_default",
        "kind 'copy': the role 'field' names 'nope', which is not a field, a link type "
        "or the back links of one",
    ),
    _invalid(
        "bad_field_unknown",
        "kind 'copy': the role 'field' names 'nope', which is not a field, a link type "
        "or the back links of one",
    ),
    _invalid(
        "bad_hash_back",
        "kind 'hash': the role 'fields' names the back links 'links_back', which cannot "
        "be hashed",
    ),
    _invalid(
        "bad_hash_result",
        "kind 'hash' gives a string, which the field's schema (number) cannot hold",
    ),
    _invalid(
        "bad_include_self",
        "kind 'max' takes the role 'include_self' only with 'transitive = true'",
    ),
    _invalid(
        "bad_kind",
        "the kind 'expr' is unknown; the kinds are copy, sum, count, min, max, any, "
        "all, collect, hash, links, content_links",
    ),
    _invalid(
        "bad_link_kind",
        "kind 'links' computes a link list, so it is declared on a link type "
        "(needs_links), not on a field",
    ),
    _invalid(
        "bad_max_order",
        "kind 'max': the role 'field' names 'owner' (string), which has no order; "
        "min and max read a number or a string with an enum",
    ),
    _invalid(
        "bad_min_result",
        "kind 'min': the role 'field' names 'hours' (number), which the field's schema "
        "(string) cannot hold",
    ),
    _invalid("bad_missing", "kind 'sum' requires the role 'over'"),
    _invalid("bad_no_kind", "it has no 'kind'"),
    _invalid("bad_not_table", "it is not a table naming a 'kind'"),
    _invalid(
        "bad_over",
        "kind 'sum': the role 'over' names 'nope', which is not a link type or the back "
        "links of one",
    ),
    "WARNING: Invalid derive of field 'bad_predicates': kind 'copy': 'predicates' "
    "cannot be given beside derive, and is ignored; the rule applies "
    "[needs.derive_invalid]",
    # each path follows the reads, from the field back to it
    _invalid(
        "bad_ring_a",
        "kind 'copy': the role 'field' reads 'bad_ring_c', whose rule reads this field "
        "back (bad_ring_a -> bad_ring_c -> bad_ring_b -> bad_ring_a), so no need can "
        "compute it",
    ),
    _invalid(
        "bad_ring_b",
        "kind 'copy': the role 'field' reads 'bad_ring_a', whose rule reads this field "
        "back (bad_ring_b -> bad_ring_a -> bad_ring_c -> bad_ring_b), so no need can "
        "compute it",
    ),
    _invalid(
        "bad_ring_c",
        "kind 'copy': the role 'field' reads 'bad_ring_b', whose rule reads this field "
        "back (bad_ring_c -> bad_ring_b -> bad_ring_a -> bad_ring_c), so no need can "
        "compute it",
    ),
    _invalid("bad_role_not_taken", "kind 'sum' does not take the role 'test'"),
    _invalid("bad_role_type", "kind 'max': the role 'transitive' must be a boolean"),
    _invalid(
        "bad_select_list",
        "kind 'copy': the role 'select' is \"list\", which needs an array field, and "
        "the field's schema is string",
    ),
    _invalid(
        "bad_select_list_item",
        "kind 'copy': the role 'select' is \"list\", so the rule gives an array of "
        "string, which the field's schema (an array of number) cannot hold",
    ),
    _invalid(
        "bad_select_no_over", "kind 'copy' takes the role 'select' only with 'over'"
    ),
    _invalid(
        "bad_sum_result",
        "kind 'sum' gives an integer, which the field's schema (string) cannot hold",
    ),
    _invalid(
        "bad_sum_type",
        "kind 'sum': the role 'field' names 'owner' (string), which is not a number",
    ),
    _invalid("bad_unknown_role", "kind 'copy': 'frm' is not a role"),
    _invalid(
        "bad_where_c",
        "kind 'count': the role 'where' calls 'c.this_doc', which a declared rule "
        "cannot read",
    ),
    _invalid(
        "bad_where_current",
        "kind 'count': the role 'where' names 'current_need', which a declared rule "
        "cannot read",
    ),
    _invalid(
        "bad_where_needs",
        "kind 'count': the role 'where' names 'needs', which a declared rule cannot read",
    ),
    _invalid(
        "bad_where_syntax",
        "kind 'count': the role 'where' does not parse as a filter (invalid syntax)",
    ),
    _invalid_link(
        "bad_link_empty_where",
        "kind 'links' has an empty 'where', which would link every need",
    ),
    _invalid_link(
        "bad_link_join",
        "kind 'links': the 'join' role is reserved and not available yet",
    ),
    _invalid_link(
        "bad_link_value_kind",
        "kind 'sum' computes a value, so it is declared on a field (needs_fields), not "
        "on a link type",
    ),
    "<srcdir>/index.rst:11: WARNING: Field 'd_total' is derived (kind 'sum') and "
    "cannot be set in a need; the value '99' is ignored [needs.derive_authored]",
    "<srcdir>/index.rst:11: WARNING: Link type 'mentions' is derived "
    "(kind 'content_links') and cannot be set in a need; the value 'REQ_001' is "
    "ignored [needs.derive_authored]",
    "<srcdir>/index.rst:20: WARNING: Field 'd_owner' is derived (kind 'copy') and "
    'cannot be set in a need; the value \'[[copy("owner", "REQ_001")]]\' is ignored '
    "[needs.derive_authored]",
    "<srcdir>/index.rst:28: WARNING: Field 'd_total' is derived (kind 'sum') and "
    "cannot be set by a needextend; the option 'd_total' is ignored "
    "[needs.derive_authored]",
]


def _built(app) -> dict:
    """The current version of the ``needs.json`` the last build wrote."""
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    return data["versions"][data["current_version"]]


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "needs", "srcdir": "doc_test/doc_derive_config"}],
    indirect=True,
)
def test_derive_findings(test_app):
    """Every rule that cannot be read is one ``needs.derive_invalid``, naming the kind
    and the role; every authored value of a derived field is one
    ``needs.derive_authored``, at the need or the ``needextend``.

    The valid rules (one per kind, ``d_*`` and three link types) give no finding,
    nor does the imported need that carries derived values.
    """
    app = test_app
    app.build()
    assert build_warnings(app) == EXPECTED_WARNINGS


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "needs", "srcdir": "doc_test/doc_derive_config"}],
    indirect=True,
)
def test_derived_fields_hold_their_rules_value(test_app):
    """A derived field holds its rule's value; what an author wrote is ignored.

    ``SPEC_AUTH`` wrote ``d_total`` 99 and ``mentions`` ``REQ_001``, ``SPEC_CALL`` a call
    in ``d_owner``, a ``needextend`` set ``SPEC_EXT``'s ``d_total``: each holds the
    rule's value. A rule that cannot be read leaves its field empty (``bad_kind``); one
    with a ``default`` beside it applies, without the default (``bad_default``). An
    imported need keeps the values it carries. A rule on a core field is ignored:
    ``status`` is authored as usual.
    """
    app = test_app
    app.build()
    needs = _built(app)["needs"]
    auth, call, ext, req = (
        needs[i] for i in ("SPEC_AUTH", "SPEC_CALL", "SPEC_EXT", "REQ_001")
    )
    assert (auth["d_total"], call["d_total"], ext["d_total"]) == (3.0, 0.0, 0.0)
    assert auth["mentions"] == ["REQ_001"]
    assert call["d_owner"] is None
    assert (req["d_title"], req["d_from"], req["d_late"]) == (
        "Requirement one",
        "alice",
        "alice",
    )
    assert (req["d_asil"], req["d_verified"], req["d_any"]) == ("B", True, False)
    assert auth["d_owners"] == ["alice"]
    assert (auth["related_open"], req["related_open"]) == (["REQ_001"], [])
    assert {needs[i]["mentioned_reqs"][0] for i in needs if i != "IMP_001"} == {
        "REQ_001"
    }
    for need_id in ("REQ_001", "SPEC_AUTH", "SPEC_CALL", "SPEC_EXT"):
        assert needs[need_id]["bad_kind"] is None, need_id
    assert (req["bad_default"], auth["bad_default"]) == ("alice", None)
    imported = needs["IMP_001"]
    assert imported["d_total"] == 7.5
    assert imported["mentions"] == ["REQ_001"]
    assert imported["d_title"] is None
    assert req["status"] == "open"
    assert ext["status"] == "draft"


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "needs", "srcdir": "doc_test/doc_derive_config"}],
    indirect=True,
)
def test_derived_fields_are_read_only_in_the_export(test_app):
    """``needs.json``'s schema marks every derived field and link type ``readOnly``.

    So an importer takes the value as data. A rule that cannot be read still makes
    the field derived; a field or link type without a rule, a back link, and a core
    field whose rule is ignored are not marked.
    """
    app = test_app
    app.build()
    properties = _built(app)["needs_schema"]["properties"]
    read_only = sorted(
        name for name, prop in properties.items() if prop.get("readOnly") is True
    )
    assert read_only == sorted(
        [
            *(
                name
                for name in properties
                if name.startswith(("d_", "bad_"))
                and properties[name]["field_type"] != "backlinks"
            ),
            "mentions",
            "mentioned_reqs",
            "related_open",
        ]
    )
    for name in ("hours", "status", "links", "mentions_back", "tests", "parent_needs"):
        assert "readOnly" not in properties[name], name
    assert properties["d_total"] == {
        "description": "Added by needs_fields config",
        "field_type": "extra",
        "readOnly": True,
        "type": "number",
    }


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "needs", "srcdir": "doc_test/doc_derive_config"}],
    indirect=True,
)
def test_a_derived_field_is_closed(test_app):
    """A derived field is not a directive option, cannot be extended, takes no default.

    So is a field whose rule cannot be read, which keeps its marker.
    """
    app = test_app
    app.build()
    schema = SphinxNeedsData(app.env).get_schema()
    for name in ("d_total", "bad_kind", "bad_cycle_a", "bad_default"):
        field = schema.get_extra_field(name)
        assert field is not None, name
        assert field.derive is not None, name
        assert not field.directive_option, name
        assert not field.allow_extend, name
        assert not field.allow_defaults, name
        assert field.default is None, name
    for name in ("mentions", "bad_link_join"):
        link = schema.get_link_field(name)
        assert link is not None, name
        assert link.derive is not None, name
        assert not link.directive_option and not link.allow_extend, name
    assert isinstance(schema.get_extra_field("d_total").derive, DeriveRule)
    assert isinstance(schema.get_extra_field("bad_default").derive, DeriveRule)
    for name in ("bad_kind", "bad_cycle_a", "bad_over", "bad_field_and_default"):
        assert isinstance(schema.get_extra_field(name).derive, DeriveInvalid), name
    status = schema.get_core_field("status")
    assert status is not None and status.derive is None
    parent_needs = schema.get_link_field("parent_needs")
    assert parent_needs is not None and parent_needs.derive is None
    assert parent_needs.directive_option and parent_needs.allow_extend
    assert schema.get_extra_field("hours").derive is None


CONF_PY_DICT_FORM = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_fields = {
    "hours": {"schema": {"type": "number"}},
    "total": {
        "schema": {"type": "number"},
        "nullable": False,
        "derive": {"kind": "sum", "field": "hours", "over": "links"},
    },
    "broken": {"derive": {"kind": "sum", "field": "hours"}},
}
needs_links = {
    "mentions": {"derive": {"kind": "content_links"}},
}
"""

CONF_PY_INDEX = """\
conf.py
=======

.. req:: Hours
   :id: REQ_001
   :hours: 3

.. spec:: Sums its links
   :id: SPEC_001
   :links: REQ_001
   :total: 4
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), CONF_PY_DICT_FORM),
                (Path("index.rst"), CONF_PY_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_derive_in_conf_py(test_app):
    """``derive`` is read from ``conf.py``'s ``needs_fields`` / ``needs_links`` too."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        _invalid("broken", "kind 'sum' requires the role 'over'"),
        "<srcdir>/index.rst:8: WARNING: Field 'total' is derived (kind 'sum') and "
        "cannot be set in a need; the value '4' is ignored [needs.derive_authored]",
    ]
    built = _built(app)
    assert built["needs"]["SPEC_001"]["total"] == 3.0
    properties = built["needs_schema"]["properties"]
    assert properties["total"]["readOnly"] is True
    assert properties["broken"]["readOnly"] is True
    assert properties["mentions"]["readOnly"] is True
    assert "readOnly" not in properties["hours"]


CONF_PY_EXTRA_OPTIONS = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_extra_options = [
    "hours",
    {"name": "copied", "derive": {"kind": "copy", "field": "title"}},
    {"name": "broken", "schema": {"type": "number"}, "derive": {"kind": "sum", "field": "hours"}},
]
"""

EXTRA_OPTIONS_INDEX = """\
needs_extra_options
===================

.. req:: Hours
   :id: REQ_001
   :hours: 3
   :copied: authored
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), CONF_PY_EXTRA_OPTIONS),
                (Path("index.rst"), EXTRA_OPTIONS_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_derive_in_needs_extra_options(test_app):
    """``derive`` is read from a ``needs_extra_options`` entry too, as from
    ``needs_extra_links``, rather than dropped, which left the field open."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        'WARNING: Config option "needs_extra_options" is deprecated. Please use '
        '"needs_fields" instead. [needs.deprecated]',
        _invalid("broken", "kind 'sum' requires the role 'over'"),
        "<srcdir>/index.rst:4: WARNING: Field 'copied' is derived (kind 'copy') and "
        "cannot be set in a need; the value 'authored' is ignored "
        "[needs.derive_authored]",
    ]
    properties = _built(app)["needs_schema"]["properties"]
    assert properties["copied"]["readOnly"] is True
    assert properties["broken"]["readOnly"] is True
    assert "readOnly" not in properties["hours"]


PARENT_NEEDS_INDEX = """\
parent_needs
============

.. req:: Parent
   :id: REQ_001

   .. req:: Child
      :id: REQ_002
"""


@pytest.mark.parametrize(
    "test_app,expected",
    [
        pytest.param(
            {
                "buildername": "needs",
                "files": [
                    (
                        Path("conf.py"),
                        'extensions = ["sphinx_needs"]\nneeds_build_json = True\n'
                        "needs_fields = {'parent_needs': "
                        "{'derive': {'kind': 'copy', 'field': 'title'}}}\n",
                    ),
                    (Path("index.rst"), PARENT_NEEDS_INDEX),
                ],
            },
            "WARNING: Invalid derive of field 'parent_needs': a core field cannot "
            "carry a derive rule in this release; the rule is ignored "
            "[needs.derive_invalid]",
            id="derive",
        ),
        pytest.param(
            {
                "buildername": "needs",
                "files": [
                    (
                        Path("conf.py"),
                        'extensions = ["sphinx_needs"]\nneeds_build_json = True\n'
                        "needs_fields = {'parent_needs': {'description': 'mine'}}\n",
                    ),
                    (Path("index.rst"), PARENT_NEEDS_INDEX),
                ],
            },
            "WARNING: needs_fields entry 'parent_needs' names the core link type "
            "'parent_needs', which is not a field; the entry is ignored [needs.config]",
            id="no-derive",
        ),
    ],
    indirect=["test_app"],
)
def test_needs_fields_parent_needs(test_app, expected):
    """A ``needs_fields`` entry named ``parent_needs``, the core link type, is reported
    and ignored, where it stopped the build ("Field 'parent_needs' already exists");
    with a ``derive``, as a rule on a core field. The link type works as before."""
    app = test_app
    app.build()
    assert build_warnings(app) == [expected]
    assert _built(app)["needs"]["REQ_002"]["parent_needs"] == ["REQ_001"]


LINK_NAMED_FIELDS_CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_links = {"tests": {}}
needs_extra_links = [{"option": "blocks", "incoming": "blocked by"}]
needs_fields = {
    "tests": {"schema": {"type": "string"}},
    "links": {"derive": {"kind": "copy", "field": "title"}},
    "blocks": {"description": "mine"},
    "owner": {"schema": {"type": "string"}},
}
"""

LINK_NAMED_FIELDS_INDEX = """\
Link-named fields
=================

.. req:: Tested
   :id: REQ_001

.. spec:: Tests it
   :id: SPEC_001
   :tests: REQ_001
   :links: REQ_001
   :blocks: REQ_001
   :owner: alice
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), LINK_NAMED_FIELDS_CONF),
                (Path("index.rst"), LINK_NAMED_FIELDS_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_needs_fields_named_after_a_link_type(test_app):
    """A ``needs_fields`` entry named after a declared link type (``needs_links``,
    ``needs_extra_links``, or the default ``links``) is reported and ignored, where it
    stopped the build ("Field 'tests' already exists"); a ``derive`` on it is ignored
    with it. The link types work as before."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        'WARNING: Config option "needs_extra_links" is deprecated. Please use '
        '"needs_links" instead. [needs.deprecated]',
        "WARNING: needs_fields entry 'tests' names the link type 'tests', which is "
        "not a field; the entry is ignored [needs.config]",
        "WARNING: needs_fields entry 'links' names the link type 'links', which is "
        "not a field; the entry is ignored [needs.config]",
        "WARNING: needs_fields entry 'blocks' names the link type 'blocks', which is "
        "not a field; the entry is ignored [needs.config]",
    ]
    spec = _built(app)["needs"]["SPEC_001"]
    assert (spec["tests"], spec["links"], spec["blocks"]) == (
        ["REQ_001"],
        ["REQ_001"],
        ["REQ_001"],
    )
    assert spec["owner"] == "alice"


COPY_DERIVED_CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_links = {
    "mentions": {"copy": True, "derive": {"kind": "content_links"}},
    "broken": {"copy": True, "derive": {"kind": "links"}},
}
"""

COPY_DERIVED_INDEX = """\
Copy of a derived link type
===========================

.. req:: Mentioned
   :id: REQ_001

.. spec:: Mentions it
   :id: SPEC_001

   Mentions :need:`REQ_001`.
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), COPY_DERIVED_CONF),
                (Path("index.rst"), COPY_DERIVED_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_copy_on_a_derived_link_type(test_app):
    """``copy = true`` on a derived link type is one ``needs.derive_invalid`` at its
    rule, and nothing is copied into ``links``; the rule applies. A rule that cannot
    be read is reported for that alone."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        _invalid_link("broken", "kind 'links' requires the role 'where'"),
        "WARNING: Invalid derive of link type 'mentions': kind 'content_links': "
        "'copy' is not available on a derived link type in this release, and is "
        "ignored; the rule applies [needs.derive_invalid]",
    ]
    spec = _built(app)["needs"]["SPEC_001"]
    assert (spec["mentions"], spec["links"]) == (["REQ_001"], [])


CONF_PY_COPY_INTO_LINKS = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_links = {
    "links": {"derive": {"kind": "links", "where": "type == 'test'"}},
    "tests": {"copy": True},
    "satisfies": {"copy": True},
    "mentions": {},
}
"""

COPY_INTO_LINKS_INDEX = """\
Copy into links
===============

.. req:: A requirement
   :id: REQ_001

.. spec:: Satisfies and tests it
   :id: SPEC_001
   :satisfies: REQ_001
   :tests: REQ_001
   :mentions: REQ_001
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), CONF_PY_COPY_INTO_LINKS),
                (Path("index.rst"), COPY_INTO_LINKS_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_a_copy_into_derived_links_is_ignored(test_app):
    """A link type with ``copy = true`` copies nothing into a derived ``links``.

    ``links`` holds what its rule computes, so the copy, a second writer, is not
    made, and it is one ``needs.derive_invalid`` at the ``links`` rule, naming every
    copying link type; the rule applies, and the copying link types keep their links.
    """
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "WARNING: Invalid derive of link type 'links': kind 'links': 'links' is "
        "derived; the copy of the link types 'satisfies' and 'tests' into it is "
        "ignored; the rule applies [needs.derive_invalid]",
    ]
    spec = _built(app)["needs"]["SPEC_001"]
    assert spec["links"] == []
    assert spec["satisfies"] == ["REQ_001"]
    assert spec["tests"] == ["REQ_001"]
    assert spec["mentions"] == ["REQ_001"]


CONF_PY_PLACEHOLDER = """\
extensions = ["sphinx_needs"]
needs_build_json = True
_ASIL = {"type": "string", "enum": ["QM", "A", "B", "C", "D"]}
needs_fields = {
    "hours": {"schema": {"type": "number"}},
    "asil_own": {"schema": _ASIL},
    "asil": {
        "schema": _ASIL,
        "nullable": False,
        "derive": {
            "kind": "max",
            "field": "asil_own",
            "over": "satisfies",
            "transitive": True,
            "include_self": True,
        },
    },
    "peak": {
        "schema": {"type": "number", "minimum": 1},
        "nullable": False,
        "derive": {"kind": "max", "field": "hours", "over": "links"},
    },
    "digest": {
        "schema": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "nullable": False,
        "derive": {"kind": "hash", "fields": ["title"]},
    },
    "broken": {
        "schema": {"type": "string", "enum": ["X"]},
        "nullable": False,
        "derive": {"kind": "sum", "field": "hours"},
    },
}
needs_links = {"satisfies": {}}
"""

PLACEHOLDER_INDEX = """\
Placeholders
============

.. req:: Assigned a level
   :id: REQ_001
   :asil_own: B

.. spec:: Assigned nothing
   :id: SPEC_001

.. req:: Assigned a level the schema refuses
   :id: REQ_002
   :asil_own: Z
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), CONF_PY_PLACEHOLDER),
                (Path("index.rst"), PLACEHOLDER_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_a_placeholder_is_not_validated(test_app):
    """The empty value a derived field holds is not checked against its schema.

    It is the field's "no value", as ``None`` is for a nullable field: a field that
    is not nullable holds ``""`` or ``0.0`` where its ``enum``, ``minimum`` or
    ``pattern`` refuses it, and that is not a schema violation, on a valid rule or
    an invalid one. The schema of a field that is not derived is checked as before.
    """
    app = test_app
    app.build()
    assert build_warnings(app) == [
        _invalid("broken", "kind 'sum' requires the role 'over'"),
        "ERROR: Need 'REQ_002' has schema violations:\n"
        "  Severity:       violation\n"
        "  Field:          asil_own\n"
        "  Need path:      REQ_002\n"
        "  Schema path:    fields > schema > properties > asil_own > enum\n"
        '  Schema message: "Z" is not one of "QM", "A" or 3 other candidates '
        "[sn_schema_violation.field_fail]",
    ]
    spec = _built(app)["needs"]["SPEC_001"]
    assert spec["asil"] == ""
    assert spec["peak"] == 0.0


@pytest.mark.parametrize(
    "raw,on_link,expected",
    [
        pytest.param(
            {"kind": "copy", "field": "title"},
            False,
            DeriveRule(kind="copy", field="title"),
            id="copy-own",
        ),
        pytest.param(
            {"kind": "copy", "field": "owner", "from": "REQ_1"},
            False,
            DeriveRule(kind="copy", field="owner", from_need="REQ_1"),
            id="copy-from",
        ),
        pytest.param(
            {"kind": "copy", "field": "owner", "over": "parent", "select": "list"},
            False,
            DeriveRule(kind="copy", field="owner", over="parent", select="list"),
            id="copy-over-select",
        ),
        pytest.param(
            {"kind": "sum", "field": "hours", "over": "links", "where": "a == 1"},
            False,
            DeriveRule(kind="sum", field="hours", over="links", where="a == 1"),
            id="sum-where",
        ),
        pytest.param(
            {"kind": "count", "over": "tests_back"},
            False,
            DeriveRule(kind="count", over="tests_back"),
            id="count",
        ),
        pytest.param(
            {
                "kind": "max",
                "field": "asil",
                "over": "satisfies",
                "transitive": True,
                "include_self": True,
            },
            False,
            DeriveRule(
                kind="max",
                field="asil",
                over="satisfies",
                transitive=True,
                include_self=True,
            ),
            id="max-transitive",
        ),
        pytest.param(
            {"kind": "all", "test": "status == 'passed'", "over": "tests_back"},
            False,
            DeriveRule(kind="all", test="status == 'passed'", over="tests_back"),
            id="all-test",
        ),
        pytest.param(
            {"kind": "collect", "field": "owner", "over": "links", "after": "derived"},
            False,
            DeriveRule(kind="collect", field="owner", over="links", after_derived=True),
            id="collect-after",
        ),
        pytest.param(
            {"kind": "hash", "fields": ["title", "links"]},
            False,
            DeriveRule(kind="hash", fields=("title", "links")),
            id="hash",
        ),
        pytest.param(
            {"kind": "links", "where": "type == 'req'", "include_parts": True},
            True,
            DeriveRule(kind="links", where="type == 'req'", include_parts=True),
            id="links",
        ),
        pytest.param(
            {"kind": "content_links"},
            True,
            DeriveRule(kind="content_links"),
            id="content-links",
        ),
    ],
)
def test_parse_derive_reads_a_rule(raw, on_link, expected):
    """A rule whose roles fit its kind is read into its typed roles."""
    assert parse_derive(raw, on_link=on_link) == expected


@pytest.mark.parametrize(
    "raw,on_link,kind,reason",
    [
        pytest.param([], False, None, "it is not a table naming a 'kind'", id="list"),
        pytest.param({}, False, None, "it has no 'kind'", id="no-kind"),
        pytest.param(
            {"kind": 1},
            False,
            None,
            "the kind 1 is unknown; the kinds are copy, sum, count, min, max, any, "
            "all, collect, hash, links, content_links",
            id="kind-not-string",
        ),
        pytest.param(
            {"kind": "expr", "expr": "1"},
            False,
            "expr",
            "the kind 'expr' is unknown; the kinds are copy, sum, count, min, max, "
            "any, all, collect, hash, links, content_links",
            id="expr-not-yet",
        ),
        pytest.param(
            {"kind": "copy", "field": "x", "join": {}},
            False,
            "copy",
            "kind 'copy': the 'join' role is reserved and not available yet",
            id="join-on-copy",
        ),
        pytest.param(
            {"kind": "copy", "field": "x", "types": ["req"]},
            False,
            "copy",
            "kind 'copy': the 'types' role is reserved and not available yet",
            id="types-reserved",
        ),
        pytest.param(
            {"kind": "count", "over": "links", "zz": 1, "aa": 2},
            False,
            "count",
            "kind 'count': 'aa' is not a role",
            id="unknown-roles-by-name",
        ),
        pytest.param(
            {"kind": "content_links"},
            False,
            "content_links",
            "kind 'content_links' computes a link list, so it is declared on a link "
            "type (needs_links), not on a field",
            id="link-kind-on-field",
        ),
        pytest.param(
            {"kind": "copy", "field": "x"},
            True,
            "copy",
            "kind 'copy' computes a value, so it is declared on a field "
            "(needs_fields), not on a link type",
            id="value-kind-on-link",
        ),
        pytest.param(
            {"kind": "hash", "fields": ["a"], "where": "a"},
            False,
            "hash",
            "kind 'hash' does not take the role 'where'",
            id="role-not-taken",
        ),
        pytest.param(
            {"kind": "copy", "field": "x", "include_parts": True, "over": "links"},
            False,
            "copy",
            "kind 'copy' does not take the role 'include_parts'",
            id="include-parts-only-on-links",
        ),
        pytest.param(
            {"kind": "collect", "field": "x"},
            False,
            "collect",
            "kind 'collect' requires the role 'over'",
            id="missing-role",
        ),
        pytest.param(
            {"kind": "copy", "field": ""},
            False,
            "copy",
            "kind 'copy': the role 'field' must not be empty",
            id="empty-field",
        ),
        pytest.param(
            {"kind": "hash", "fields": "title"},
            False,
            "hash",
            "kind 'hash': the role 'fields' must be a non-empty list of field names",
            id="fields-not-list",
        ),
        pytest.param(
            {"kind": "hash", "fields": []},
            False,
            "hash",
            "kind 'hash': the role 'fields' must be a non-empty list of field names",
            id="fields-empty",
        ),
        pytest.param(
            {"kind": "copy", "field": "x", "over": "links", "select": "last"},
            False,
            "copy",
            'kind \'copy\': the role \'select\' must be "first", "unique" or "list"',
            id="select-value",
        ),
        pytest.param(
            {"kind": "links", "where": "a", "include_self": "no"},
            True,
            "links",
            "kind 'links': the role 'include_self' must be a boolean",
            id="boolean-role",
        ),
        pytest.param(
            {"kind": "all", "over": "links"},
            False,
            "all",
            "kind 'all' takes exactly one of the roles 'field' and 'test'",
            id="all-neither",
        ),
        pytest.param(
            {"kind": "links", "where": ""},
            True,
            "links",
            "kind 'links' has an empty 'where', which would link every need",
            id="links-empty-where",
        ),
    ],
)
def test_parse_derive_refuses_a_rule(raw, on_link, kind, reason):
    """A rule whose roles do not fit its kind is a marker, with why, naming the role."""
    assert parse_derive(raw, on_link=on_link) == DeriveInvalid(kind, reason)


def test_replace_field_keeps_its_place():
    """A field is replaced by a new one of the same name, as a rule that cannot be
    read is marked: the frozen field is rebuilt whole, not changed in place, and keeps
    its place, so the order of the fields does not move."""
    schema = FieldsSchema()
    for name in ("a", "b", "c"):
        schema.add_extra_field(FieldSchema(name=name, schema={"type": "string"}))
    link = LinkSchema(
        name="l",
        schema={"type": "array", "items": {"type": "string"}},
        display=LinkDisplayConfig(incoming="l in", outgoing="l"),
    )
    schema.add_link_field(link)
    marker = DeriveInvalid("copy", "why")
    old = schema.get_extra_field("b")
    schema.replace_field(dataclasses.replace(old, derive=marker))
    assert list(schema.iter_extra_field_names()) == ["a", "b", "c"]
    assert schema.get_extra_field("b").derive == marker
    assert old.derive is None
    schema.replace_field(dataclasses.replace(link, derive=marker))
    assert schema.get_link_field("l").derive == marker
    with pytest.raises(ValueError, match="does not exist"):
        schema.replace_field(FieldSchema(name="z", schema={"type": "string"}))
    with pytest.raises(ValueError, match="does not exist"):
        schema.replace_field(dataclasses.replace(link, name="a"))
