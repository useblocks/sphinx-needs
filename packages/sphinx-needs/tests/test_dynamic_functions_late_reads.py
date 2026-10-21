"""A read of a value the pass has not computed yet is reported as it happens.

Your own functions that declare nothing, and the calls whose filter cannot be read, are
computed after the built-in functions of their step, and read what they like. While
such a call runs, and while a filter or ``where`` of a built-in function or rule is
evaluated in a step that has such calls, every read of a need's field is watched: a
read of a value not computed yet at that moment is one ``needs.derive_scope`` per
reader and cause, naming the needs read, and so is a read of a computed value a
function's declaration does not name. Nothing else changes: the reader runs and holds
the value it computed, and a reader that never touched such a value (a ``and`` that
stopped before it) is not reported.
"""

import json
from pathlib import Path

import pytest

from sphinx_needs_testkit import build_warnings


def _built(app) -> dict:
    data = json.loads(Path(app.outdir, "needs.json").read_text("utf8"))
    return data["versions"][data["current_version"]]["needs"]


def _project(conf: str, index: str) -> dict:
    return {
        "buildername": "needs",
        "files": [(Path("conf.py"), conf), (Path("index.rst"), index)],
    }


def _line(index: str, need_id: str) -> int:
    """The 1-based line of the directive whose ``:id:`` is ``need_id``."""
    lines = index.splitlines()
    at = lines.index(f"   :id: {need_id}")
    while not lines[at].startswith(".. "):
        at -= 1
    return at + 1


def _scope(index: str, need_id: str, message: str) -> str:
    return (
        f"<srcdir>/index.rst:{_line(index, need_id)}: WARNING: {message} "
        "[needs.derive_scope]"
    )


_MY_LINKS = (
    "before it was computed: it is computed by your own function 'my_links', which "
    "runs after the built-in functions"
)

# -- the issue (#2354): built-in filters reading your own function's links -----------

CONF_ISSUE = """\
extensions = ["sphinx_needs"]
needs_build_json = True
suppress_warnings = ["config.cache"]


def my_links(app, need, needs, *args, **kwargs):
    return ["REQ_2"]


needs_functions = [my_links]
needs_links = {
    "blocks": {},
    "via": {},
    "via_eval": {},
    "via_current": {},
    "never": {},
    "never_eval": {},
    "via_rule": {"derive": {"kind": "links", "where": "'REQ_2' in blocks"}},
    "never_rule": {"derive": {"kind": "links", "where": "type == 'req' and 'REQ_2' in blocks"}},
}
"""

INDEX_ISSUE = """\
Issue
=====

.. req:: One
   :id: REQ_1

.. req:: Two
   :id: REQ_2

.. spec:: Its blocks are your own function's
   :id: SPEC_1
   :blocks: [[my_links()]]
   :via_current: [[links_from_filter("'REQ_2' in current_need['blocks']")]]

.. spec:: Reads blocks through a filter, on each tier
   :id: SPEC_2
   :via: [[links_from_filter("'REQ_2' in blocks")]]
   :via_eval: [[links_from_filter("[b for b in blocks if b == 'REQ_2']")]]

.. spec:: Never reaches blocks on a need computing it
   :id: SPEC_3
   :never: [[links_from_filter("type == 'req' and 'REQ_2' in blocks")]]
   :never_eval: [[links_from_filter("type == 'req' and [b for b in blocks]")]]
"""


@pytest.mark.parametrize("test_app", [_project(CONF_ISSUE, INDEX_ISSUE)], indirect=True)
def test_a_filter_reading_your_own_functions_value_is_reported(test_app):
    """A built-in call's filter, on the fast path (``via``) and through ``eval``
    (``via_eval``, a comprehension; ``via_current``, ``current_need``), and a ``links``
    rule's ``where`` read ``SPEC_1``'s ``blocks`` before ``my_links`` computed it: each
    is one warning -- the rule one for every need computing it -- and each keeps the
    value it computed. A filter whose ``and`` stops before ``blocks`` on the one need
    computing it (``never``, ``never_eval``, ``never_rule``: ``SPEC_1`` is no ``req``)
    reads no value not computed yet, and is not reported."""
    app = test_app
    app.build()
    rule = "derive rule 'links' for option 'via_rule' on 5 needs (REQ_1, REQ_2, SPEC_1 and 2 more)"
    lff = "dynamic function 'links_from_filter' for option"
    assert build_warnings(app) == [
        _scope(
            INDEX_ISSUE, "REQ_1", f"{rule} read 'blocks' on need 'SPEC_1' {_MY_LINKS}"
        ),
        _scope(
            INDEX_ISSUE,
            "SPEC_1",
            f"{lff} 'via_current' read 'blocks' on need 'SPEC_1' {_MY_LINKS}",
        ),
        *(
            _scope(
                INDEX_ISSUE,
                "SPEC_2",
                f"{lff} '{option}' read 'blocks' on need 'SPEC_1' {_MY_LINKS}",
            )
            for option in ("via", "via_eval")
        ),
    ]
    needs = _built(app)
    assert needs["SPEC_1"]["blocks"] == ["REQ_2"]
    # the values master computed: the readers ran before my_links
    for name in ("via", "via_eval", "via_current", "never", "never_eval"):
        assert all(needs[i][name] == [] for i in ("SPEC_1", "SPEC_2", "SPEC_3"))
    assert all(n["via_rule"] == n["never_rule"] == [] for n in needs.values())


