"""Declared derived fields compute their values: one test per kind, then the findings.

A ``derive`` rule on a ``needs_fields`` / ``needs_links`` entry computes the field for
every need from the project's sources, in the step its kind belongs to: ``links`` and
``content_links`` with the link fields, every other kind with the other fields, and
``hash`` (and a rule with ``after = "derived"``) after every other field. The values
pinned here are the ones the build computes, each checked against the contract of the
kinds shared with ubCode (candidates, order, duplicates, unset values, the empty value
over no candidate).
"""

import hashlib
import json
import os
import time
from pathlib import Path

import pytest
from sphinx.util.parallel import parallel_available

from sphinx_needs_testkit import build_warnings

KINDS = {"buildername": "needs", "srcdir": "doc_test/doc_derive_kinds"}


def _needs(app) -> dict[str, dict]:
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    return data["versions"][data["current_version"]]["needs"]


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@pytest.mark.parametrize("test_app", [KINDS], indirect=True)
def test_the_kinds_project_warns_only_what_it_should(test_app):
    """One ``needs.derive_unique`` (two parents set ``owner``), and the two dead links."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "<srcdir>/index.rst:34: WARNING: derive rule 'copy' for option 'c_unique' "
        "found 2 needs setting 'owner' (REQ_A, REQ_B); the lowest id, 'REQ_A', is "
        "copied [needs.derive_unique]",
        "<srcdir>/index.rst:34: WARNING: Need 'SPEC_1' has unknown outgoing link "
        "'NOPE_2' in field 'l_mentions' [needs.link_outgoing]",
        "<srcdir>/index.rst:34: WARNING: Need 'SPEC_1' has unknown outgoing link "
        "'NOPE_1' in field 'links' [needs.link_outgoing]",
    ]


@pytest.mark.parametrize("test_app", [KINDS], indirect=True)
def test_copy(test_app):
    """``copy``: the own field, the need ``from`` names, and over a link type.

    ``SPEC_1``'s ``parent`` names ``REQ_B``, then ``REQ_A``: ``select = "first"`` takes
    the lowest id among the targets that set ``owner`` (``REQ_A``), as does ``unique``
    (which reports the two); ``list`` takes every value in the order written, a list
    field's items flattened and nothing removed.
    """
    app = test_app
    app.build()
    needs = _needs(app)
    spec = needs["SPEC_1"]
    assert spec["c_title"] == "Spec 1"
    assert needs["REQ_C"]["c_title"] == "Größe"
    assert {needs[i]["c_from"] for i in needs} == {"alice"}
    assert spec["c_first"] == "alice"
    assert spec["c_unique"] == "alice"
    assert spec["c_list"] == ["bob", "alice"]
    assert spec["c_labels"] == ["y", "z", "x", "y"]
    # no target: the empty value (nullable string: unset; array: [])
    assert needs["REQ_A"]["c_first"] is None
    assert needs["REQ_A"]["c_list"] == []


@pytest.mark.parametrize("test_app", [KINDS], indirect=True)
def test_sum_and_count(test_app):
    """``sum`` reads each link in the order written: ``SPEC_1``'s ``links`` are
    ``REQ_B, REQ_A, REQ_A, REQ_A.p, NOPE_1``, so ``REQ_A`` is read three times (twice by
    id, once through its part) and the dead ``NOPE_1`` is skipped: ``5 + 2 + 2 + 2``.

    A sum of an ``integer`` field is an integer. ``count`` over ``tests_back`` counts
    the tests that pass ``where``, or with ``field`` those that set it.
    """
    app = test_app
    app.build()
    needs = _needs(app)
    spec = needs["SPEC_1"]
    assert spec["s_hours"] == 11.0
    assert isinstance(spec["s_points"], int)
    assert spec["s_points"] == 13
    assert spec["s_open"] == 6.0
    assert spec["n_passed"] == 1
    assert spec["n_hours"] == 1
    # no candidate: 0.0, 0, 0
    assert (needs["REQ_A"]["s_hours"], needs["REQ_A"]["s_points"]) == (0.0, 0)
    assert needs["REQ_A"]["n_passed"] == 0


@pytest.mark.parametrize("test_app", [KINDS], indirect=True)
def test_any_and_all(test_app):
    """``any`` / ``all`` over the tests of ``SPEC_1``; over none, ``all`` is true and
    ``any`` false."""
    app = test_app
    app.build()
    needs = _needs(app)
    spec = needs["SPEC_1"]
    assert (spec["a_all"], spec["a_any"], spec["a_field"]) == (False, True, True)
    other = needs["REQ_A"]
    assert (other["a_all"], other["a_any"], other["a_field"]) == (True, False, False)


@pytest.mark.parametrize("test_app", [KINDS], indirect=True)
def test_min_max_and_collect(test_app):
    """``min`` / ``max`` of a number, and of an enum in its declared order;
    ``collect`` is a set, in the order of the candidates, a list's items each."""
    app = test_app
    app.build()
    needs = _needs(app)
    spec = needs["SPEC_1"]
    assert (spec["m_min"], spec["m_max"]) == (2.0, 5.0)
    # REQ_B is A, REQ_A is B: B is the greater, in the enum's order QM, A, B, C, D
    assert spec["m_asil"] == "B"
    assert spec["k_owners"] == ["bob", "alice"]
    assert spec["k_labels"] == ["y", "z", "x"]
    # no candidate: unset, and []
    assert (needs["REQ_A"]["m_min"], needs["REQ_A"]["k_owners"]) == (None, [])


