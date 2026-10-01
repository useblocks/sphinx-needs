import json
from pathlib import Path

import pytest
from sphinx import version_info
from syrupy.filters import props

from sphinx_needs.exceptions import FunctionParsingException
from sphinx_needs.functions.functions import (
    DynamicFunctionParsed,
    NeedAttribute,
)
from sphinx_needs_testkit import assert_no_warnings, build_warnings


@pytest.mark.parametrize(
    "func_str,expected_name,expected_args,expected_kwargs",
    [
        ("my_function()", "my_function", (), ()),
        ("my_function(1, 2, 3.0)", "my_function", (1, 2, 3.0), ()),
        ('my_function("a", "b", "c")', "my_function", ("a", "b", "c"), ()),
        ("my_function(True, False)", "my_function", (True, False), ()),
        ("my_function(need.a)", "my_function", (NeedAttribute("a"),), ()),
        (
            'my_function(1, "a", True)',
            "my_function",
            (1, "a", True),
            (),
        ),
        (
            'my_function(1, "a", True, kwarg1=2, kwarg2=3.0, kwarg3="b", kwarg4=False, kwarg5=need.b)',
            "my_function",
            (1, "a", True),
            (
                ("kwarg1", 2),
                ("kwarg2", 3.0),
                ("kwarg3", "b"),
                ("kwarg4", False),
                ("kwarg5", NeedAttribute("b")),
            ),
        ),
        (
            'my_function(kwarg1=[1, 2, 3], kwarg2=[1.0, 2.0, 3.0], kwarg3=["a", "b", "c"], kwarg4=[True, False])',
            "my_function",
            (),
            (
                ("kwarg1", [1, 2, 3]),
                ("kwarg2", [1.0, 2.0, 3.0]),
                ("kwarg3", ["a", "b", "c"]),
                ("kwarg4", [True, False]),
            ),
        ),
    ],
)
def test_dynamic_function_from_string(
    func_str, expected_name, expected_args, expected_kwargs
):
    dynamic_func = DynamicFunctionParsed.from_string(func_str, allow_need=True)

    assert dynamic_func.name == expected_name
    assert dynamic_func.args == expected_args
    assert dynamic_func.kwargs == expected_kwargs


