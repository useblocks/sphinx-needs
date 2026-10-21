"""A function of your own that declares what it reads is computed in order.

``sphinx_needs.api.reads`` (or ``add_dynamic_function``'s ``reads``) declares the fields
a call reads, on its own need, on every need, or on the needs it names. Such a call is
a node like a built-in one: it is computed after what it declares, before the values
that read it, a read of itself is a cycle and a read of a later step is not run. A
function that declares nothing is computed after the built-in functions, as before.
"""

import functools
import json
from pathlib import Path

import pytest

from sphinx_needs.api import reads
from sphinx_needs.functions.functions import Reads
from sphinx_needs_testkit import build_warnings


def _built(app) -> dict:
    data = json.loads(Path(app.outdir, "needs.json").read_text("utf8"))
    return data["versions"][data["current_version"]]["needs"]


def _project(conf: str, index: str) -> dict:
    return {
        "buildername": "needs",
        "files": [(Path("conf.py"), conf), (Path("index.rst"), index)],
    }


def _warnings(app) -> list[str]:
    # but Sphinx's own about caching a function (spelt "unpickable" by Sphinx 7)
    return [w for w in build_warnings(app) if "cannot cache unpick" not in w]


# -- the issue's project (#2354), its function declared ------------------------------

CONF_ISSUE = """\
from sphinx_needs.api import reads

extensions = ["sphinx_needs"]
needs_build_json = True


{declare}
def my_links(app, need, needs, *args, **kwargs):
    return ["REQ_2"]


needs_functions = [my_links]
needs_links = {{
    "blocks": {{}},
    "via": {{}},
    "via_rule": {{"derive": {{"kind": "links", "where": "'REQ_2' in blocks"}}}},
    "all_links": {{"derive": {{"kind": "union", "fields": ["links", "blocks"]}}}},
    "via_union": {{}},
}}
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
   :links: REQ_1

.. spec:: Reads blocks through a filter
   :id: SPEC_2
   :via: [[links_from_filter("'REQ_2' in blocks")]]
   :via_union: [[links_from_filter("'REQ_2' in all_links")]]
"""


@pytest.mark.parametrize(
    "test_app",
    [_project(CONF_ISSUE.format(declare="@reads()"), INDEX_ISSUE)],
    indirect=True,
)
def test_a_declared_function_is_read_by_the_built_in_functions_complete(test_app):
    """``my_links`` declares that it reads no computed value, so its links are computed
    before the built-in readers of ``blocks``: a filter (``via``), a ``links`` rule
    (``via_rule``, on every need) and a union over it, which is computed with the
    built-in functions again, and the filter reading the union (``via_union``)."""
    app = test_app
    app.build()
    assert _warnings(app) == []
    needs = _built(app)
    assert needs["SPEC_1"]["blocks"] == ["REQ_2"]
    assert needs["SPEC_1"]["all_links"] == ["REQ_1", "REQ_2"]
    assert needs["SPEC_2"]["via"] == needs["SPEC_2"]["via_union"] == ["SPEC_1"]
    assert {i: n["via_rule"] for i, n in needs.items()} == {
        "REQ_1": ["SPEC_1"],
        "REQ_2": ["SPEC_1"],
        "SPEC_1": [],
        "SPEC_2": ["SPEC_1"],
    }


@pytest.mark.parametrize(
    "test_app",
    [_project(CONF_ISSUE.format(declare=""), INDEX_ISSUE)],
    indirect=True,
)
def test_an_undeclared_function_is_still_computed_last(test_app):
    """The same project with ``my_links`` declaring nothing: it is computed after the
    built-in functions, so the readers of ``blocks`` read it empty, as before; the
    union over it is computed after it, and the filter reading the union is not run."""
    app = test_app
    app.build()
    needs = _built(app)
    assert needs["SPEC_1"]["blocks"] == ["REQ_2"]
    assert needs["SPEC_2"]["via"] == needs["SPEC_2"]["via_union"] == []
    assert all(n["via_rule"] == [] for n in needs.values())
    assert [w for w in _warnings(app) if "via_union" in w] == [
        "<srcdir>/index.rst:15: WARNING: dynamic function 'links_from_filter' for "
        "option 'via_union' reads 'all_links' on need 'SPEC_1', a union computed after "
        "your own functions and the calls whose filter cannot be read that fill its "
        "members, which this step cannot wait for: the call is not run and the field is "
        "left empty [needs.derive_scope]"
    ]


