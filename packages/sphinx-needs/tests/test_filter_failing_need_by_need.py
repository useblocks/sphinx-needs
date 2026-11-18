"""A filter that fails where it is tested need by need is reported, and matches nothing.

needflow's ``:highlight:``, needgantt's ``:milestone_filter:``, needsequence's
``:filter:`` and a :ref:`needs_constraints` check test their filter on one need at a
time. A filter failing there -- one that is not Python, one naming a field no need has,
one raising while it is evaluated -- ended the build with a traceback (#2252), where a
view's ``:filter:`` reports it. It is now reported as a view reports it: one
``needs.filter`` warning per place however many needs it fails on, at the directive,
and it matches no need; a constraint check is reported once, naming the constraint and
the check, and is not evaluated.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sphinx.application import Sphinx
from sphinxcontrib.plantuml import plantuml

from sphinx_needs.directives.needflow._directive import NeedflowGraphiz
from sphinx_needs_testkit import build_warnings

FAILING = {
    "not-python": "nc::MISSING",
    "unknown-name": "ab == 1",
    "raises": "int('x') == 1",
}
"""The three ways a filter fails: it does not parse, it names a field no need has,
and it raises while it is evaluated."""

CONF = """\
extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]
needs_flow_engine = "graphviz"
needs_build_json = True
needs_fields = {"duration": {"schema": {"type": "integer"}, "nullable": True}}
"""

HEADER = """\
Index
=====

.. req:: S
   :id: SEQ_S
   :duration: 1
   :links: SEQ_M

.. req:: M
   :id: SEQ_M
   :duration: 1
   :links: SEQ_R, SEQ_T

.. req:: R
   :id: SEQ_R
   :duration: 1

.. req:: T
   :id: SEQ_T
   :duration: 1

"""
"""Four needs, so that every place tests its filter on more than one; the directive
under test starts on line 22."""

LINE = 22

DIRECTIVES = {
    "needflow-highlight": ".. needflow::\n   :highlight: {f}\n",
    "needgantt-milestone_filter": (
        ".. needgantt::\n   :starts_after_links: links\n   :milestone_filter: {f}\n"
    ),
    "needsequence-filter": ".. needsequence::\n   :start: SEQ_S\n   :filter: {f}\n",
}


def _project(body: str, conf: str = CONF) -> dict[str, object]:
    return {
        "buildername": "html",
        "files": [(Path("conf.py"), conf), (Path("index.rst"), HEADER + body)],
    }


def _is_reported(warning: str, text: str, line: int | None, append: str = "") -> bool:
    """Whether ``warning`` is the report of ``text`` at ``line``, as a view's
    ``:filter:`` reports it: the stable parts, around the interpreter's own text of
    the error."""
    where = f"<srcdir>/index.rst:{line}: " if line is not None else ""
    return warning.startswith(
        f"{where}WARNING: Filter {text!r} not valid. Error: "
    ) and warning.endswith(f".{append} [needs.filter]")


def _capture(app: Sphinx) -> list[str]:
    """The source of every diagram on the resolved pages, as it is drawn."""
    sources: list[str] = []

    def collect(app_, doctree, docname):
        for node in doctree.findall(plantuml):
            sources.append(node["uml"])
        for node in doctree.findall(NeedflowGraphiz):
            sources.append(node["resolved_content"])

    app.connect("doctree-resolved", collect, priority=900)
    return sources


@pytest.mark.parametrize(
    ("test_app", "place", "text"),
    [
        pytest.param(
            _project(body.replace("{f}", text)), place, text, id=f"{place}-{kind}"
        )
        for place, body in DIRECTIVES.items()
        for kind, text in FAILING.items()
    ],
    indirect=["test_app"],
)
def test_a_directive_reports_it_once_and_matches_nothing(
    test_app: Sphinx, place: str, text: str
):
    app = test_app
    sources = _capture(app)
    app.build()

    warnings = build_warnings(app)
    assert len(warnings) == 1, warnings
    assert _is_reported(warnings[0], text, LINE), warnings[0]

    if place == "needflow-highlight":
        # every need drawn, none highlighted
        assert len(sources) == 1
        for need_id in ("SEQ_S", "SEQ_M", "SEQ_R", "SEQ_T"):
            assert f'"{need_id}"' in sources[0]
        assert "color=red" not in sources[0]
    elif place == "needgantt-milestone_filter":
        # every need a task, none a milestone
        assert len(sources) == 1
        assert sources[0].count(" lasts 1 days") == 4
        assert "lasts 0 days" not in sources[0]
        assert " happens at " not in sources[0]
        assert "[SEQ_S] starts at [SEQ_M]'s end" in sources[0]
    else:
        # no receiver passes, so no message is drawn
        assert sources == []
        html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
        assert "No needs passed the filters" in html


CONSTRAINED = """\
.. req:: A
   :id: CON_A
   :status: open
   :constraints: c1

.. req:: B
   :id: CON_B
   :status: closed
   :constraints: c1
"""


def _constraint_conf(text: str) -> str:
    return CONF + (
        "needs_constraints = {'c1': {"
        f"'check_0': {text!r}, 'check_1': \"status == 'open'\", 'severity': 'LOW'"
        "}}\n"
        "needs_constraint_failed_options = {'LOW': {"
        "'on_fail': ['warn'], 'style': ['red_bar'], 'force_style': False"
        "}}\n"
    )


@pytest.mark.parametrize(
    ("test_app", "text"),
    [
        pytest.param(_project(CONSTRAINED, _constraint_conf(text)), text, id=kind)
        for kind, text in FAILING.items()
    ],
    indirect=["test_app"],
)
def test_a_constraint_check_is_reported_once_and_not_evaluated(
    test_app: Sphinx, text: str
):
    """One warning for the check, however many needs it fails on; the check neither
    passes nor fails, so it runs no ``on_fail`` action, and each need stores what it
    would have stored had the check not been declared. The other check of the same
    constraint is evaluated as before."""
    app = test_app
    app.build()

    warnings = build_warnings(app)
    reports = [w for w in warnings if "[needs.filter]" in w]
    assert len(reports) == 1, warnings
    assert _is_reported(
        reports[0], text, None, " (from constraint 'c1', check 'check_0')"
    ), reports[0]
    # the working check's own failure, on the need it fails on, and nothing else
    assert [w for w in warnings if w not in reports] == [
        "<srcdir>/index.rst:27: WARNING: Constraint status == 'open' for need CON_B "
        "FAILED! severity: LOW None [needs.constraint]"
    ]

    needs = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    stored = needs["versions"][""]["needs"]
    assert stored["CON_A"]["constraints_results"] == {"c1": {"check_1": True}}
    assert stored["CON_A"]["constraints_passed"] is True
    assert not stored["CON_A"].get("style")
    assert stored["CON_B"]["constraints_results"] == {"c1": {"check_1": False}}
    assert stored["CON_B"]["constraints_passed"] is False
    # the style the working check's failure sets, as it sets it
    assert stored["CON_B"]["style"] == "red_bar,"
