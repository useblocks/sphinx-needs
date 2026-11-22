"""Tests for the ``needgantt`` directive."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from lxml import etree
from lxml import html as html_parser
from sphinxcontrib.plantuml import plantuml

from sphinx_needs_testkit import assert_no_warnings, build_warnings

#: A ``conf.py`` for the inline source projects below.
#: ``needgantt`` requires both of its value options to be numeric fields.
CONF_PY = """\
extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]
needs_types = [
    {
        "directive": "story",
        "title": "User Story",
        "prefix": "US_",
        "color": "#BFD8D2",
        "style": "node",
    },
]
needs_fields = {
    "duration": {"schema": {"type": "integer"}, "nullable": True},
    "completion": {"schema": {"type": "integer"}, "nullable": True},
}
"""

#: A chart exercising every statement kind the directive emits:
#: a declaration, a completion value, a type colour, a milestone and a constraint.
CHART = """\
Gantt chart
===========

.. story:: Find and report bug
   :id: TASK_A
   :duration: 3
   :completion: 80

.. story:: Analyse bug
   :id: TASK_B
   :duration: 2
   :links: TASK_A

.. story:: Solution ticket closed
   :id: TASK_C
   :duration: 1
   :links: TASK_B

.. needgantt:: Chart
   :starts_after_links: links
   :milestone_filter: id == "TASK_C"
   :start_date: 2020-03-25
"""

#: The same project with a ``number``-typed completion field, i.e. one whose values arrive
#: as floats. This is what the sphinx-needs documentation itself uses (its ``amount`` field
#: is ``schema.type = "number"``, and ``needgantt``'s ``completion_option`` example points at
#: it), and what made the four-year-old vendored PlantUML the only renderer this project's
#: own docs would build with.
CONF_PY_FLOAT_COMPLETION = CONF_PY.replace(
    '"completion": {"schema": {"type": "integer"}',
    '"completion": {"schema": {"type": "number"}',
)

#: One task, one completion value, nothing else to go wrong.
FLOAT_COMPLETION_CHART = """\
Gantt chart
===========

.. story:: Find and report bug
   :id: TASK_A
   :duration: 3
   :completion: 90

.. needgantt:: Chart
"""

#: A declaration, i.e. ``[<title>] as [<id>] lasts <n> days``.
_DECLARATION = re.compile(r"^\[(?P<title>.*)\] as \[(?P<id>[^\]]*)\] lasts ")

#: Any bracketed task reference.
_REFERENCE = re.compile(r"\[([^\]]*)\]")


def _capture_diagrams(app) -> list[str]:
    """Collect the PlantUML source of every diagram the build generates.

    The generated source is asserted on rather than the rendered image, so that the
    assertions describe what the directive decided to draw and do not depend on the
    PlantUML binary being able to draw it.

    :param app: The (not yet built) Sphinx application.
    :return: A list that is filled with one source per diagram, as the build runs.
    """
    sources: list[str] = []

    def collect(app_, doctree, docname):
        for node in doctree.findall(plantuml):
            sources.append(node["uml"])

    app.connect("doctree-resolved", collect, priority=900)
    return sources


def _statements(uml: str) -> list[str]:
    """The meaningful statements of a generated chart, i.e. without comments."""
    return [
        stripped
        for line in uml.splitlines()
        if (stripped := line.strip()) and not stripped.startswith("'")
    ]


def _declarations(uml: str) -> dict[str, str]:
    """The tasks a generated chart declares, as ``{alias: title}``."""
    return {
        match["id"]: match["title"]
        for line in _statements(uml)
        if (match := _DECLARATION.match(line))
    }


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [(Path("conf.py"), CONF_PY), (Path("index.rst"), CHART)],
        }
    ],
    indirect=True,
)
def test_tasks_are_addressed_by_id(test_app):
    """Every statement must address a task that was actually declared.

    Tasks are declared as ``[<title>] as [<id>]``, which binds later ``[...]``
    references to the *alias*. PlantUML does not reject an unbound reference: it
    silently declares a new, zero length task of that name. So a completion or colour
    line addressing a task by its title used to draw a second, phantom bar for every
    need that had a type colour or a completion value -- which, since types carry a
    colour by default, is every need in almost every chart.
    """
    app = test_app
    sources = _capture_diagrams(app)
    app.build()

    assert_no_warnings(app)

    assert len(sources) == 1
    uml = sources[0]

    declared = _declarations(uml)
    assert declared == {
        "TASK_A": "Find and report bug",
        "TASK_B": "Analyse bug",
        "TASK_C": "Solution ticket closed",
    }

    # no statement may reference a task that is not one of the declared aliases,
    # as any such reference silently becomes an extra bar in the rendered chart
    for statement in _statements(uml):
        if _DECLARATION.match(statement):
            continue
        for reference in _REFERENCE.findall(statement):
            assert reference in declared, (
                f"undeclared task {reference!r} referenced by {statement!r}"
            )

    # and, explicitly, the two accumulators that used to address tasks by title
    assert "[TASK_A] is 80% completed" in uml
    assert "[TASK_A] is colored in #BFD8D2" in uml


@pytest.mark.parametrize(
    "test_app,date",
    [
        (
            {
                "buildername": "html",
                "files": [
                    (Path("conf.py"), CONF_PY),
                    (Path("index.rst"), CHART.replace("2020-03-25", date)),
                ],
            },
            date,
        )
        for date in ("2020-01-01", "2020-03-25", "2020-12-31")
    ],
    ids=["january", "march", "december"],
    indirect=["test_app"],
)
def test_start_date_is_the_given_date(test_app, date):
    """The project must start on the date the option gives, in every month.

    The date used to be re-formatted through a month name table that was indexed
    with the 1-based month number, so the chart started one month later than asked
    for, and a December date raised an ``IndexError`` that aborted the whole build.
    """
    app = test_app
    sources = _capture_diagrams(app)
    app.build()

    assert_no_warnings(app)
    assert f"Project starts {date}" in sources[0]


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF_PY_FLOAT_COMPLETION),
                (Path("index.rst"), FLOAT_COMPLETION_CHART),
            ],
        }
    ],
    indirect=True,
)
def test_a_float_completion_is_an_integer_percentage(test_app):
    """A ``number``-typed completion field must not emit ``90.0% completed``.

    PlantUML's gantt grammar takes an integer percentage. Up to 1.2022.14 it tolerated a
    fractional one; 1.2026.8 rejects the statement outright -- ``Syntax Error? (Assumed
    diagram type: gantt)`` -- so a chart whose completion field is typed ``number`` (the
    JSON-schema type that gives a float) stopped rendering altogether, and under ``-nW``
    took the build with it. The directive already rounds a float *duration* for the same
    reason; this is the other half of that.

    Asserted on the generated source rather than the rendered image, like every other case
    here, so that what is pinned is the decision the directive made.
    """
    app = test_app
    sources = _capture_diagrams(app)
    app.build()

    assert_no_warnings(app)

    uml = sources[0]
    assert "[TASK_A] is 90% completed" in uml
    assert "90.0" not in uml


#: Titles a gantt element's label must still draw: a need part's text (its ``title``) may
#: span lines, be empty or hold brackets, and so may a need's title.
CONF_PY_TITLES = (
    CONF_PY + "needs_title_optional = True\nplantuml_output_format = 'svg'\n"
)

TITLES_CHART = """\
Gantt titles
============