# -- a tr_link-like function, declared by its parameters -----------------------------

CONF_TR = """\
from sphinx_needs.api import reads

extensions = ["sphinx_needs"]
needs_build_json = True
needs_id_regex = "^.+$"
needs_types = [
    {"directive": "req", "title": "Req", "prefix": "R_"},
    {"directive": "test", "title": "Test", "prefix": "T_"},
]
needs_fields = {"references": {"nullable": True}}
needs_links = {
    "covers": {},
    "extra": {},
    "verified": {"derive": {"kind": "links", "where": "type == 'test' and len(links) > 0"}},
    "all_links": {"derive": {"kind": "union", "fields": ["links", "extra"]}},
    "cov_u": {},
}


@reads(own="test_option", every="target_option")
def my_link(app, need, needs, test_option, target_option, *args, **kwargs):
    wanted = need.get(test_option)
    if not wanted:
        return []
    return [
        other["id"] for other in needs.values() if other.get(target_option) == wanted
    ]


needs_functions = [my_link]
"""

INDEX_TR = """\
Tests
=====

.. req:: Req 0
   :id: REQ_0
   :covers: [[links_from_filter("type == 'test' and 'REQ_0' in links")]]
   :cov_u: [[links_from_filter("'REQ_0' in all_links")]]

.. req:: Req 1
   :id: REQ_1
   :covers: [[links_from_filter("type == 'test' and 'REQ_1' in links")]]

.. test:: Test 0
   :id: TC_0
   :references: REQ_0
   :links: [[my_link('references', 'id')]]

.. test:: Test 1
   :id: TC_1
   :references: REQ_1
   :links: [[my_link('references', 'id')]]

.. test:: Test 2
   :id: TC_2
   :references: REQ_0
   :links: [[my_link('references', 'id')]]
"""


@pytest.mark.parametrize("test_app", [_project(CONF_TR, INDEX_TR)], indirect=True)
def test_a_function_declared_by_its_parameters(test_app):
    """``own="test_option", every="target_option"``: the arguments of those parameters
    name the fields it reads (``references`` on its own need, ``id`` on every need,
    which nothing computes), so the readers of its links hold them: a filter on them,
    a ``links`` rule's ``where`` (on every need), a union and a filter on the union."""
    app = test_app
    app.build()
    assert _warnings(app) == []
    needs = _built(app)
    assert [needs[i]["links"] for i in ("TC_0", "TC_1", "TC_2")] == [
        ["REQ_0"],
        ["REQ_1"],
        ["REQ_0"],
    ]
    assert needs["REQ_0"]["covers"] == ["TC_0", "TC_2"]
    assert needs["REQ_1"]["covers"] == ["TC_1"]
    assert needs["REQ_0"]["cov_u"] == ["TC_0", "TC_2"]
    assert needs["TC_2"]["all_links"] == ["REQ_0"]
    assert needs["REQ_1"]["verified"] == ["TC_0", "TC_1", "TC_2"]
    assert needs["TC_0"]["verified"] == ["TC_1", "TC_2"]


# -- the override, and a wrapper ----------------------------------------------------

CONF_ROUTES = """\
import functools

from sphinx_needs.api import add_dynamic_function, reads

extensions = ["sphinx_needs"]
needs_build_json = True
suppress_warnings = ["config.cache"]
needs_links = {"blocks": {}, "via": {}}


def theirs(app, need, needs, *args, **kwargs):
    return ["REQ_1"]


# a declaration naming no parameter of it, which the override replaces
reads(own="nope")(theirs)


@reads()
def base(app, need, needs, *args, **kwargs):
    return ["REQ_2"]


@functools.wraps(base)
def wrapped(app, need, needs, *args, **kwargs):
    return base(app, need, needs, *args, **kwargs)


def setup(app):
    add_dynamic_function(app, theirs, reads=reads())
    add_dynamic_function(app, wrapped, name="wrapped")
"""

INDEX_ROUTES = """\
Routes
======

.. req:: One
   :id: REQ_1

.. req:: Two
   :id: REQ_2

.. spec:: Theirs
   :id: SPEC_1
   :blocks: [[theirs()]]

.. spec:: Wrapped
   :id: SPEC_2
   :blocks: [[wrapped()]]

.. spec:: Reader
   :id: SPEC_3
   :via: [[links_from_filter("len(blocks) > 0")]]
"""


