import re
from pathlib import Path

import pytest
from docutils import nodes
from sphinxcontrib.plantuml import plantuml
from syrupy.filters import props

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.directives.needuml import (
    NeedumlException,
    get_debug_node_from_puml_node,
)
from sphinx_needs_testkit import assert_no_warnings, build_warnings


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needuml"}],
    indirect=True,
)
def test_doc_build_html(test_app, snapshot):
    app = test_app
    app.build()

    assert Path(app.outdir, "index.html").read_text(encoding="utf8")

    data = SphinxNeedsData(app.env)

    all_needs = {k: {**v} for k, v in data.get_needs_view().items()}
    assert all_needs == snapshot()

    all_needumls = data.get_or_create_umls()
    assert all_needumls == snapshot(exclude=props("process_time"))


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needuml_duplicate_key"}],
    indirect=True,
)
def test_needuml_option_key_duplicate(test_app):
    app = test_app

    with pytest.raises(
        NeedumlException,
        match=re.escape(
            "Inside need: INT_001, found duplicate Needuml option key name: sequence"
        ),
    ):
        app.build()


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needuml_key_name_diagram"}],
    indirect=True,
)
def test_needuml_option_key_forbidden(test_app):
    app = test_app

    with pytest.raises(
        NeedumlException,
        match=re.escape("Needuml option key name can't be: diagram"),
    ):
        app.build()


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_needuml_diagram_allowmixing",
            "plantuml": True,
        }
    ],
    indirect=True,
)
def test_needuml_diagram_allowmixing(test_app):
    app = test_app
    app.build()
    # this build renders eight diagrams, and a failed render is only a WARNING to
    # sphinxcontrib-plantuml -- so without this the test is green on a renderer that
    # cannot run, which is how it spent years drawing with whatever `plantuml` the
    # machine carried. A renderer that cannot even be STARTED is a different message
    # ("plantuml command ... cannot be run"), also a WARNING: both are covered by
    # asserting the build emitted nothing at all
    assert_no_warnings(app)
    # the positive assertion is that the diagrams exist. Eight on a good build; none
    # under either failure (measured)
    assert list(Path(app.outdir, "_images").glob("plantuml-*"))


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needuml_save"}],
    indirect=True,
)
def test_needuml_save(test_app, snapshot):
    app = test_app
    app.build()

    # check generated plantuml code saved in given path
    from sys import platform

    if platform == "win32":
        assert "doc_needuml_save\\_build\\html" in str(app.outdir)
    else:
        assert "doc_needuml_save/_build/html" in str(app.outdir)
    assert app.config.needs_build_needumls == "my_needumls"

    uml_path = Path(app.outdir).joinpath(app.config.needs_build_needumls)
    umls = {
        "uml1": uml_path.joinpath("_build", "my_needuml.puml").read_text(),
        "uml2": uml_path.joinpath("_out", "sub_folder", "my_needs.puml").read_text(),
    }
    assert umls == snapshot


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needuml_save_with_abs_path"}],
    indirect=True,
)
def test_needuml_save_with_abs_path(test_app):
    app = test_app

    # this fails before plantuml is required, so the build never renders
    with pytest.raises(
        NeedumlException,
        match=re.escape(
            "Given save path: /_out/my_needuml.puml, is not a relative posix path."
        ),
    ):
        app.build()


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "needumls", "srcdir": "doc_test/doc_needuml_save"}],
    indirect=True,
)
def test_needumls_builder(test_app, snapshot):
    app = test_app
    app.build()

    # check generated plantuml code saved in given path
    from sys import platform

    if platform == "win32":
        assert "doc_needuml_save\\_build\\needumls" in str(app.outdir)
    else:
        assert "doc_needuml_save/_build/needumls" in str(app.outdir)

    uml_path = Path(app.outdir)
    umls = {
        "uml1": uml_path.joinpath("_build", "my_needuml.puml").read_text(),
        "uml2": uml_path.joinpath("_out", "sub_folder", "my_needs.puml").read_text(),
    }
    assert umls == snapshot


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_needuml_filter",
            "plantuml": True,
        }
    ],
    indirect=True,
)
def test_needuml_filter(test_app, snapshot):
    app = test_app
    app.build()

    all_needumls = app.env._needs_all_needumls
    assert all_needumls == snapshot(exclude=props("process_time"))

    html = Path(app.outdir, "index.html").read_text(encoding="utf8")
    assert "as ST_002 [[../index.html#ST_002]]" in html

    assert_no_warnings(app)


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_needuml_jinja_func_flow",
            "plantuml": True,
        }
    ],
    indirect=True,
)
def test_needuml_jinja_func_flow(test_app, snapshot):
    app = test_app
    app.build()

    all_needumls = app.env._needs_all_needumls
    assert all_needumls == snapshot(exclude=props("process_time"))

    html = Path(app.outdir, "index.html").read_text(encoding="utf8")
    assert "as ST_001 [[../index.html#ST_001]]" in html

    assert_no_warnings(app)


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needuml_jinja_func_need_removed"}],
    indirect=True,
)
def test_needuml_jinja_func_need_removed(test_app):
    app = test_app

    with pytest.raises(
        NeedumlException,
        match=re.escape(
            "Jinja function 'need()' is not supported in needuml directive."
        ),
    ):
        app.build()


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_needuml_jinja_func_import_negative_tests",
        }
    ],
    indirect=True,
)
def test_doc_needarch_jinja_import_negative(test_app):
    app = test_app

    with pytest.raises(
        NeedumlException,
        match=re.escape(
            "Jinja function 'import()' is not supported in needuml directive."
        ),
    ):
        app.build()


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_needuml_jinja_func_ref",
            "plantuml": True,
        }
    ],
    indirect=True,
)
def test_needuml_jinja_func_ref(test_app, snapshot):
    app = test_app
    app.build()

    all_needumls = app.env._needs_all_needumls
    assert all_needumls == snapshot(exclude=props("process_time"))

    html = Path(app.outdir, "index.html").read_text(encoding="utf8")
    assert "Marvel: [[../index.html#ST_001 Test story]]" in html
    assert "DC: [[../index.html#ST_002 Different text to explain the story]]" in html

    assert "Marvel: [[../index.html#ST_001.np_id np_id]]" in html
    assert "DC: [[../index.html#ST_001.np_id np_content]]" in html

    assert (
        "Marvel: [[../index.html#ST_001.np_id Different text to explain the story 2]]"
        in html
    )

    assert_no_warnings(app)


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_needuml_option_warnings",
            "plantuml": True,
        }
    ],
    indirect=True,
)
def test_needuml_option_warnings(test_app):
    """A bad ``:config:``, ``:extra:`` or ``:scale:`` value is reported.

    All three were silent before: an unknown config name was dropped without a word,
    a non-numeric scale fell back to 100 without a word, and an ``:extra:`` segment
    carrying no colon ended the whole build with an unhandled ``ValueError``.  A value
    that itself contains a colon must survive, the pair being split on the first colon
    only.

    Both options carry a trailing comma, so both produce one empty segment: it is
    skipped without a word, and ``:extra:`` must not report it as a malformed pair.
    """
    app = test_app
    app.build()

    assert build_warnings(app) == [
        "<srcdir>/index.rst:4: WARNING: config name 'no_such_config' is not defined in "
        "needs_flow_configs. [needs.needuml]",
        "<srcdir>/index.rst:4: WARNING: extra option 'broken' is not a 'key:value' pair. "
        "[needs.needuml]",
        '<srcdir>/index.rst:12: WARNING: scale value must be a number. "not-a-number" '
        "found [needs.diagram_scale]",
    ]
    # the trailing commas of both options are skipped in silence, as an empty
    # `:config:` segment always has -- no "extra option '' is not a pair" line
    assert not [line for line in build_warnings(app) if "''" in line]

    needuml, scaled = app.env._needs_all_needumls.values()
    assert needuml["extra"] == {"url": "https://example.com/a:b", "plain": "value"}
    assert 'card "https://example.com/a:b" as a' in needuml["content_calculated"]
    assert 'card "value" as b' in needuml["content_calculated"]
    # the known config name is still applied, the unknown one simply skipped
    assert "allowmixing" in needuml["content_calculated"]
    # the unusable scale still falls back to 100 and the diagram is still rendered,
    # the value is only now announced rather than silently discarded
    assert scaled["scale"] == "not-a-number"
    assert 'card "fallback scale" as c' in scaled["content_calculated"]
    assert ".svg" in Path(app.outdir, "index.html").read_text(encoding="utf8")


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needuml_key_missing"}],
    indirect=True,
)
def test_needuml_jinja_func_uml_missing_key(test_app):
    """``uml()`` with an arch key the need does not have names the key and the need.

    The guard subscripted ``arch`` before testing for the key, so the intended message
    was unreachable and the build ended on a bare ``KeyError`` instead.
    """
    app = test_app

    with pytest.raises(
        NeedumlException,
        match=re.escape("Option key name: nosuchkey does not exist in need SP_001."),
    ) as caught:
        app.build()

    # the guard, not a KeyError caught or wrapped after the fact: nothing is chained
    # to it, either way
    assert not isinstance(caught.value.__context__, KeyError)
    assert not isinstance(caught.value.__cause__, KeyError)


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needuml_import_string_option"}],
    indirect=True,
)
def test_needuml_jinja_func_import_string_option(test_app):
    """``import()`` of an option holding a plain string names the option.

    A string is iterable, so it used to be consumed one character at a time and each
    character looked up as a need id, reporting the first character as an unknown id.
    """
    app = test_app

    with pytest.raises(
        NeedumlException,
        match=re.escape("Option value for 'status' is not a list of need ids: 'open'."),
    ) as caught:
        app.build()

    # not the old message, which reported the string's first character as a need id
    assert "undefined need_id: 'o'" not in str(caught.value)


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needuml_jinja_warnings"}],
    indirect=True,
)
def test_needuml_jinja_func_warnings(test_app):
    """``ref()`` and ``import()`` report what they silently accepted before.

    ``ref()``'s own validation was unreachable (``(a and b) and (not a and not b)``),
    so passing both ``option`` and ``text``, or neither, went unreported; ``import()``
    ignored an option name the need does not carry.  None of them changes what is
    rendered, so all three are warnings rather than errors.

    An option that *is* defined but holds nothing (``myopt`` here, the commonest shape
    of all) must stay a silent no-op: it imports nothing, says nothing, and above all
    must not reach the new "not a list of need ids" check, which would end the build.
    """
    app = test_app
    app.build()

    assert build_warnings(app) == [
        "<srcdir>/index.rst:13: WARNING: Jinja function ref() was given both 'option' "
        "and 'text' for need_id 'SP_001'; the value of 'option' is used. "
        "[needs.needuml]",
        "<srcdir>/index.rst:13: WARNING: Jinja function ref() was given neither "
        "'option' nor 'text' for need_id 'SP_001'; the link is rendered without a "
        "label. [needs.needuml]",
        "<srcdir>/index.rst:13: WARNING: Jinja function import() is called with option "
        "name 'no_such_option', which does not exist in need SP_002. [needs.needuml]",
    ]
    # in particular: the defined-but-empty 'myopt' contributes no warning of its own
    assert not [line for line in build_warnings(app) if "'myopt'" in line]

    (needuml,) = app.env._needs_all_needumls.values()
    content = needuml["content_calculated"]
    # option wins when both are given, and the label-less link keeps its old shape
    assert "Alice -> Bob: [[../index.html#SP_001 Test spec]]" in content
    assert "Bob --> Alice: [[../index.html#SP_001]]" in content
    assert "Alice -> Bob: [[../index.html#SP_001 only text]]" in content
    # a list of ids is still imported
    assert "as SP_001 [[../index.html#SP_001]]" in content