@pytest.mark.parametrize(
    "func_str,error_message",
    [
        ("", "Error parsing dynamic function: Not a function call"),
        ("x.", "Error parsing dynamic function: Not a function call"),
        ("xx", "Error parsing dynamic function: Not a function call"),
        (
            "dunc(None)",
            "Error parsing dynamic function 'dunc': Unsupported arg 0 value type",
        ),
        (
            "dunc([None])",
            "Error parsing dynamic function 'dunc': Unsupported arg 0 item 0 value type",
        ),
        (
            "dunc(x)",
            "Error parsing dynamic function 'dunc': Unsupported arg 0 value type",
        ),
        (
            "dunc(1, x.y)",
            "Error parsing dynamic function 'dunc': Unsupported arg 1 value type",
        ),
        (
            "dunc(func())",
            "Error parsing dynamic function 'dunc': Unsupported arg 0 value type",
        ),
        (
            "dunc(x=x)",
            "Error parsing dynamic function 'dunc': Unsupported kwarg 'x' value type",
        ),
        (
            "dunc(1, y=x.y)",
            "Error parsing dynamic function 'dunc': Unsupported kwarg 'y' value type",
        ),
        (
            "dunc(z=func())",
            "Error parsing dynamic function 'dunc': Unsupported kwarg 'z' value type",
        ),
        (
            "dunc(x=None)",
            "Error parsing dynamic function 'dunc': Unsupported kwarg 'x' value type",
        ),
        (
            "dunc(x=[None])",
            "Error parsing dynamic function 'dunc': Unsupported kwarg 'x' item 0 value type",
        ),
        (
            "dunc([need.x])",
            "Error parsing dynamic function 'dunc': Unsupported arg 0 item 0 value type",
        ),
        (
            "dunc(x=[1, need.x])",
            "Error parsing dynamic function 'dunc': Unsupported kwarg 'x' item 1 value type",
        ),
    ],
)
def test_dynamic_function_from_string_fail(func_str, error_message):
    with pytest.raises(FunctionParsingException, match=error_message):
        DynamicFunctionParsed.from_string(func_str, allow_need=True)


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_dynamic_functions",
        }
    ],
    indirect=True,
)
def test_doc_dynamic_functions(test_app, snapshot):
    app = test_app
    app.build()

    warning_records = build_warnings(app)
    assert warning_records == [
        "<srcdir>/index.rst:26: WARNING: Need could not be created: 'tags' value is invalid: only one string, dynamic function or variant function allowed per array item. [needs.create_need]",
        "<srcdir>/index.rst:47: WARNING: Need could not be created: Field 'test_func' is invalid: Error parsing dynamic function 'test': Unsupported arg 0 value type [needs.create_need]",
        "<srcdir>/index.rst:53: WARNING: Need could not be created: Field 'test_func' is invalid: Error parsing dynamic function 'test': Unsupported arg 0 value type [needs.create_need]",
        "<srcdir>/index.rst:45: WARNING: Error while executing function 'copy': Need not found [needs.dynamic_function]",
    ]

    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    # since 9.0.0 ``[[...]]`` in a need's CONTENT is plain text, and only the ``ndf`` role runs
    # a dynamic function there.  Sphinx's smartquotes transform has already curled the quotes by
    # the time the text is rendered -- which is what the removed scan used to undo before it ran
    # the call, and one of the reasons the syntax was surprising.
    assert "This is id [[copy(\u201cid\u201d)]]" in html
    assert "This is the best id SP_TOO_001" in html
    assert "nested id [[copy(\u2018id\u2019)]]" in html
    assert "nested id best TEST_6" in html
    # a link's URI is left alone too
    assert "href=\"http://www.[[copy('id')]]\"" in html
    # an ``ndf`` reached through a substitution used as an INTERNAL hyperlink reference
    # (``|intsub|_``): the reference node carries a refid and NO refuri, and the walk this
    # PR replaced returned early on exactly that, never visiting the reference's children.
    # It rendered ``??``; here it resolves.  The other half of this assertion is the
    # expected-warnings list above, which is exact and holds a single "Need not found" --
    # the one from the need-less ``:ndf:`` at index.rst:45, not a second, spurious one.
    assert (
        'via an internal link: <a class="reference internal" '
        'href="#dynamic-functions">SP_TOO_001</a>' in html
    )

    json_data = Path(app.outdir, "needs.json").read_text(encoding="utf-8")
    needs = json.loads(json_data)
    assert needs == snapshot(exclude=props("created", "project", "creator"))


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_df_calc_sum",
        }
    ],
    indirect=True,
)
def test_doc_df_calc_sum(test_app):
    app = test_app
    app.build()
    assert_no_warnings(app)
    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    assert "43210" in html  # all hours
    assert "3210" in html  # hours of linked needs
    assert "210" in html  # hours of filtered needs


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_df_check_linked_values",
        }
    ],
    indirect=True,
)
def test_doc_df_linked_values(test_app):
    app = test_app
    app.build()
    assert_no_warnings(app)
    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    assert "all_good" in html
    assert "all_bad" not in html
    assert "all_awesome" in html


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_df_links_from_content",
        }
    ],
    indirect=True,
)
def test_doc_df_links_from_content(test_app, snapshot):
    app = test_app
    app.build()
    warning_records = build_warnings(app)
    assert warning_records == [
        "<srcdir>/index.rst:51: WARNING: links_from_content: no stored node for need 'unknown1' [needs.dynamic_function]",
        "<srcdir>/index.rst:51: WARNING: links_from_content: no stored node for need 'unknown2' [needs.dynamic_function]",
        "<srcdir>/index.rst:57: WARNING: Error while executing function 'links_from_content': No need found for links_from_content [needs.dynamic_function]",
        "WARNING: links_from_content: no stored node for need 'unknown3' [needs.dynamic_function]",
    ]

    json_data = Path(app.outdir, "needs.json").read_text(encoding="utf-8")
    needs = json.loads(json_data)
    assert needs == snapshot(exclude=props("created", "project", "creator"))


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_df_user_functions",
        }
    ],
    indirect=True,
)
def test_doc_df_user_functions(test_app):
    app = test_app
    app.build()

    warning_records = build_warnings(app)
    # print(warnings)
    expected = [
        "<srcdir>/index.rst:12: WARNING: Error while resolving dynamic values for field 'status', of need 'TEST_2': dynamic function value <class 'object'> is not of type 'string' [needs.dynamic_function]",
        "<srcdir>/index.rst:16: WARNING: Return value of function 'bad_function' is of type <class 'object'>. Allowed are str, int, float, list [needs.dynamic_function]",
        "<srcdir>/index.rst:18: WARNING: Error parsing dynamic function: Not a function call [needs.dynamic_function]",
        "<srcdir>/index.rst:20: WARNING: Unknown function 'unknown' [needs.dynamic_function]",
    ]
    if version_info >= (7, 3):
        warn = "WARNING: cannot cache unpickable configuration value: 'needs_functions' (because it contains a function, class, or module object)"
        if version_info >= (8, 0):
            warn += " [config.cache]"
        if version_info >= (8, 2):
            warn = warn.replace("unpickable", "unpickleable")
        expected.insert(0, warn)
    assert warning_records == expected

    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    assert "Awesome" in html
    # the same call written as ``[[...]]`` in the content is plain text since 9.0.0
    assert "[[my_own_function()]] is not a dynamic function here" in html