@pytest.mark.parametrize("test_app", [KINDS], indirect=True)
def test_max_transitive(test_app):
    """``max`` closed over ``satisfies``: ``TRANS_2`` and ``TRANS_3`` satisfy each other.

    ``TRANS_1`` (QM) satisfies ``TRANS_2`` (A), which satisfies ``TRANS_3`` (C) and back;
    ``TRANS_4`` (D) satisfies ``TRANS_1``. Each member of the cycle reaches the other
    and itself, so both are C even without ``include_self``; ``TRANS_4`` is D with
    ``include_self`` and C without. A need that satisfies nothing is its own level with
    ``include_self``, and unset without.
    """
    app = test_app
    app.build()
    needs = _needs(app)
    with_self = {
        i: needs[i]["t_asil"] for i in ("TRANS_1", "TRANS_2", "TRANS_3", "TRANS_4")
    }
    without = {
        i: needs[i]["t_asil_out"] for i in ("TRANS_1", "TRANS_2", "TRANS_3", "TRANS_4")
    }
    assert with_self == {"TRANS_1": "C", "TRANS_2": "C", "TRANS_3": "C", "TRANS_4": "D"}
    assert without == {"TRANS_1": "C", "TRANS_2": "C", "TRANS_3": "C", "TRANS_4": "C"}
    assert (needs["REQ_A"]["t_asil"], needs["REQ_A"]["t_asil_out"]) == ("B", None)


#: the JSON text each pinned hash is the SHA-256 of, written out by hand
HASHED = {
    ("SPEC_1", "h_digest"): '["Spec 1",null,11.0,["NOPE_1","REQ_A","REQ_A.p","REQ_B"]]',
    ("REQ_C", "h_digest"): '["Größe","open",0.0,[]]',
    ("REQ_A", "h_numbers"): "[3,0.5]",
    ("REQ_B", "h_numbers"): "[4,1e+16]",
    ("REQ_A", "h_list"): '[["x","y"],"alice"]',
    ("REQ_C", "h_list"): '[null,"carol"]',
}