def test_get_debug_node_from_puml_node_figure():
    """The figure branch of the ``:debug:`` block reads the figure's child.

    The branch assigned from the child and was then unconditionally overwritten by the
    figure's own (absent) ``uml`` attribute, so it could only ever produce an empty
    debug block -- a botched copy of :func:`~sphinx_needs.diagrams_common.
    get_debug_container`, which has the same code written correctly.  Nothing in the
    current pipeline wraps the plantuml node in a figure, hence the direct call.
    """
    child = nodes.Element()
    child["uml"] = "@startuml\nAlice -> Bob: <hi>\n@enduml"
    figure = nodes.figure()
    figure += child

    assert (
        "Alice -&gt; Bob: &lt;hi&gt;" in get_debug_node_from_puml_node(figure).astext()
    )


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "needumls", "srcdir": "doc_test/doc_needuml_save"}],
    indirect=True,
)
def test_needumls_builder_rerun_keeps_saved_files(test_app, make_app):
    """A second build must not truncate the ``.puml`` files the first one wrote.

    ``content_calculated`` is filled in while a document is written, after the
    environment has been pickled, so a build that re-reads nothing has an empty value
    for every needuml -- which the builder used to write over the good file, leaving
    zero bytes behind.
    """
    app = test_app

    first: list[str] = []
    for run in range(2):
        # the SECOND run is a second application over the first one's build directory,
        # not a second `app.build()`: it has to load the environment the first run
        # pickled, because that is where `content_calculated` is empty. An application
        # that never let go of its environment still holds the values its own write
        # phase put there, and would not exercise this at all
        current = (
            app
            if run == 0
            else make_app(
                buildername="needumls",
                srcdir=app.srcdir,
                builddir=Path(app.outdir).parent,
            )
        )
        current.build()

        saved = [
            Path(current.outdir, "_build", "my_needuml.puml"),
            Path(current.outdir, "_out", "sub_folder", "my_needs.puml"),
        ]
        contents = [path.read_text() for path in saved]
        assert all(content.strip() for content in contents), (
            f"a saved .puml file is empty after run {run + 1}: {contents}"
        )
        if run == 0:
            first = contents
        else:
            assert contents == first


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_needuml_save_no_plantuml",
        }
    ],
    indirect=True,
)
def test_needuml_save_without_plantuml(test_app):
    """Without PlantUML there is nothing to save, so no file is written.

    The unrendered needuml was skipped but its (empty) content was still handed to the
    builder, which wrote a zero-byte ``.puml`` file over anything already there.
    """
    app = test_app
    app.build()

    assert build_warnings(app) == [
        "<srcdir>/index.rst:4: WARNING: PlantUML is not available, so the diagram was "
        "not rendered. Install 'sphinxcontrib-plantuml' and add it to the "
        "'extensions' list to render it. [needs.needuml]"
    ]

    saved = Path(app.outdir, "my_needumls", "_out", "my_needuml.puml")
    assert not saved.exists(), f"an empty file was written to {saved}"


