"""A dense derived link type is warned of once, by the links it stores: ``needs.derive_dense``.

For each link type, the links in the lists a ``links`` or ``content_links`` rule
computed (``derive`` or ``derive_by_type``), or, on a link type without a rule, the
lists ``links_from_filter``, ``links_from_content`` and ``links_from_match`` computed,
are summed over every need, and compared with ``needs_derive_max_links_per_need``
times the needs of the project. Written links, those a ``needextend`` adds and the back
links are never counted; dead links and part links a rule computed are; the project's
needs are every need (external ones too), never their parts. One warning per link
type, strictly above the threshold, never with ``0``, on every build.

The shared cases are in the conformance corpus (``derive-dense-*``); these pin the rest
of the metric, the text, the default and the warning on a build that reads nothing.
"""

from __future__ import annotations

import dataclasses
import json
import os
import time
from pathlib import Path
from typing import Any

import pytest

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs_testkit import build_warnings


def _conf(threshold: int | None, links: dict[str, Any], extra: str = "") -> str:
    """A ``conf.py`` declaring ``links`` and the threshold (unset with ``None``)."""
    text = (
        'extensions = ["sphinx_needs"]\n'
        "needs_build_json = True\n"
        f"needs_links = {links!r}\n"
    )
    if threshold is not None:
        text += f"needs_derive_max_links_per_need = {threshold}\n"
    return text + extra


def _need(kind: str, need_id: str, *lines: str, status: str = "open") -> str:
    options = "".join(f"   {line}\n" for line in lines)
    return (
        f".. {kind}:: {need_id}\n   :id: {need_id}\n   :status: {status}\n{options}\n"
    )


def _project(conf: str, *needs: str, files: tuple = ()) -> dict[str, Any]:
    return {
        "buildername": "needs",
        "files": [
            (Path("conf.py"), conf),
            (Path("index.rst"), "Index\n=====\n\n" + "".join(needs)),
            *files,
        ],
    }


def _dense(app: Any) -> list[str]:
    return [w for w in build_warnings(app) if "[needs.derive_dense]" in w]


def _fields(app: Any) -> list[str]:
    """The link type each ``needs.derive_dense`` warning names, in order."""
    return [w.split("'")[1] for w in _dense(app)]


def _needs(app: Any) -> dict[str, dict[str, Any]]:
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    return data["versions"][data["current_version"]]["needs"]


# --- the default ---------------------------------------------------------------------


def test_the_default_threshold_is_100():
    """100 links per need of the project: where a build roughly doubles (the recon of
    #2202); ``0`` is the switch that turns the warning off."""
    (field,) = (
        f
        for f in dataclasses.fields(NeedsSphinxConfig)
        if f.name == "derive_max_links_per_need"
    )
    assert field.default == 100
    assert field.metadata == {"rebuild": "html", "types": (int,)}


@pytest.mark.parametrize(
    "test_app",
    [_project(_conf(None, {}), _need("req", "REQ_1"))],
    indirect=True,
)
def test_the_default_is_what_a_project_reads(test_app):
    app = test_app
    app.build()
    assert NeedsSphinxConfig(app.config).derive_max_links_per_need == 100


# --- the text ------------------------------------------------------------------------

#: five needs, four open; every need links the open needs but itself: 3 x 4 + 4 = 16
FIVE = (
    _need("req", "REQ_1"),
    _need("req", "REQ_2"),
    _need("req", "REQ_3"),
    _need("spec", "SPEC_1"),
    _need("spec", "SPEC_2", status="closed"),
)
OPEN_ALL = {"open_all": {"derive": {"kind": "links", "where": "status == 'open'"}}}


@pytest.mark.parametrize(
    "test_app", [_project(_conf(2, OPEN_ALL), *FIVE)], indirect=True
)
def test_the_warning_names_the_facts_of_a_rule(test_app):
    """The link type, the rule's kind, the links, the needs computing it, the needs of
    the project, the threshold, the longest list and its need, what to do and how to
    keep it; no location, as a finding of the configuration."""
    app = test_app
    app.build()
    assert _dense(app) == [
        "WARNING: Link type 'open_all' stores 16 links computed by its derive rule "
        "(kind 'links') on 5 needs, more than 2 per need of the project (5 needs, at "
        "most 10); the longest list, 4 links, is SPEC_2's. Narrow the rule's where, "
        "roll the set up on one need over the back links (a count or collect over a "
        "'_back' field), or show it in a view such as needtable; to keep it, raise "
        "needs_derive_max_links_per_need (0 never warns) or add "
        "'needs.derive_dense' to suppress_warnings [needs.derive_dense]"
    ]