@pytest.mark.parametrize("test_app", [KINDS], indirect=True)
def test_hash(test_app):
    """``hash``: the SHA-256 of one compact JSON array of the listed fields.

    Each value as ``needs.json`` holds it (``SPEC_1``'s ``links`` sorted and without
    duplicates, an unset field ``null``, the derived ``s_hours`` computed before),
    with no whitespace, ``Größe`` not escaped, a float as Python writes it (``0.5``,
    ``1e+16``). A copy with ``after = "derived"`` reads the hash after it is computed.
    """
    app = test_app
    app.build()
    needs = _needs(app)
    for (need_id, field), text in HASHED.items():
        assert needs[need_id][field] == _sha256(text), (need_id, field, text)
    # the hex, pinned for ubCode to compute byte for byte
    assert needs["SPEC_1"]["h_digest"] == (
        "ec9eb469e9b4f36b7912cc510376dd5a13fd3269b1976eb0b583bb3764fdc180"
    )
    assert needs["REQ_B"]["h_numbers"] == (
        "fe64a22116ee2e8b583fd00ad07e35e5977f3a4e21402f09417fa312a3b3d498"
    )
    assert needs["REQ_C"]["h_list"] == (
        "20a10551bd6fe84d2d780847e01f7f48df36ab6bb60d60a1c02b2762e2cfd121"
    )
    for need_id, need in needs.items():
        assert need["l_digest"] == need["h_digest"], need_id


@pytest.mark.parametrize("test_app", [KINDS], indirect=True)
def test_links_and_content_links(test_app):
    """``links``: every need passing ``where``, the need itself (and its parts) left out
    unless ``include_self``, parts tested only with ``include_parts``.
    ``content_links``: the ``:need:`` references of the content, a part reference kept as
    a part link, a dead one kept, the need itself kept; under ``where`` only the
    referenced needs that pass (a part through its need). ``from`` reads another need's
    content. (Link lists are written sorted.)
    """
    app = test_app
    app.build()
    needs = _needs(app)
    assert needs["SPEC_1"]["l_open"] == ["REQ_A", "REQ_C"]
    assert needs["REQ_A"]["l_open"] == ["REQ_C"]
    assert needs["SPEC_1"]["l_specs"] == ["SPEC_1"]
    assert needs["REQ_A"]["l_specs"] == ["SPEC_1"]
    assert needs["SPEC_1"]["l_parts"] == ["REQ_A.p"]
    assert needs["REQ_A"]["l_parts"] == []
    assert needs["SPEC_1"]["l_mentions"] == ["NOPE_2", "REQ_A.p", "REQ_B", "SPEC_1"]
    assert needs["SPEC_1"]["l_mentioned_reqs"] == ["REQ_A.p", "REQ_B"]
    assert needs["REQ_A"]["l_mentions"] == ["REQ_B"]
    assert needs["REQ_B"]["l_mentions"] == []
    assert {i: needs[i]["l_from"] for i in ("REQ_A", "SPEC_1")} == {
        "REQ_A": ["REQ_B"],
        "SPEC_1": ["REQ_B"],
    }
    # the derived links are back links like any other
    assert "SPEC_1" in needs["REQ_C"]["l_open_back"]
    assert "REQ_C" not in needs["REQ_C"]["l_open_back"]


NEGATIVE_CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_id_regex = "^.+$"
needs_fields = {
    "hours": {"schema": {"type": "number"}},
    "owner": {"schema": {"type": "string"}},
    "summary": {"schema": {"type": "string"}},
    "reads_total": {"schema": {"type": "number"}},
    "cyc": {
        "schema": {"type": "string"},
        "derive": {"kind": "copy", "field": "cyc", "over": "links"},
    },
    "digest": {"schema": {"type": "string"}, "derive": {"kind": "hash", "fields": ["title"]}},
    "from_missing": {
        "schema": {"type": "string"},
        "derive": {"kind": "copy", "field": "owner", "from": "NOPE_9"},
    },
    "raising": {
        "schema": {"type": "number"},
        "derive": {"kind": "sum", "field": "hours", "over": "links", "where": "hours > 1"},
    },
    "total": {
        "schema": {"type": "number"},
        "derive": {"kind": "sum", "field": "hours", "over": "links"},
    },
}
needs_links = {
    "big": {"derive": {"kind": "links", "where": "total is not None and total > 1"}},
}
"""

NEGATIVE_INDEX = """\
Negative
========

.. req:: A
   :id: A
   :links: B
   :hours: 2
   :summary: [[copy("digest")]]
   :reads_total: [[copy("total")]]

