"""The suites of ``test-results`` and the environments of ``test-env`` are real sections (#1959).

Both directives used to build a ``nodes.section`` per suite / environment and then splice
it into a Python list with ``+=``: ``list.__iadd__`` iterates its argument, and a docutils
``Element`` iterates its CHILDREN, so the list received the title, the paragraphs and the
table, and the section around them was discarded. The enclosing section then held a second
``<title>`` per suite, rendered at ITS level with ITS permalink, no id of its own, absent
from ``.. contents::`` and the sidebar -- and inside a list item the HTML writer asserted.

Each generated section is now a child of the section the directive stands in, one level
below it, with an id. ``doc_test/sections_doc`` holds one page per shape: every
``test-env`` site has a page of its own, so a site that splices again fails its own row.
``doc_test/sections_in_list`` is the list-item shape, a project of its own because it used
to fail the whole build.
"""

import re
from pathlib import Path

import pytest
from docutils import nodes

SECTIONS_DOC = {"buildername": "html", "srcdir": "doc_test/sections_doc"}
IN_LIST_DOC = {"buildername": "html", "srcdir": "doc_test/sections_in_list"}

#: The control fragments, captured from master's HTML (`ec0b626d`) for the same pages. The
#: fix moves headings and adds ``<section>`` wrappers; the body of each suite and
#: environment is byte-identical.
MASTER_COUNTERS = "<p>Tests: 2, Failures: 1, Errors: 0, Skips: 0</p>"
MASTER_TIME = "<p>Time: 0.001</p>"
MASTER_ROW = (
    '<tr class="tr_passed row-even"><td class="tr_passed class">'
    '<p class="tr_passed">TimerTest</p></td>\n'
    '<td class="tr_passed name"><p class="tr_passed">test_Timer_increment</p></td>\n'
    '<td class="tr_passed status"><p class="tr_passed">passed</p></td>\n'
    '<td class="tr_passed reason"><p class="tr_passed">\n\n</p></td>\n'
    "</tr>"
)
MASTER_ENV_ROW = (
    '<tr class="row-even"><td><p>host</p></td>\n<td><p>user_abc</p></td>\n</tr>'
)
#: The ``:raw:`` block of ``flake8`` with ``:data: name``: ``json.dumps(..., indent=4)``.
MASTER_RAW_JSON = '{\n    "name": "flake8"\n}'


def _section(doctree: nodes.document, section_id: str) -> nodes.section:
    """The authored section with ``section_id``."""
    found = [s for s in doctree.findall(nodes.section) if section_id in s["ids"]]
    assert len(found) == 1, f"no single section with id {section_id!r}"
    return found[0]


def _child_sections(parent: nodes.Element) -> list[nodes.section]:
    return [child for child in parent.children if isinstance(child, nodes.section)]


def _title(section: nodes.section) -> str:
    assert isinstance(section[0], nodes.title)
    return section[0].astext()


def _assert_generated(parent: nodes.Element, titles: list[str]) -> list[nodes.section]:
    """``parent`` holds exactly one title -- its own, if any -- and one child section per
    title, each with one id, in order."""
    stray_titles = [c for c in parent.children[1:] if isinstance(c, nodes.title)]
    assert stray_titles == [], (
        "a generated title was spliced into the enclosing section"
    )
    generated = _child_sections(parent)
    assert [_title(s) for s in generated] == titles
    for section in generated:
        assert len(section["ids"]) == 1
    return generated


def _html(app, docname: str) -> str:
    return Path(app.outdir, f"{docname}.html").read_text(encoding="utf-8")


def _assert_heading(html: str, level: int, title: str) -> str:
    """``title`` is an ``<h{level}>`` directly inside a ``<section>`` whose id its
    permalink points to; returns that id. (Under ``.. contents::`` the title text is a
    back-link to its contents entry.)"""
    match = re.search(
        rf'<section id="([^"]+)">\s*<h{level}>(?:<a class="toc-backref"[^>]*>)?'
        rf'{re.escape(title)}(?:</a>)?<a class="headerlink" href="#\1"',
        html,
    )
    assert match, f"no <h{level}>{title} inside its own <section id>"
    return match.group(1)


@pytest.mark.parametrize("test_app", [SECTIONS_DOC], indirect=True)
def test_test_results_suites_are_sections_one_level_below(test_app):
    """A1: under a level-3 heading, every suite is a level-4 section of its own."""
    app = test_app
    app.build()

    doctree = app.env.get_doctree("results")
    enclosing = _section(doctree, "chapter-1-1-1")
    titles = ["TimerTest", "TimerCounterImplTest", "Another Test"]
    generated = _assert_generated(enclosing, titles)
    assert [s["ids"] for s in generated] == [
        ["timertest"],
        ["timercounterimpltest"],
        ["another-test"],
    ]

    html = _html(app, "results")
    _assert_heading(html, 3, "Chapter 1.1.1")
    for title in titles:
        _assert_heading(html, 4, title)

    # The sidebar / page toc: Sphinx's TocTreeCollector walks sections, so it lists them.
    toc_text = app.env.tocs["results"].astext()
    for title in titles:
        assert title in toc_text

    # A same-page `` `TimerTest`_ `` reference resolves: the section's name is the
    # normalised title, as an authored heading's is. (It stands under a heading of its own:
    # text after the directive in the same section would follow the last suite.)
    assert 'The first suite: <a class="reference internal" href="#timertest">' in html
    assert "ERROR" not in app._warning.getvalue()