# -- the ``need_func`` role, removed in 9.0.0 --------------------------------
#
# It was deprecated in 4.0.0 together with ``[[...]]`` in a need's content, and
# ``ndf`` replaces both.  Nothing registers it any more, so a document that still
# writes it gets docutils' own diagnostic for a role that does not exist.

NEED_FUNC_CONF = """\
extensions = ["sphinx_needs"]
"""

NEED_FUNC_INDEX = """\
Removed role
============

.. req:: One
   :id: R_ONE

   This is id :need_func:`[[copy("id")]]`
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), NEED_FUNC_CONF),
                (Path("index.rst"), NEED_FUNC_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_need_func_role_removed(test_app):
    app = test_app
    app.build()

    warning_records = build_warnings(app)
    assert len(warning_records) == 1, warning_records
    assert 'Unknown interpreted text role "need_func"' in warning_records[0]


# -- ``copy`` with ``upper``/``lower`` on a list option -----------------------
#
# They used to case the list's printed form, so a list of two tags became ONE tag,
# ``"['ALPHA', 'BETA']"``; they now case each item.

COPY_CASE_CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
"""

COPY_CASE_INDEX = """\
Copy with a case change
=======================

.. req:: Source
   :id: SRC_1
   :tags: Alpha, beta
   :status: Open

   Tags as text: :ndf:`copy("tags", upper=True)`

.. spec:: Upper-cased tags
   :id: UPPER
   :tags: [[copy("tags", "SRC_1", upper=True)]]
   :status: [[copy("status", "SRC_1", upper=True)]]

.. spec:: Lower-cased tags
   :id: LOWER
   :tags: [[copy("tags", "SRC_1", lower=True)]]
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), COPY_CASE_CONF),
                (Path("index.rst"), COPY_CASE_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_doc_df_copy_case_of_a_list(test_app):
    app = test_app
    app.build()
    assert_no_warnings(app)

    needs = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    needs = needs["versions"][""]["needs"]

    assert needs["UPPER"]["tags"] == ["ALPHA", "BETA"]
    assert needs["LOWER"]["tags"] == ["alpha", "beta"]
    # a value that is not a list is cased as before
    assert needs["UPPER"]["status"] == "OPEN"

    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    assert "Tags as text: ALPHA, BETA" in html


# -- ``copy`` with ``c.this_doc()`` in its filter ----------------------------------
#
# The source is the first need in the document of the current need, not the first need
# of the project. The filter used to be evaluated without a document, so ``c.this_doc()``
# failed and ``copy`` fell back to copying from the current need.


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), COPY_CASE_CONF),
                (
                    Path("index.rst"),
                    "Copy in this document\n=====================\n\n"
                    ".. toctree::\n\n   a_other\n\n"
                    ".. req:: Source in this document\n"
                    "   :id: COPY_THIS_DOC\n"
                    "   :status: here\n\n"
                    ".. spec:: Copier\n"
                    "   :id: COPY_TARGET\n"
                    '   :status: [[copy("status", filter="c.this_doc() and type == \'req\'")]]\n',
                ),
                # read first, so without c.this_doc() it would be the source
                (
                    Path("a_other.rst"),
                    "Other document\n==============\n\n"
                    ".. req:: Source in another document\n"
                    "   :id: COPY_OTHER_DOC\n"
                    "   :status: elsewhere\n",
                ),
            ],
        }
    ],
    indirect=True,
)
def test_doc_df_copy_filter_this_doc(test_app):
    app = test_app
    app.build()
    assert_no_warnings(app)

    needs = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    needs = needs["versions"][""]["needs"]

    assert needs["COPY_TARGET"]["status"] == "here"


# -- ``links_from_filter`` ------------------------------------------------------
#
# No filter below reads a field that is itself a dynamic function: those are
# resolved need by need, so what such a filter sees depends on the order of the needs.

LINKS_FROM_FILTER_CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
"""