.. req:: B
   :id: B
   :links: A
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), NEGATIVE_CONF),
                (Path("index.rst"), NEGATIVE_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_what_a_rule_cannot_compute(test_app):
    """The findings of a rule at run time, each leaving its field empty.

    - ``cyc`` copies ``cyc`` over ``links``, and ``A`` and ``B`` link each other: a cycle
      of the two needs (``needs.derive_cycle``).
    - ``big`` (a link type, computed with the link fields) filters on ``total``, which
      is computed after them: not run (``needs.derive_scope``).
    - ``summary`` copies the ``hash`` ``digest``, computed in the late step: not run
      (``needs.derive_scope``).
    - ``from`` names no need, and ``where`` cannot be evaluated on ``B`` (no ``hours``):
      ``needs.dynamic_function``.
    A copy of a derived value of the same step waits for it (``reads_total``).
    """
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "<srcdir>/index.rst:4: WARNING: derive rule 'links' for option 'big' reads "
        "'total' on 2 needs (A, B), which are final only after the link fields are "
        "computed: the rule is not run and the field is left empty "
        "[needs.derive_scope]",
        "<srcdir>/index.rst:11: WARNING: derive rule 'links' for option 'big' reads "
        "'total' on 2 needs (A, B), which are final only after the link fields are "
        "computed: the rule is not run and the field is left empty "
        "[needs.derive_scope]",
        "<srcdir>/index.rst:4: WARNING: derive rule 'copy' for option 'cyc' is on a "
        "cycle: 'cyc' on 2 needs (A, B); the field is left empty [needs.derive_cycle]",
        "<srcdir>/index.rst:11: WARNING: derive rule 'copy' for option 'cyc' is on a "
        "cycle: 'cyc' on 2 needs (A, B); the field is left empty [needs.derive_cycle]",
        "<srcdir>/index.rst:4: WARNING: Error while resolving dynamic values for field "
        "'from_missing', of need 'A': 'from' names no need: 'NOPE_9' "
        "[needs.dynamic_function]",
        "<srcdir>/index.rst:4: WARNING: Error while resolving dynamic values for field "
        "'raising', of need 'A': on need 'B': Filter 'hours > 1' not valid. Error: '>' "
        "not supported between instances of 'NoneType' and 'int'. "
        "[needs.dynamic_function]",
        "<srcdir>/index.rst:4: WARNING: dynamic function 'copy' for option 'summary' "
        "reads 'digest' on need 'A', which is computed in the late step, after every "
        "other field (a derive rule of the kind 'hash' or with after = \"derived\"): "
        "the call is not run and the field is left empty [needs.derive_scope]",
        "<srcdir>/index.rst:11: WARNING: Error while resolving dynamic values for field "
        "'from_missing', of need 'B': 'from' names no need: 'NOPE_9' "
        "[needs.dynamic_function]",
    ]
    needs = _needs(app)
    a, b = needs["A"], needs["B"]
    assert (a["cyc"], b["cyc"], a["big"], b["big"]) == (None, None, [], [])
    assert (a["from_missing"], a["raising"], b["raising"]) == (None, None, 2.0)
    assert (a["total"], b["total"], a["reads_total"]) == (0.0, 2.0, 0.0)
    assert a["summary"] is None
    assert a["digest"] == _sha256('["A"]')


# -- a chain of rules across documents, in two layouts, serial and -j 2 ---------------