TIE = {"rel": {}}


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            _conf(1, TIE),
            # REQ_2 and REQ_1 both compute the longest list (2 links): the lowest id
            _need("req", "REQ_2", ":rel: [[links_from_filter(\"type == 'spec'\")]]"),
            _need("req", "REQ_1", ":rel: [[links_from_filter(\"type == 'spec'\")]]"),
            _need("spec", "SPEC_1"),
            _need("spec", "SPEC_2", ":rel: [[links_from_filter(\"id == 'REQ_1'\")]]"),
        )
    ],
    indirect=True,
)
def test_the_warning_names_the_dynamic_functions_and_the_lowest_id_on_a_tie(test_app):
    """On a link type without a rule, the calls computed the lists; of two longest
    lists, the need with the lowest id is named, whatever the order written."""
    app = test_app
    app.build()
    assert _dense(app) == [
        "WARNING: Link type 'rel' stores 5 links computed by the dynamic function "
        "links_from_filter on 3 needs, more than 1 per need of the project (4 needs, "
        "at most 4); the longest list, 2 links, is REQ_1's. Narrow the calls' filter, "
        "roll the set up on one need over the back links (a count or collect over a "
        "'_back' field), or show it in a view such as needtable; to keep it, raise "
        "needs_derive_max_links_per_need (0 never warns) or add "
        "'needs.derive_dense' to suppress_warnings [needs.derive_dense]"
    ]


# --- the metric ----------------------------------------------------------------------

MIXED = {"mixed": {}}


def _mixed(calls: str) -> dict[str, Any]:
    call = f':mixed: SPEC_1, [[links_from_filter("{calls}")]]'
    return _project(
        _conf(1, MIXED),
        _need("req", "REQ_1", call),
        _need("req", "REQ_2", call),
        _need("spec", "SPEC_1", ":mixed: REQ_1, REQ_2", status="closed"),
        _need("spec", "SPEC_2", call),
        ".. needextend:: type == 'req'\n   :+mixed: SPEC_2\n\n",
    )


@pytest.mark.parametrize(
    ("test_app", "expected"),
    [
        # written 1 + 1 + 2 + 1 = 5 and extended 1 + 1 = 2, not counted; computed
        # 0 + 1 + 1 = 2 (REQ_1 but on itself), not more than 1 x 4 (2 + 7 = 9 would be)
        (_mixed("id == 'REQ_1'"), []),
        # computed 2 + 2 + 2 = 6 (the open needs but the need itself): 6 > 1 x 4
        (_mixed("status == 'open'"), ["mixed"]),
    ],
    indirect=["test_app"],
)
def test_written_links_are_not_counted(test_app, expected):
    """A link type with written links and a call counts only what the call computed;
    the links a ``needextend`` adds are not counted either."""
    app = test_app
    app.build()
    # the written and the extended links are stored
    assert {"SPEC_1", "SPEC_2"} <= set(_needs(app)["REQ_1"]["mixed"])
    assert _fields(app) == expected


TWO_CALLS = {"rel": {}}


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            _conf(1, TWO_CALLS),
            # REQ_1 computes REQ_2, then REQ_3 and REQ_4, then REQ_2 again: 3 links
            # stored; REQ_2 computes REQ_1, then REQ_3 and REQ_4: 3; 6 > 1 x 4
            _need(
                "req",
                "REQ_1",
                ":rel: [[links_from_filter(\"id == 'REQ_2'\")]], "
                "[[links_from_filter(\"id == 'REQ_3' or id == 'REQ_4'\")]], "
                "[[links_from_filter(\"id == 'REQ_2'\")]]",
            ),
            _need(
                "req",
                "REQ_2",
                ":rel: [[links_from_filter(\"id == 'REQ_1'\")]], "
                "[[links_from_filter(\"id == 'REQ_3' or id == 'REQ_4'\")]]",
            ),
            _need("req", "REQ_3"),
            _need("req", "REQ_4"),
        )
    ],
    indirect=True,
)
def test_every_call_of_a_list_is_counted(test_app):
    """Several calls in one need's list each add what they computed (one call alone,
    the first or the last, would make it 1 + 1 or 2 + 2, not more than 4); a link two
    calls of a need compute is stored once, and counted once."""
    app = test_app
    app.build()
    assert _needs(app)["REQ_1"]["rel"] == ["REQ_2", "REQ_3", "REQ_4"]
    assert _fields(app) == ["rel"]
    assert "stores 6 links" in _dense(app)[0]