# -- the readers of the recon matrix: each reported once, values as before ----------

CONF_MATRIX = """\
extensions = ["sphinx_needs"]
needs_build_json = True
suppress_warnings = ["config.cache"]


def my_links(app, need, needs, *args, **kwargs):
    return ["REQ_2"]


def my_hours(app, need, needs, *args, **kwargs):
    return 5


needs_functions = [my_links, my_hours]
needs_fields = {
    "hours": {"schema": {"type": "integer"}, "nullable": True},
    "cost": {"schema": {"type": "integer"}, "nullable": True},
    "s_f": {"schema": {"type": "number"}, "nullable": True},
    "clv_f": {"nullable": True},
    "cpf2": {"nullable": True},
}
needs_links = {
    "blocks": {},
    "opq": {},
    "via_opq": {},
    "cont": {},
    "cpf": {},
    "cont_rule": {"derive": {"kind": "content_links", "where": "'REQ_2' in blocks"}},
}
"""

INDEX_MATRIX = """\
Matrix
======

.. req:: One
   :id: REQ_1

.. req:: Two
   :id: REQ_2

.. spec:: Late feeder
   :id: SPEC_1
   :blocks: [[my_links()]]
   :opq: [[links_from_filter("len(needs) > 0 and id == 'REQ_1'")]]
   :hours: [[my_hours()]]
   :cost: 7

.. spec:: Readers
   :id: SPEC_2
   :links: SPEC_1
   :via_opq: [[links_from_filter("'REQ_1' in opq")]]
   :cont: [[links_from_content(filter="'REQ_2' in blocks")]]
   :cpf: [[copy("blocks", filter="'REQ_2' in blocks")]]
   :s_f: [[calc_sum("cost", filter="hours is not None and hours > 1")]]
   :clv_f: [[check_linked_values("yes", "cost", [99], filter_string="hours is not None and hours > 1")]]
   :cpf2: [[copy("title", filter="hours is not None and hours > 1")]]

   Refers :need:`SPEC_1`.
"""


@pytest.mark.parametrize(
    "test_app", [_project(CONF_MATRIX, INDEX_MATRIX)], indirect=True
)
def test_every_built_in_filter_reading_a_late_value_is_reported(test_app):
    """The filters a built-in function reads silently today, each reading a value your
    own function, or a call whose filter cannot be read, computes after it: the
    content filter of ``links_from_content`` and of a ``content_links`` rule, and the
    filters of ``copy``, ``calc_sum`` and ``check_linked_values``. Each is one
    warning, and holds what it held."""
    app = test_app
    app.build()
    hours = (
        "read 'hours' on need 'SPEC_1' before it was computed: it is computed by your "
        "own function 'my_hours', which runs after the built-in functions"
    )
    reported = [w for w in build_warnings(app) if "derive_scope" in w]
    assert reported == [
        _scope(INDEX_MATRIX, "SPEC_2", message)
        for message in (
            f"dynamic function 'links_from_content' for option 'cont' read 'blocks' "
            f"on need 'SPEC_1' {_MY_LINKS}",
            f"derive rule 'content_links' for option 'cont_rule' read 'blocks' on need "
            f"'SPEC_1' {_MY_LINKS}",
            f"dynamic function 'copy' for option 'cpf' read 'blocks' on need 'SPEC_1' "
            f"{_MY_LINKS}",
            "dynamic function 'links_from_filter' for option 'via_opq' read 'opq' on "
            "need 'SPEC_1' before it was computed: it is computed by a call whose "
            "filter cannot be read, which runs after the other built-in functions",
            f"dynamic function 'check_linked_values' for option 'clv_f' {hours}",
            f"dynamic function 'copy' for option 'cpf2' {hours}",
            f"dynamic function 'calc_sum' for option 's_f' {hours}",
        )
    ]
    spec_2 = _built(app)["SPEC_2"]
    assert (spec_2["via_opq"], spec_2["cont"], spec_2["cpf"]) == ([], [], [])
    assert (spec_2["s_f"], spec_2["clv_f"], spec_2["cpf2"]) == (0.0, "yes", "Readers")