# --- a part address where a need is expected -------------------------------------------
#
# Where a need is expected, a part address reads as its need (design/parts-contract.md):
# ``uml()`` and ``flow()`` given ``REQ_1.p1``, and ``import()`` following a link to it,
# draw ``REQ_1`` exactly as they draw it given ``REQ_1``. An address naming a part its
# need does not have ends the build as one naming no need does, naming the address as
# written. All three ended the build on the part address itself.

PART_ADDRESS_CONF = 'extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]\n'

PART_ADDRESS = """\
Part addresses
==============

.. req:: Target
   :id: REQ_1

   The target, with :np:`(p1) the part`.

   .. needarch::

      component "arch of REQ_1"

.. req:: Drawn by flow
   :id: REQ_2

   A need with no diagram, with :np:`(p2) its part`.

.. spec:: Imports through a part link
   :id: SPEC_1
   :links: REQ_1.p1

   .. needarch::

      {{import("links")}}

.. spec:: Imports the need
   :id: SPEC_2
   :links: REQ_1

   .. needarch::

      {{import("links")}}

.. needuml::

   {{uml("REQ_1")}}

.. needuml::

   {{uml("REQ_1.p1")}}

.. needuml::

   {{flow("REQ_2")}}

.. needuml::

   {{flow("REQ_2.p2")}}
"""

