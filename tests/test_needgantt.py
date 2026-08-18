"""Tests for the ``needgantt`` directive."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from sphinx.util.console import strip_colors
from sphinxcontrib.plantuml import plantuml

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

    assert strip_colors(app._warning.getvalue()).strip() == ""

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

    assert strip_colors(app._warning.getvalue()).strip() == ""
    assert f"Project starts {date}" in sources[0]