# -- your own functions reading what is computed after them ---------------------------

CONF_OWN = """\
from sphinx_needs.api import reads

extensions = ["sphinx_needs"]
needs_build_json = True
suppress_warnings = ["config.cache"]
needs_id_regex = "^.+$"
needs_fields = {
    name: {"nullable": True} for name in ("a", "b", "d", "e", "f", "g", "h", "ref", "scan")
}
needs_links = {"opq": {}, "o": {}, "via": {}}


def make_b(app, need, needs, *args, **kwargs):
    return "B"


def read_b(app, need, needs, *args, **kwargs):
    return needs["SPEC_9"]["b"]


def read_opq(app, need, needs, *args, **kwargs):
    return list(needs["SPEC_5"]["opq"])


def whole(app, need, needs, *args, **kwargs):
    # a whole-need read touches every field, b among them
    return str(len(dict(needs["SPEC_9"])))


def scan(app, need, needs, *args, **kwargs):
    return ",".join(sorted(str(n.get("b")) for n in needs.values()))


def links_reading_ref(app, need, needs, *args, **kwargs):
    return [] if need.get("ref") is None else ["REQ_1"]


@reads()
def under(app, need, needs, *args, **kwargs):
    # declares nothing, and reads SPEC_9.b, not computed yet, and SPEC_1's via, final
    return f"{needs['SPEC_9']['b']}{len(needs['SPEC_1']['via'])}"


@reads()
def under_final(app, need, needs, *args, **kwargs):
    # declares nothing, and reads only a field nothing computes
    return needs["SPEC_1"]["title"]


needs_functions = [make_b, read_b, read_opq, whole, scan, links_reading_ref, under, under_final]
"""

INDEX_OWN = """\
Own
===

.. req:: One
   :id: REQ_1

.. spec:: Readers, all before SPEC_9
   :id: SPEC_1
   :a: [[read_b()]]
   :o: [[read_opq()]]
   :d: [[whole()]]
   :f: [[under()]]
   :g: [[under_final()]]
   :via: [[links_from_filter("id == 'REQ_1'")]]

.. spec:: A link field's own function reading a field of a later step
   :id: SPEC_3
   :ref: [[copy("title", "REQ_1")]]
   :o: [[links_reading_ref()]]

.. spec:: Scanners
   :id: SPEC_4
   :scan: [[scan()]]

.. spec:: An opaque call
   :id: SPEC_5
   :opq: [[links_from_filter("len(needs) > 0 and id == 'REQ_1'")]]
   :scan: [[scan()]]

.. spec:: The own functions' outputs
   :id: SPEC_9
   :b: [[make_b()]]

.. spec:: Another
   :id: SPEC_A
   :b: [[make_b()]]
"""


@pytest.mark.parametrize("test_app", [_project(CONF_OWN, INDEX_OWN)], indirect=True)
def test_your_own_functions_reading_later_values_are_reported(test_app):
    """Each read of a value not computed yet when your own function ran, with its
    cause: another function of yours after it (``a``; ``d``, through a whole-need
    read), a call whose filter cannot be read after it (``o``), a value of a later
    step (``SPEC_3``'s ``o`` in a link field reads ``ref``). A function computing a
    field on several needs is one warning naming them all (``scan``). A function
    that declares what it reads is reported for every read of a computed value it
    does not declare, computed yet or not (``under``), and for none of a value
    nothing computes (``under_final``). The values are what they were."""
    app = test_app
    app.build()
    later = (
        "after this call: your own functions, and the calls whose filter cannot be "
        "read, run after the built-in functions, in (need id, field) order"
    )
    assert build_warnings(app) == [
        _scope(
            INDEX_OWN,
            "SPEC_1",
            "dynamic function 'read_opq' for option 'o' read 'opq' on need 'SPEC_5' "
            f"before it was computed: it is computed by a call whose filter cannot be "
            f"read, {later}",
        ),
        _scope(
            INDEX_OWN,
            "SPEC_3",
            "dynamic function 'links_reading_ref' for option 'o' read 'ref' on need "
            "'SPEC_3' before it was computed: it is computed after the link fields, in "
            "a later step",
        ),
        _scope(
            INDEX_OWN,
            "SPEC_1",
            "dynamic function 'under' for option 'f' read 'b' on need 'SPEC_9' and "
            "'via' on need 'SPEC_1', which are computed in the pass and not among the "
            "reads 'under' declares: the call is not ordered after them, and may read "
            "them before they are computed; declare them among its reads",
        ),
        *(
            _scope(
                INDEX_OWN,
                "SPEC_1",
                f"dynamic function '{function}' for option '{option}' read 'b' on need "
                "'SPEC_9' before it was computed: it is computed by your own function "
                f"'make_b', {later}",
            )
            for function, option in (("read_b", "a"), ("whole", "d"))
        ),
        _scope(
            INDEX_OWN,
            "SPEC_4",
            "dynamic function 'scan' for option 'scan' on 2 needs (SPEC_4, SPEC_5) read "
            "'b' on 2 needs (SPEC_9, SPEC_A) before they were computed: they are "
            f"computed by your own function 'make_b', {later}",
        ),
    ]
    needs = _built(app)
    assert needs["SPEC_1"]["a"] is None
    assert needs["SPEC_1"]["o"] == needs["SPEC_3"]["o"] == []
    assert needs["SPEC_1"]["f"] == "None1"
    assert needs["SPEC_4"]["scan"] == needs["SPEC_5"]["scan"] == ",".join(["None"] * 7)
    assert needs["SPEC_9"]["b"] == "B"