LINKS_FROM_FILTER_INDEX = """\
Links from a filter
===================

.. req:: Open requirement with a part
   :id: LFF_R1
   :status: open

   Part: :np:`(p1) part one`

.. req:: Open requirement
   :id: LFF_R2
   :status: open

.. req:: Closed requirement
   :id: LFF_R3
   :status: closed

.. spec:: Collector
   :id: LFF_COLL
   :links: [[links_from_filter("type == 'req' and status == 'open'")]]

.. spec:: Collector matching itself
   :id: LFF_SELF_EX
   :links: [[links_from_filter("id == 'LFF_R2' or id == 'LFF_SELF_EX'")]]

.. spec:: Collector matching itself, kept
   :id: LFF_SELF_IN
   :links: [[links_from_filter("id == 'LFF_R2' or id == 'LFF_SELF_IN'", include_self=True)]]

.. spec:: Parts not searched
   :id: LFF_PARTS_DEF
   :links: [[links_from_filter("id_parent == 'LFF_R1'")]]

.. spec:: Parts searched
   :id: LFF_PARTS_IN
   :links: [[links_from_filter("id_parent == 'LFF_R1'", include_parts=True)]]

.. spec:: Parts searched, own parts excluded
   :id: LFF_OWN_EX
   :links: [[links_from_filter("id_parent == 'LFF_R1' or id_parent == 'LFF_OWN_EX'", include_parts=True)]]

   Own part: :np:`(q1) own part`

.. spec:: Parts searched, own parts kept
   :id: LFF_OWN_IN
   :links: [[links_from_filter("id_parent == 'LFF_OWN_IN'", include_parts=True, include_self=True)]]

   Own part: :np:`(q1) own part`

.. spec:: Nothing found, allowed
   :id: LFF_NONE
   :links: [[links_from_filter("status == 'nonexistent'", allow_empty=True)]]

.. spec:: Links as text
   :id: LFF_NDF

   Open requirements: :ndf:`links_from_filter("type == 'req' and status == 'open'")`
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), LINKS_FROM_FILTER_CONF),
                (Path("index.rst"), LINKS_FROM_FILTER_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_doc_df_links_from_filter(test_app):
    app = test_app
    app.build()
    assert_no_warnings(app)

    needs = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    needs = needs["versions"][""]["needs"]

    # several needs found, in document order, and linked back
    assert needs["LFF_COLL"]["links"] == ["LFF_R1", "LFF_R2"]
    assert "LFF_COLL" in needs["LFF_R1"]["links_back"]
    assert "LFF_COLL" in needs["LFF_R2"]["links_back"]
    assert "LFF_COLL" not in needs["LFF_R3"]["links_back"]

    # the collector itself is excluded unless include_self=True
    assert needs["LFF_SELF_EX"]["links"] == ["LFF_R2"]
    assert needs["LFF_SELF_IN"]["links"] == ["LFF_R2", "LFF_SELF_IN"]

    # parts are searched only with include_parts=True
    assert needs["LFF_PARTS_DEF"]["links"] == ["LFF_R1"]
    assert needs["LFF_PARTS_IN"]["links"] == ["LFF_R1", "LFF_R1.p1"]
    # the collector's own parts count as itself
    assert needs["LFF_OWN_EX"]["links"] == ["LFF_R1", "LFF_R1.p1"]
    assert needs["LFF_OWN_IN"]["links"] == ["LFF_OWN_IN", "LFF_OWN_IN.q1"]

    # nothing found, and allow_empty=True keeps it silent
    assert needs["LFF_NONE"]["links"] == []

    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    assert "Open requirements: LFF_R1, LFF_R2" in html


LINKS_FROM_FILTER_EMPTY_INDEX = """\
Links from an empty filter
==========================