.. story:: Hard parts
   :id: US_H
   :duration: 3

   :np:`(ml) first line
   second line` and :np:`(em)` and :np:`(br) close ] and [open`.

.. story:: close ] and [open
   :id: US_BR
   :duration: 1

.. story:: first line
   second line
   :id: US_ML
   :duration: 1

.. story::
   :id: US_EM
   :duration: 1

   Body only.

.. story:: Find and report bug
   :id: US_OK
   :duration: 2

.. container:: part-lines

   .. needgantt:: Part lines
      :filter: id_complete == "US_H.ml"

.. container:: part-empty

   .. needgantt:: Part empty
      :filter: id_complete == "US_H.em"

.. container:: part-brackets

   .. needgantt:: Part brackets
      :filter: id_complete == "US_H.br"

.. container:: part-milestone

   .. needgantt:: Part milestone
      :filter: id_complete == "US_H.br"
      :milestone_filter: is_part

.. container:: need-brackets

   .. needgantt:: Need brackets
      :filter: id == "US_BR"

.. container:: need-lines

   .. needgantt:: Need lines
      :filter: id == "US_ML"

.. container:: need-empty

   .. needgantt:: Need empty
      :filter: id == "US_EM"

.. container:: need-ordinary

   .. needgantt:: Need ordinary
      :filter: id == "US_OK"
"""


def _drawn_texts(app, container: str) -> list[str]:
    """The texts of the chart drawn in the ``.. container::`` of class *container*."""
    page = html_parser.fromstring(
        Path(app.outdir, "index.html").read_text(encoding="utf-8")
    )
    (div,) = page.xpath(
        f'//div[contains(concat(" ", normalize-space(@class), " "), " {container} ")]'
    )
    (svg_path,) = div.xpath(".//object/@data")
    svg = etree.fromstring(Path(app.outdir, svg_path).read_bytes())
    return [
        " ".join("".join(text.itertext()).split())
        for text in svg.iter("{http://www.w3.org/2000/svg}text")
    ]


def _elements(uml: str) -> str:
    """The element definitions of a generated chart, as written."""
    return (
        uml.split("' Elements definition", 1)[1].split("' Element links", 1)[0].strip()
    )


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF_PY_TITLES),
                (Path("index.rst"), TITLES_CHART),
            ],
            "plantuml": True,
        }
    ],
    indirect=True,
)
def test_an_element_label_draws_whatever_its_title_holds(test_app):
    """A gantt element is declared ``[<label>] as [<id>]``, and PlantUML refuses the
    whole chart when the label spans lines, is empty or holds a bracket. The label is the
    title on one line, the element's id when that is empty, and each bracket written as
    a character reference, which the chart draws as the bracket itself.

    A need part's ``title`` is its text, where a line break or an empty text is ordinary,
    so a part reaches each case; a need's title reaches them too. An ordinary title is
    written as it always was.
    """
    app = test_app
    sources = _capture_diagrams(app)
    app.build()

    assert build_warnings(app) == []

    assert [_elements(uml) for uml in sources] == [
        "[first line second line] as [ml] lasts 3 days",
        "[em] as [em] lasts 3 days",
        "[close &#93; and &#91;open] as [br] lasts 3 days",
        "[close &#93; and &#91;open] as [br] lasts 0 days",
        "[close &#93; and &#91;open] as [US_BR] lasts 1 days",
        "[first line second line] as [US_ML] lasts 1 days",
        "[US_EM] as [US_EM] lasts 1 days",
        "[Find and report bug] as [US_OK] lasts 2 days",
    ]

    drawn = {
        "part-lines": "first line second line",
        "part-empty": "em",
        "part-brackets": "close ] and [open",
        "part-milestone": "close ] and [open",
        "need-brackets": "close ] and [open",
        "need-lines": "first line second line",
        "need-empty": "US_EM",
        "need-ordinary": "Find and report bug",
    }
    for container, label in drawn.items():
        assert label in _drawn_texts(app, container), container