BACK = {"rel": {"derive": {"kind": "links", "where": "type == 'spec'"}}}


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            # 4 needs each link the 2 specs but themselves: 2 + 2 + 1 + 1 = 6, at 6 / 4
            # = 1.5 per need; the 6 back links of rel_back would make it 12 / 4 = 3
            _conf(2, BACK),
            _need("req", "REQ_1"),
            _need("req", "REQ_2"),
            _need("spec", "SPEC_1"),
            _need("spec", "SPEC_2"),
        )
    ],
    indirect=True,
)
def test_back_links_are_not_counted(test_app):
    app = test_app
    app.build()
    needs = _needs(app)
    assert sum(len(n["rel_back"]) for n in needs.values()) == 6
    assert _dense(app) == []


DEAD = {"mentions": {"derive": {"kind": "content_links"}}}


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            _conf(1, DEAD),
            # 3 dead references stored in REQ_1's list: 3 > 1 x 2
            ".. req:: REQ_1\n   :id: REQ_1\n\n"
            "   :need:`NOPE_1`, :need:`NOPE_2` and :need:`NOPE_3`.\n\n",
            _need("req", "REQ_2"),
        )
    ],
    indirect=True,
)
def test_dead_links_a_rule_stores_are_counted(test_app):
    app = test_app
    app.build()
    assert _needs(app)["REQ_1"]["mentions"] == ["NOPE_1", "NOPE_2", "NOPE_3"]
    assert _fields(app) == ["mentions"]
    assert "stores 3 links" in _dense(app)[0]


PARTS = {
    "open_all": {
        "derive": {"kind": "links", "where": "status == 'open'", "include_self": True}
    }
}


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            # 3 needs, each links REQ_1 and REQ_2: 6 > 1 x 3; REQ_1's 3 parts are not
            # needs of the project (6 would not be more than 1 x 6)
            _conf(1, PARTS),
            ".. req:: REQ_1\n   :id: REQ_1\n   :status: open\n\n"
            "   :np:`(a) a`, :np:`(b) b` and :np:`(c) c`.\n\n",
            _need("req", "REQ_2"),
            _need("req", "REQ_3", status="closed"),
        )
    ],
    indirect=True,
)
def test_parts_are_not_needs_of_the_project(test_app):
    app = test_app
    app.build()
    assert _fields(app) == ["open_all"]
    assert "(3 needs, at most 3)" in _dense(app)[0]


EXTERNAL = {
    "current_version": "1.0",
    "versions": {
        "1.0": {
            "needs": {
                f"EXT_{i}": {"id": f"EXT_{i}", "type": "spec", "title": f"External {i}"}
                for i in (1, 2)
            }
        }
    },
}
EXTERNAL_LINKS = {
    # each local need links both local reqs: 2 x 2 = 4, not more than 1 x 4
    "reqs": {
        "derive": {"kind": "links", "where": "type == 'req'", "include_self": True}
    },
    # each local need links the 4 needs: 2 x 4 = 8 > 1 x 4
    "every": {
        "derive": {
            "kind": "links",
            "where": "type == 'req' or type == 'spec'",
            "include_self": True,
        }
    },
}


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            _conf(
                1,
                EXTERNAL_LINKS,
                'needs_external_needs = [{"base_url": "http://example.org/", '
                '"json_path": "external.json"}]\n',
            ),
            _need("req", "REQ_1"),
            _need("req", "REQ_2"),
            files=((Path("external.json"), json.dumps(EXTERNAL)),),
        )
    ],
    indirect=True,
)
def test_external_needs_are_needs_of_the_project(test_app):
    """An external need computes no rule, but it is a need of the project: 4 needs, 2
    computing each rule."""
    app = test_app
    app.build()
    assert _fields(app) == ["every"]
    assert "on 2 needs, more than 1 per need of the project (4 needs" in _dense(app)[0]


BY_TYPE = {
    "specs_to_reqs": {
        "derive_by_type": {"spec": {"kind": "links", "where": "type == 'req'"}}
    }
}


def _by_type(specs: int, reqs: int) -> dict[str, Any]:
    return _project(
        _conf(1, BY_TYPE),
        *(_need("spec", f"SPEC_{i}") for i in range(1, specs + 1)),
        *(_need("req", f"REQ_{i}") for i in range(1, reqs + 1)),
    )