@pytest.mark.parametrize(
    "test_app", [_project(CONF_ROUTES, INDEX_ROUTES)], indirect=True
)
def test_the_override_and_a_wrapper_are_declared(test_app):
    """``add_dynamic_function(..., reads=...)`` declares a function you do not own, over
    the declaration it carries (here one naming no parameter of it, never checked); a
    wrapper made with ``functools.wraps`` carries the declaration of the function it
    wraps. Both are computed before the reader of ``blocks``."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    assert _built(app)["SPEC_3"]["via"] == ["SPEC_1", "SPEC_2"]


# -- what cannot be ordered ---------------------------------------------------------

CONF_LIMITS = """\
from sphinx_needs.api import reads

extensions = ["sphinx_needs"]
needs_build_json = True
suppress_warnings = ["config.cache"]
needs_fields = {"summary": {"nullable": True}}
needs_links = {"blocks": {}, "via": {}, "late": {}}


@reads(every="option")
def scan(app, need, needs, option):
    return [other["id"] for other in needs.values() if other.get(option)]


@reads(own="option")
def own_read(app, need, needs, option):
    return [need.get(option)] if need.get(option) else []


@reads(own="option")
def bad(app, need, needs, option):
    return ["REQ_1"]


@reads(own="nope")
def unknown(app, need, needs, option):
    return ["REQ_1"]


needs_functions = [scan, own_read, bad, unknown]
"""

INDEX_LIMITS = """\
Limits
======

.. req:: One
   :id: REQ_1
   :summary: [[copy("title")]]

.. spec:: Reads its own link type on every need
   :id: SPEC_1
   :blocks: [[scan('blocks')]]

.. spec:: Reads a field computed after the link fields
   :id: SPEC_2
   :summary: [[copy("title")]]
   :late: [[own_read('summary')]]

.. spec:: A declared argument that is no field name, twice; a declaration naming no parameter
   :id: SPEC_3
   :blocks: [[bad(need.summary)]]
   :via: [[bad(need.summary)]]
   :late: [[unknown('summary')]]
"""


@pytest.mark.parametrize(
    "test_app", [_project(CONF_LIMITS, INDEX_LIMITS)], indirect=True
)
def test_what_a_declaration_cannot_order(test_app):
    """A declared read of the call's own field is a cycle, named by the declaration; a
    declared read of a field computed after the link fields, from a link field, is not
    run. A declared parameter whose argument is no field name written out (here a
    ``need.<field>``) cannot be declared: one ``needs.config`` warning for the function,
    and its calls are computed after the built-in functions, as calls of a function
    that declares nothing. A declaration naming what is not a parameter of the function
    is one ``needs.config`` warning when the function is registered, and the function
    declares nothing."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "WARNING: Dynamic function 'unknown' declares what it reads, but 'nope' is not "
        "a parameter of it after app, need and needs; it is computed after the built-in "
        "functions, as a function that declares nothing [needs.config]",
        "<srcdir>/index.rst:17: WARNING: dynamic function 'bad' declares what it "
        "reads, but the declaration cannot be applied to its call for option 'blocks' "
        "of need 'SPEC_3': the argument of its parameter 'option' is need.summary, not "
        "a field name written in the call; such a call is computed after the built-in "
        "functions, as a call of a function that declares nothing [needs.config]",
        "<srcdir>/index.rst:8: WARNING: dynamic function 'scan' for option 'blocks' is "
        "on a cycle: 'blocks' on need 'SPEC_1', through scan's declared read of 'blocks' "
        "on every need; the field is left empty [needs.derive_cycle]",
        "<srcdir>/index.rst:12: WARNING: dynamic function 'own_read' for option 'late' "
        "reads 'summary' on need 'SPEC_2', which is final only after the link fields "
        "are computed: the call is not run and the field is left empty "
        "[needs.derive_scope]",
    ]
    needs = _built(app)
    assert needs["SPEC_1"]["blocks"] == needs["SPEC_2"]["late"] == []
    assert needs["SPEC_3"]["blocks"] == needs["SPEC_3"]["via"] == ["REQ_1"]


# -- a need.<field> argument computed in the same step ------------------------------