CHAIN_CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_id_regex = "^.+$"
needs_fields = {
    "hours": {"schema": {"type": "number"}},
    "sub": {
        "schema": {"type": "number"},
        "derive": {"kind": "sum", "field": "hours", "over": "links"},
    },
    "subsub": {
        "schema": {"type": "number"},
        "derive": {"kind": "sum", "field": "sub", "over": "links"},
    },
    "top": {
        "schema": {"type": "number"},
        "derive": {"kind": "copy", "field": "subsub", "over": "parent", "select": "first"},
    },
}
needs_links = {"parent": {}}
"""

PADDING = [(Path(f"pad_{n}.rst"), f":orphan:\n\nPad {n}\n=====\n") for n in range(4)]


def _chain(order: list[str]) -> list[tuple[Path, str]]:
    pages = {
        "x": ".. req:: X\n   :id: CH_X\n   :links: CH_Y\n",
        "y": ".. req:: Y\n   :id: CH_Y\n   :links: CH_Z\n",
        "z": ".. req:: Z\n   :id: CH_Z\n   :hours: 0.1\n",
        "w": ".. req:: W\n   :id: CH_W\n   :parent: CH_X\n",
    }
    toctree = "Index\n=====\n\n.. toctree::\n\n" + "".join(f"   {p}\n" for p in order)
    return [
        (Path("conf.py"), CHAIN_CONF),
        (Path("index.rst"), toctree),
        *((Path(f"{p}.rst"), f"{p}\n=\n\n{pages[p]}") for p in order),
    ]


def _layouts(**layouts: list[tuple[Path, str]]) -> list:
    params = []
    for name, files in layouts.items():
        params.append(
            pytest.param({"buildername": "needs", "files": files}, id=f"{name}-serial")
        )
        params.append(
            pytest.param(
                {"buildername": "needs", "files": [*files, *PADDING], "parallel": 2},
                id=f"{name}-j2",
                marks=pytest.mark.skipif(
                    not parallel_available, reason="Parallel execution not supported"
                ),
            )
        )
    return params


@pytest.mark.parametrize(
    "test_app",
    _layouts(
        readers_first=_chain(["w", "x", "y", "z"]),
        sources_first=_chain(["z", "y", "x", "w"]),
    ),
    indirect=True,
)
def test_a_chain_of_rules_in_every_layout(test_app):
    """``CH_W`` copies ``CH_X``'s ``subsub``, the sum of ``CH_Y``'s ``sub``, the sum of
    ``CH_Z``'s ``hours``: computed in dependency order whatever the document order and
    ``-j``."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    needs = _needs(app)
    assert needs["CH_Y"]["sub"] == 0.1
    assert needs["CH_X"]["subsub"] == 0.1
    assert needs["CH_W"]["top"] == 0.1


# -- a configuration change reaches the needs of unchanged documents ------------------

RECONF_CONF = """\
extensions = ["sphinx_needs"]
needs_from_toml = "ubproject.toml"
needs_build_json = True
"""

RECONF_TOML = """\
[needs.fields.hours]
schema = { type = "number" }

[needs.fields.owner]
schema = { type = "string" }

[needs.fields.total]
schema = { type = "number" }
"""

RECONF_ADDED = """
[needs.fields.total.derive]
kind = "sum"
field = "hours"
over = "links"
"""

RECONF_INDEX = """\
Reconfigured
============

.. req:: Hours
   :id: REQ_001
   :hours: 3

.. req:: Total
   :id: REQ_002
   :links: REQ_001
   :total: 5
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), RECONF_CONF),
                (Path("ubproject.toml"), RECONF_TOML),
                (Path("index.rst"), RECONF_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_a_changed_field_configuration_rereads_every_document(test_app, make_app):
    """A ``derive`` rule, or a ``default``, added between two builds applies at once.

    The field configuration is read by every need as it is created, so a change to it
    re-reads every document: before, the second build kept the needs of the unchanged
    document as the first build created them (``total`` 5, no default ``owner``).
    """
    app = test_app
    app.build()
    assert build_warnings(app) == []
    assert _needs(app)["REQ_002"]["total"] == 5.0

    toml = Path(app.srcdir, "ubproject.toml")
    text = toml.read_text(encoding="utf-8").replace(
        '[needs.fields.owner]\nschema = { type = "string" }\n',
        '[needs.fields.owner]\nschema = { type = "string" }\ndefault = "alice"\n',
    )
    toml.write_text(text + RECONF_ADDED, encoding="utf-8")
    # newer than the first build, whatever the file system's clock resolution
    later = time.time_ns() + 60_000_000_000
    os.utime(toml, ns=(later, later))

    second = make_app(buildername="needs", srcdir=app.srcdir)
    second.build()
    # a second application in one process re-registers Sphinx's own nodes, with
    # warnings of its own; the needs' warnings are these
    assert [w for w in build_warnings(second) if "[needs." in w] == [
        "<srcdir>/index.rst:8: WARNING: Field 'total' is derived (kind 'sum') and "
        "cannot be set in a need; the value '5' is ignored [needs.derive_authored]",
    ]
    needs = _needs(second)
    assert needs["REQ_002"]["total"] == 3.0
    assert needs["REQ_001"]["owner"] == "alice"


GLOBAL_CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_fields = {"owner": {"schema": {"type": "string"}}}
"""