.. req:: Requirement
   :id: LFF_R1

.. spec:: Collector
   :id: LFF_COLL
   :links: [[links_from_filter("")]]
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), LINKS_FROM_FILTER_CONF),
                (Path("index.rst"), LINKS_FROM_FILTER_EMPTY_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_doc_df_links_from_filter_empty(test_app):
    app = test_app
    app.build()

    warning_records = build_warnings(app)
    assert len(warning_records) == 1, warning_records
    assert "links_from_filter needs a non-empty filter" in warning_records[0]
    assert "[needs.dynamic_function]" in warning_records[0]

    needs = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    assert needs["versions"][""]["needs"]["LFF_COLL"]["links"] == []


LINKS_FROM_FILTER_NO_MATCH_INDEX = """\
Links from a filter which finds nothing
=======================================

.. req:: Requirement
   :id: LFF_R1

.. spec:: Nothing found
   :id: LFF_NONE
   :links: [[links_from_filter("status == 'nonexistent'")]]

.. spec:: Only itself found
   :id: LFF_ONLY_SELF
   :links: [[links_from_filter("id == 'LFF_ONLY_SELF'")]]
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), LINKS_FROM_FILTER_CONF),
                (Path("index.rst"), LINKS_FROM_FILTER_NO_MATCH_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_doc_df_links_from_filter_no_match(test_app):
    app = test_app
    app.build()

    warning_records = build_warnings(app)
    assert len(warning_records) == 2, warning_records
    assert all("[needs.links_from_filter]" in w for w in warning_records)
    assert "index.rst:7:" in warning_records[0]
    assert "no need passed the filter \"status == 'nonexistent'\"" in warning_records[0]
    assert "index.rst:11:" in warning_records[1]
    assert "unless include_self=True" in warning_records[1]

    needs = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    needs = needs["versions"][""]["needs"]
    assert needs["LFF_NONE"]["links"] == []
    assert needs["LFF_ONLY_SELF"]["links"] == []


# ``links_from_filter`` replacing a project's own function, which linked a need to
# every system requirement in its own directory:
#
#     path = need["docname"].replace("index", "")
#     for nd in needs.values():
#         if not nd["is_external"] and nd["docname"].startswith(path) and nd["type"] == ...:
#             links.append(nd["id"])
#
# The filter cuts the docname after its last "/" instead of removing the string
# "index", so a collector outside an ``index`` document finds its directory too.

LINKS_FROM_FILTER_SYSTEM_CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_types = [
    {"directive": "sysreq", "title": "System requirement", "prefix": "SR_"},
    {"directive": "sysarch", "title": "System architecture", "prefix": "SA_"},
]
"""

LINKS_FROM_FILTER_SYSTEM_FILTER = (
    "not is_external and docname"
    # the collector's directory: its docname up to and including the last "/"
    ' and docname.startswith(current_need["docname"][: current_need["docname"].rfind("/") + 1])'
    ' and type == "sysreq"'
)


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), LINKS_FROM_FILTER_SYSTEM_CONF),
                (
                    Path("index.rst"),
                    "Root\n====\n\n.. toctree::\n\n   system/index\n",
                ),
                # listed first, so that ``system/`` exists for the files below it
                (
                    Path("system/index.rst"),
                    "System\n======\n\n.. toctree::\n\n"
                    "   central_locking/index\n"
                    "   central_locking/details\n"
                    "   other/index\n",
                ),
                (
                    Path("system/central_locking/index.rst"),
                    "Central locking\n===============\n\n"
                    ".. sysreq:: Lock\n   :id: SR_LOCK\n\n"
                    ".. sysarch:: Locking architecture\n   :id: SA_LOCK\n"
                    f"   :links: [[links_from_filter('{LINKS_FROM_FILTER_SYSTEM_FILTER}')]]\n",
                ),
                (
                    Path("system/central_locking/details.rst"),
                    "Details\n=======\n\n"
                    ".. sysreq:: Unlock\n   :id: SR_UNLOCK\n\n"
                    ".. sysarch:: Unlocking architecture\n   :id: SA_UNLOCK\n"
                    f"   :links: [[links_from_filter('{LINKS_FROM_FILTER_SYSTEM_FILTER}')]]\n",
                ),
                (
                    Path("system/other/index.rst"),
                    "Other\n=====\n\n"
                    ".. sysreq:: Other\n   :id: SR_OTHER\n\n"
                    ".. sysarch:: Other architecture\n   :id: SA_OTHER\n"
                    f"   :links: [[links_from_filter('{LINKS_FROM_FILTER_SYSTEM_FILTER}')]]\n",
                ),
            ],
        }
    ],
    indirect=True,
)
def test_doc_df_links_from_filter_system_requirements(test_app):
    app = test_app
    app.build()
    assert_no_warnings(app)

    needs = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    needs = needs["versions"][""]["needs"]

    # every system requirement in the collector's directory, whichever document holds it
    assert needs["SA_LOCK"]["links"] == ["SR_LOCK", "SR_UNLOCK"]
    assert needs["SA_OTHER"]["links"] == ["SR_OTHER"]
    # not an ``index`` document: ``replace("index", "")`` would have found SR_UNLOCK only
    assert needs["SA_UNLOCK"]["links"] == ["SR_LOCK", "SR_UNLOCK"]