CONF_ARGUMENT = """\
from sphinx_needs.api import reads

extensions = ["sphinx_needs"]
needs_build_json = True
suppress_warnings = ["config.cache"]
needs_fields = {{k: {{"nullable": True}} for k in ("status2", "out", "selfa")}}


{declare}
def tagged(app, need, needs, value, target):
    # value is data; target names the field read on every need
    return f"{{value}}:{{sum(1 for n in needs.values() if n.get(target))}}"


@reads()
def echo_arg(app, need, needs, value):
    return str(value)


needs_functions = [tagged, echo_arg]
"""

INDEX_ARGUMENT = """\
Argument
========

.. spec:: A
   :id: SPEC_1
   :status2: [[copy("title")]]
   :out: [[tagged(need.status2, "status2")]]
   :selfa: [[echo_arg(need.selfa)]]
"""


@pytest.mark.parametrize(
    "test_app",
    [
        pytest.param(
            _project(CONF_ARGUMENT.format(declare=declare), INDEX_ARGUMENT), id=name
        )
        for name, declare in (("declared", '@reads(every="target")'), ("plain", ""))
    ],
    indirect=True,
)
def test_a_need_argument_computed_in_the_same_step_is_waited_for(test_app):
    """``need.status2`` is data the call is given (its parameter is not declared),
    computed by a built-in call of the same step: the declared call is computed after
    it, so it holds what it held undeclared. A declared call given its own field as
    data is a cycle, and says it runs through the argument."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "<srcdir>/index.rst:4: WARNING: dynamic function 'echo_arg' for option "
        "'selfa' is on a cycle: 'selfa' on need 'SPEC_1', through its argument "
        "need.selfa; the field is left empty [needs.derive_cycle]"
    ]
    assert _built(app)["SPEC_1"]["out"] == "A:1"


CONF_LATER = """\
from sphinx_needs.api import reads

extensions = ["sphinx_needs"]
needs_build_json = True
suppress_warnings = ["config.cache"]
needs_fields = {"s": {"nullable": True}}
needs_links = {"blocks": {}}


@reads()
def lk(app, need, needs, *args, **kwargs):
    return [] if needs["SPEC_1"]["s"] is None else ["REQ_1"]


needs_functions = [lk]
"""

INDEX_LATER = """\
Later
=====

.. req:: One
   :id: REQ_1

.. spec:: S
   :id: SPEC_1
   :s: [[copy("title")]]
   :blocks: [[lk()]]
"""


@pytest.mark.parametrize("test_app", [_project(CONF_LATER, INDEX_LATER)], indirect=True)
def test_a_declared_function_reading_a_later_step_is_told_so(test_app):
    """A declared function in a link field reading a field computed after the link
    fields reads it before it is computed: reported with that cause, not as a read
    its declaration lacks (the declaration names its own step's values)."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "<srcdir>/index.rst:7: WARNING: dynamic function 'lk' for option 'blocks' read "
        "'s' on need 'SPEC_1' before it was computed: it is computed after the link "
        "fields, in a later step [needs.derive_scope]"
    ]
    assert _built(app)["SPEC_1"]["blocks"] == []


# -- the decorator itself ----------------------------------------------------------


def test_reads_declares_the_function_it_is_applied_to():
    def mine(app, need, needs, option, *more, flag=None):
        return None

    declaration = reads(own="option", every="more")
    assert declaration == Reads(("option",), ("more",))
    assert declaration(mine) is mine
    assert mine.needs_reads is declaration  # ty: ignore[unresolved-attribute]
    assert reads(own=("option", "flag")) == Reads(("option", "flag"), ())
    assert reads() == Reads()
    # a wrapper copies the function's attributes, the declaration among them
    wrapper = functools.wraps(mine)(lambda *a: None)
    assert wrapper.needs_reads is declaration  # ty: ignore[unresolved-attribute]


def test_reads_refuses_what_it_cannot_declare():
    """A name must be a string; ``@reads`` without parentheses is refused by Python,
    as ``reads`` takes no positional argument, so it never replaces the function."""

    def mine(app, need, needs, option):
        return None

    with pytest.raises(TypeError, match="1 is not a name"):
        reads(own=("option", 1))  # ty: ignore[invalid-argument-type]
    with pytest.raises(TypeError, match="positional"):
        reads(mine)  # ty: ignore[too-many-positional-arguments]
    assert not hasattr(mine, "needs_reads")