GLOBAL_INDEX = """\
Global options
==============

.. req:: Owned
   :id: REQ_001
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), GLOBAL_CONF),
                (Path("index.rst"), GLOBAL_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_a_changed_global_option_rereads_every_document(test_app, make_app):
    """A ``needs_global_options`` default added between two builds applies at once.

    It is read by every need as it is created, as the field configuration is: before,
    the second build kept the need of the unchanged document without the default.
    """
    app = test_app
    app.build()
    assert build_warnings(app) == []
    assert _needs(app)["REQ_001"]["owner"] is None

    conf = Path(app.srcdir, "conf.py")
    conf.write_text(
        GLOBAL_CONF + 'needs_global_options = {"owner": {"default": "bob"}}\n',
        encoding="utf-8",
    )
    later = time.time_ns() + 60_000_000_000
    os.utime(conf, ns=(later, later))

    second = make_app(buildername="needs", srcdir=app.srcdir)
    second.build()
    assert [w for w in build_warnings(second) if "[needs." in w] == [
        'WARNING: Config option "needs_global_options" is deprecated. Please use '
        "needs_fields and needs_links instead. [needs.deprecated]",
    ]
    assert _needs(second)["REQ_001"]["owner"] == "bob"


IMPORT_SOURCE = {
    "current_version": "1.0",
    "versions": {
        "1.0": {
            "needs": {
                "IMP_001": {
                    "id": "IMP_001",
                    "type": "req",
                    "title": "Imported",
                    "links": ["REQ_001"],
                    "total": 42.0,
                }
            }
        }
    },
}


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (
                    Path("conf.py"),
                    'extensions = ["sphinx_needs"]\nneeds_build_json = True\n'
                    "needs_fields = {\n"
                    '    "hours": {"schema": {"type": "number"}},\n'
                    '    "total": {"schema": {"type": "number"}, '
                    '"derive": {"kind": "sum", "field": "hours", "over": "links"}},\n'
                    "}\n",
                ),
                (Path("imported.json"), json.dumps(IMPORT_SOURCE)),
                (
                    Path("index.rst"),
                    "Import\n======\n\n.. req:: Hours\n   :id: REQ_001\n   :hours: 3\n\n"
                    ".. req:: Sums\n   :id: REQ_002\n   :links: REQ_001\n\n"
                    ".. needimport:: imported.json\n",
                ),
            ],
        }
    ],
    indirect=True,
)
def test_no_rule_runs_on_an_imported_need(test_app):
    """An imported need keeps the value it carries; a need of the project computes it."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    needs = _needs(app)
    assert needs["IMP_001"]["total"] == 42.0
    assert needs["REQ_002"]["total"] == 3.0


ADD_FIELD_CONF = """\
from sphinx_needs.api import add_field

extensions = ["sphinx_needs"]
needs_build_json = True
needs_fields = {"hours": {"schema": {"type": "number"}}}


def setup(app):
    add_field(
        "total",
        "The hours of the linked needs",
        schema={"type": "number"},
        derive={"kind": "sum", "field": "hours", "over": "links"},
    )
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), ADD_FIELD_CONF),
                (
                    Path("index.rst"),
                    "API\n===\n\n.. req:: Hours\n   :id: REQ_001\n   :hours: 3\n\n"
                    ".. req:: Sums\n   :id: REQ_002\n   :links: REQ_001\n",
                ),
            ],
        }
    ],
    indirect=True,
)
def test_add_field_declares_a_derived_field(test_app):
    """An extension declares a derived field through the ``add_field`` API."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    assert _needs(app)["REQ_002"]["total"] == 3.0