@pytest.mark.parametrize(
    ("docname", "titles"),
    [
        pytest.param("env_table", ["flake8", "py35", "pylint"], id="table"),
        pytest.param("env_env", ["py35", "flake8"], id="env"),
        pytest.param("env_raw", ["flake8", "py35", "pylint"], id="raw"),
        pytest.param("env_raw_env", ["py35"], id="raw-env"),
    ],
)
@pytest.mark.parametrize("test_app", [SECTIONS_DOC], indirect=True)
def test_test_env_environments_are_sections_one_level_below(test_app, docname, titles):
    """A2: each of ``test-env``'s four forms -- one per site that used to splice."""
    app = test_app
    app.build()

    doctree = app.env.get_doctree(docname)
    _assert_generated(_section(doctree, "chapter-1-1"), titles)

    html = _html(app, docname)
    _assert_heading(html, 2, "Chapter 1.1")
    for title in titles:
        _assert_heading(html, 3, title)


@pytest.mark.parametrize("test_app", [IN_LIST_DOC], indirect=True)
def test_sections_inside_a_list_item_build(test_app):
    """A3: written inside a bullet item, both directives build; the sections sit in it.

    Before, the stray titles inside the list item made docutils' HTML writer assert
    (``AssertionError`` in ``_html_base.py``'s ``visit_title``) and the build fail.
    """
    app = test_app
    app.build()

    doctree = app.env.get_doctree("index")
    items = list(doctree.findall(nodes.list_item))
    assert len(items) == 2
    assert [_title(s) for s in _child_sections(items[0])] == ["pytest62"]
    assert [_title(s) for s in _child_sections(items[1])] == ["py35"]

    html = _html(app, "index")
    assert re.search(r'<li><p>results</p>\s*<section id="pytest62">', html)


@pytest.mark.parametrize("test_app", [SECTIONS_DOC], indirect=True)
def test_two_suites_named_alike_are_two_sections_without_a_warning(test_app):
    """A4: both sections exist with distinct ids; the duplicate is not a warning.

    docutils reports a duplicate implicit target at INFO level, so ``-W`` stays green.
    """
    app = test_app
    app.build()

    doctree = app.env.get_doctree("duplicates")
    generated = _assert_generated(
        _section(doctree, "duplicates"), ["pytest62", "pytest62"]
    )
    ids = [s["ids"][0] for s in generated]
    assert len(set(ids)) == 2
    assert ids[0] == "pytest62"
    assert "WARNING" not in app._warning.getvalue()


@pytest.mark.parametrize("test_app", [SECTIONS_DOC], indirect=True)
def test_contents_lists_the_generated_sections(test_app):
    """A5: ``.. contents::`` has one entry per generated section, linking its id."""
    app = test_app
    app.build()

    doctree = app.env.get_doctree("results")
    topic = next(doctree.findall(nodes.topic))
    refids = {ref.get("refid") for ref in topic.findall(nodes.reference)}
    generated = _child_sections(_section(doctree, "chapter-1-1-1"))
    assert len(generated) == 3
    for section in generated:
        assert section["ids"][0] in refids

    html = _html(app, "results")
    for section in generated:
        assert f'href="#{section["ids"][0]}"' in html


@pytest.mark.parametrize("test_app", [SECTIONS_DOC], indirect=True)
def test_the_section_bodies_are_unchanged(test_app):
    """A5 controls: what a suite / environment section holds is byte-identical to master.

    The counters line, the ``Time:`` line and a table row of ``test-results``, a table row
    of ``test-env`` and the JSON of a ``:raw:`` block. (The warnings ``test-env`` issues are
    pinned, unchanged, by ``test_env.py``'s warning test.)
    """
    app = test_app
    app.build()

    results = _html(app, "results")
    assert MASTER_COUNTERS in results
    assert MASTER_TIME in results
    assert MASTER_ROW in results
    assert MASTER_ENV_ROW in _html(app, "env_table")

    raw = app.env.get_doctree("env_raw")
    blocks = [b for b in raw.findall(nodes.literal_block) if b["language"] == "json"]
    assert len(blocks) == 3
    assert blocks[0].astext() == MASTER_RAW_JSON


ASL_DOC = {"buildername": "html", "srcdir": "doc_test/sections_autosectionlabel"}


@pytest.mark.parametrize("test_app", [ASL_DOC], indirect=True)
def test_autosectionlabel_labels_the_generated_sections(test_app):
    """A6: with ``autosectionlabel_prefix_document``, each page's suite is labelled under
    the page's prefix, a ``:ref:`` to one resolves, and a same-page ```Title`_`` reference
    resolves too (the section carries the title as its name). No warning."""
    app = test_app
    app.build()

    labels = app.env.get_domain("std").labels
    assert labels["one:pytest62"][:2] == ("one", "pytest62")
    assert labels["two:pytest62"][:2] == ("two", "pytest62")
    assert 'href="one.html#pytest62"' in _html(app, "index")
    assert 'href="#pytest62"' in _html(app, "one")
    assert "WARNING" not in app._warning.getvalue()


@pytest.mark.parametrize(
    "test_app",
    [{**ASL_DOC, "confoverrides": {"autosectionlabel_prefix_document": False}}],
    indirect=True,
)
def test_autosectionlabel_without_a_prefix_reports_a_suite_name_on_two_pages(test_app):
    """A6: without the prefix, one suite name on two pages is autosectionlabel's usual
    duplicate label -- a warning, as for two authored headings of one title."""
    app = test_app
    app.build()

    assert (
        "WARNING: duplicate label pytest62, other instance in"
        in app._warning.getvalue()
    )