PART_ADDRESS_PROJECT = {
    "buildername": "html",
    "files": [
        (Path("conf.py"), PART_ADDRESS_CONF),
        (Path("index.rst"), PART_ADDRESS),
    ],
}


def _plantuml_sources(app) -> list[str]:
    """The PlantUML source of every diagram on the resolved pages, in page order."""
    sources: list[str] = []

    def collect(app_, doctree, docname):
        sources.extend(node["uml"] for node in doctree.findall(plantuml))

    app.connect("doctree-resolved", collect, priority=900)
    return sources


@pytest.mark.parametrize(
    "test_app", [PART_ADDRESS_PROJECT], indirect=True, ids=["found"]
)
def test_needuml_a_part_address_reads_as_its_need(test_app):
    """``uml()``, ``flow()`` and the links ``import()`` follows read ``REQ_1.p1`` as
    ``REQ_1``: each diagram is the one the need's own id gives."""
    app = test_app
    sources = _plantuml_sources(app)
    app.build()
    assert_no_warnings(app)
    _arch, by_part_link, by_need_link, by_need, by_part, flow_need, flow_part = sources
    assert 'component "arch of REQ_1"' in by_need_link
    assert by_part_link == by_need_link
    assert 'component "arch of REQ_1"' in by_need
    assert by_part == by_need
    assert "as REQ_2" in flow_need
    assert flow_part == flow_need