# -- what is not reported -------------------------------------------------------------

CONF_QUIET = """\
extensions = ["sphinx_needs"]
needs_build_json = True
suppress_warnings = ["config.cache"]
needs_fields = {
    "hours": {"schema": {"type": "integer"}, "nullable": True},
    "total": {"schema": {"type": "number"}, "nullable": True},
    "seen": {"schema": {"type": "number"}, "nullable": True},
    "tag": {"nullable": True},
    "want": {"nullable": True},
    "joined": {
        "nullable": True,
        "derive": {"kind": "copy", "field": "title", "join": {"field": "tag", "equals": "want"}},
    },
}


def hours(app, need, needs, *args, **kwargs):
    return 5


def read_total(app, need, needs, *args, **kwargs):
    return needs["SPEC_5"]["total"]


def my_tag(app, need, needs, *args, **kwargs):
    return "T"


needs_functions = [hours, read_total, my_tag]
"""

INDEX_QUIET = """\
Quiet
=====

.. spec:: Your own function reading a built-in sum, computed before it
   :id: SPEC_0
   :seen: [[read_total()]]

.. spec:: Written
   :id: SPEC_1
   :hours: 2

.. spec:: The sum
   :id: SPEC_5
   :total: [[calc_sum("hours")]]

.. spec:: Your own function's hours and tag
   :id: SPEC_9
   :hours: [[hours()]]
   :tag: [[my_tag()]]
"""


@pytest.mark.parametrize("test_app", [_project(CONF_QUIET, INDEX_QUIET)], indirect=True)
def test_a_read_of_a_value_computed_already_is_not_reported(test_app):
    """``read_total`` runs after every built-in function, so the sum it reads is
    computed (from ``SPEC_9``'s hours read empty, which the sum itself reports, once):
    nothing more is reported, though the value it copies is partial. A join whose
    own ``equals`` is empty matches nothing, whatever the others hold, and reads no
    value not computed yet."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        _scope(
            INDEX_QUIET,
            "SPEC_5",
            "dynamic function 'calc_sum' for option 'total' read 'hours' on need "
            "'SPEC_9' before it was computed: it is computed by your own function "
            "'hours', which runs after the built-in functions",
        )
    ]
    needs = _built(app)
    assert needs["SPEC_5"]["total"] == needs["SPEC_0"]["seen"] == 2.0
    assert all(need["joined"] is None for need in needs.values())


CONF_NOTHING_LATE = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_links = {"via": {}}
needs_fields = {"summary": {"nullable": True}}
"""

INDEX_NOTHING_LATE = """\
Nothing late
============

.. req:: One
   :id: REQ_1
   :summary: [[copy("title")]]

.. req:: Two
   :id: REQ_2
   :via: [[links_from_filter("id == 'REQ_1'")]]
"""


@pytest.mark.parametrize(
    "test_app", [_project(CONF_NOTHING_LATE, INDEX_NOTHING_LATE)], indirect=True
)
def test_a_step_without_a_late_call_watches_nothing(test_app, monkeypatch):
    """With no call computed after the built-in functions, no read is watched: the
    filters and calls run as they would without the check."""
    from sphinx_needs import _read_watch

    opened: list[bool] = []
    watching = _read_watch.watching

    def counting(*args, **kwargs):
        opened.append(kwargs["filters_only"])
        return watching(*args, **kwargs)

    monkeypatch.setattr(_read_watch, "watching", counting)
    app = test_app
    app.build()
    assert build_warnings(app) == []
    assert opened == []
    assert _built(app)["REQ_2"]["via"] == ["REQ_1"]