# ``links_from_filter`` linking to the needs in the same file and the same chapter.
# ``sections`` runs from the need's own section up to the document title, so equal
# lists mean the same chapter under the same parents; ``c.this_doc()`` is still needed,
# because another file can repeat every title.

LINKS_FROM_FILTER_CHAPTER = (
    "[[links_from_filter('c.this_doc() and sections == current_need[\"sections\"]')]]"
)


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), LINKS_FROM_FILTER_CONF),
                (
                    Path("index.rst"),
                    "Vehicle\n=======\n\n.. toctree::\n\n   other\n\n"
                    "Braking\n-------\n\n"
                    ".. req:: Brake\n   :id: LFF_BRAKE\n\n"
                    ".. req:: Brake light\n   :id: LFF_BRAKE_LIGHT\n\n"
                    ".. spec:: Braking collector\n   :id: LFF_BRAKE_SPEC\n"
                    f"   :links: {LINKS_FROM_FILTER_CHAPTER}\n\n"
                    "Emergency braking\n~~~~~~~~~~~~~~~~~\n\n"
                    ".. req:: Emergency brake\n   :id: LFF_EMERGENCY\n\n"
                    "Steering\n--------\n\n"
                    ".. req:: Steer\n   :id: LFF_STEER\n\n"
                    ".. spec:: Steering collector\n   :id: LFF_STEER_SPEC\n"
                    f"   :links: {LINKS_FROM_FILTER_CHAPTER}\n",
                ),
                # the same document title and chapter, in another file
                (
                    Path("other.rst"),
                    "Vehicle\n=======\n\n"
                    "Braking\n-------\n\n"
                    ".. req:: Brake in another file\n   :id: LFF_BRAKE_OTHER\n",
                ),
            ],
        }
    ],
    indirect=True,
)
def test_doc_df_links_from_filter_same_file_and_chapter(test_app):
    app = test_app
    app.build()
    assert_no_warnings(app)

    needs = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    needs = needs["versions"][""]["needs"]

    # only c.this_doc() tells these two apart
    assert needs["LFF_BRAKE_OTHER"]["sections"] == needs["LFF_BRAKE"]["sections"]

    # not the collector itself, not the subchapter, not the same chapter in other.rst
    assert needs["LFF_BRAKE_SPEC"]["links"] == ["LFF_BRAKE", "LFF_BRAKE_LIGHT"]
    assert needs["LFF_STEER_SPEC"]["links"] == ["LFF_STEER"]