@pytest.mark.parametrize(
    ("test_app", "expected"),
    [
        # SPEC_1 alone links the 3 reqs: 3 links, not more than 1 x 4 needs (though 3
        # per need computing it)
        (_by_type(1, 3), []),
        # SPEC_1 and SPEC_2 link the 3 reqs: 6 > 1 x 5
        (_by_type(2, 3), ["specs_to_reqs"]),
    ],
    indirect=["test_app"],
)
def test_a_rule_by_type_is_divided_by_the_needs_of_the_project(test_app, expected):
    """A rule for one need type is computed on its needs alone, and divided by every
    need of the project all the same."""
    app = test_app
    app.build()
    assert _fields(app) == expected


BOUNDARY = {
    "boundary": {
        "derive": {"kind": "links", "where": "type == 'spec'", "include_self": True}
    }
}


@pytest.mark.parametrize(
    ("test_app", "expected"),
    [
        # open_all: 16 links on 5 needs
        (_project(_conf(4, OPEN_ALL), *FIVE), []),  # 16 is not more than 20
        (_project(_conf(3, OPEN_ALL), *FIVE), ["open_all"]),  # 16 > 15
        (_project(_conf(0, OPEN_ALL), *FIVE), []),  # never
        (_project(_conf(-1, OPEN_ALL), *FIVE), []),  # less than 0 is 0
        (_project(_conf(None, OPEN_ALL), *FIVE), []),  # 100
        # boundary: the 2 specs on each of 5 needs, 10 links
        (_project(_conf(2, BOUNDARY), *FIVE), []),  # 10 is not more than 10
        (_project(_conf(1, BOUNDARY), *FIVE), ["boundary"]),  # 10 > 5
    ],
    indirect=["test_app"],
)
def test_the_threshold(test_app, expected):
    """Strictly more than the threshold times the needs; ``0`` never warns."""
    app = test_app
    app.build()
    assert _fields(app) == expected


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            _conf(
                2,
                {
                    **OPEN_ALL,
                    "ok": {"derive": {"kind": "links", "where": "status == 'closed'"}},
                    "rel": {},
                },
            ),
            *(
                need.replace(
                    "   :status:",
                    "   :rel: [[links_from_filter(\"status == 'open'\")]]\n   :status:",
                )
                for need in FIVE
            ),
        )
    ],
    indirect=True,
)
def test_one_warning_per_link_type(test_app):
    """Two dense link types, each computed on five needs: two warnings, one each, in
    the order the link types are declared."""
    app = test_app
    app.build()
    assert _fields(app) == ["open_all", "rel"]


# --- every build ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "test_app",
    [{**_project(_conf(2, OPEN_ALL), *FIVE), "buildername": "html"}],
    indirect=True,
)
def test_the_warning_is_given_on_every_build(test_app, make_app):
    """The links are counted on every build, from the needs as computed then: a build
    that reads no document warns again, and so does a fresh one (``-E``)."""
    app = test_app
    app.build()
    assert _fields(app) == ["open_all"]

    warm = make_app(buildername="html", srcdir=app.srcdir)
    warm.build()
    assert "0 added, 0 changed, 0 removed" in warm._status.getvalue()
    assert _fields(warm) == ["open_all"]

    fresh = make_app(buildername="html", srcdir=app.srcdir, freshenv=True)
    fresh.build()
    assert _fields(fresh) == ["open_all"]


@pytest.mark.parametrize(
    "test_app",
    [{**_project(_conf(2, OPEN_ALL), *FIVE), "buildername": "html"}],
    indirect=True,
)
def test_a_changed_threshold_applies_without_reading_a_document(test_app, make_app):
    """The threshold is read by the count, not by the needs: raising it silences the
    next build, which reads no document (``rebuild = "html"``)."""
    app = test_app
    app.build()
    assert _fields(app) == ["open_all"]

    conf = Path(app.srcdir, "conf.py")
    conf.write_text(
        conf.read_text(encoding="utf-8").replace(
            "needs_derive_max_links_per_need = 2", "needs_derive_max_links_per_need = 4"
        ),
        encoding="utf-8",
    )
    later = time.time_ns() + 60_000_000_000
    os.utime(conf, ns=(later, later))
    second = make_app(buildername="html", srcdir=app.srcdir)
    second.build()
    assert _fields(second) == []