ONCE = """\
Once
====

.. req:: Target
   :id: REQ_1

   The target, with :np:`(p1) the part`.

.. needuml::

   {{flow("REQ_1")}}
   {{flow("REQ_1.p1")}}
   {{uml("REQ_1.p1")}}
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [(Path("conf.py"), PART_ADDRESS_CONF), (Path("index.rst"), ONCE)],
        }
    ],
    indirect=True,
)
def test_needuml_a_need_and_its_part_are_drawn_once(test_app):
    """A diagram draws a need once however it is named: the need's id and a part
    address of it are one need, so the second and third calls draw nothing."""
    app = test_app
    sources = _plantuml_sources(app)
    app.build()
    assert_no_warnings(app)
    (source,) = sources
    assert source.count(" as REQ_1") == 1


UNRESOLVED = """\
Unresolved
==========

.. req:: Target
   :id: REQ_1

   The target, with :np:`(p1) the part`.

.. needuml::

   {{{{{call}("{target}")}}}}
"""


@pytest.mark.parametrize(
    "test_app,message",
    [
        pytest.param(
            {
                "buildername": "html",
                "files": [
                    (Path("conf.py"), PART_ADDRESS_CONF),
                    (Path("index.rst"), UNRESOLVED.format(call=call, target=target)),
                ],
            },
            f"Jinja function {name} is called with undefined need_id: '{target}'.",
            id=f"{call}-{outcome}",
        )
        for call, name in (("uml", "uml()"), ("flow", "flow"))
        for outcome, target in (
            ("part-missing", "REQ_1.p9"),
            ("need-missing", "NOPE_1"),
            ("part-of-a-missing-need", "NOPE_1.p1"),
        )
    ],
    indirect=["test_app"],
)
def test_needuml_an_address_that_does_not_resolve(test_app, message):
    """A part the need does not have ends the build as a need that does not exist
    does, the message naming the address as written."""
    with pytest.raises(NeedumlException, match=re.escape(message)):
        test_app.build()


IMPORT_LINK = """\
Import
======

.. req:: Target
   :id: REQ_1

   The target, with :np:`(p1) the part`.

.. spec:: Imports
   :id: SPEC_1
   :links: {link}

   .. needarch::

      {{{{import("links")}}}}
"""


@pytest.mark.parametrize(
    "test_app,link",
    [
        pytest.param(
            {
                "buildername": "html",
                "files": [
                    (Path("conf.py"), PART_ADDRESS_CONF),
                    (Path("index.rst"), IMPORT_LINK.format(link=link)),
                ],
            },
            link,
            id=name,
        )
        for name, link in (("part-missing", "REQ_1.p9"), ("need-missing", "NOPE_1"))
    ],
    indirect=["test_app"],
)
def test_needuml_import_of_a_link_that_does_not_resolve(test_app, link):
    """``import()`` of a link to a part the need does not have ends the build as one
    to a need that does not exist does, naming the link as written."""
    with pytest.raises(
        NeedumlException,
        match=re.escape(
            f"Jinja function uml() is called with undefined need_id: '{link}'."
        ),
    ):
        test_app.build()
