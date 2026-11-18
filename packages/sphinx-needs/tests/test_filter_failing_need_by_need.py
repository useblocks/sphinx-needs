"""A filter that fails where it is tested need by need is reported, and matches nothing.

needflow's ``:highlight:``, needgantt's ``:milestone_filter:``, needsequence's
``:filter:`` and a :ref:`needs_constraints` check test their filter on one need at a
time. A filter failing there -- one that is not Python, one naming a field no need has,
one raising while it is evaluated -- ended the build with a traceback (#2252), where a
view's ``:filter:`` reports it. It is now reported as a view reports it: one
``needs.filter`` warning per place however many needs it fails on, at the directive,
and it matches no need it fails on; a constraint check is reported once, naming the
constraint, the check and the first need it fails on, and is not evaluated on a need
it fails on. A filter answers every need it does not fail on, and a filter that works
selects what it selected.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sphinx.application import Sphinx
from sphinxcontrib.plantuml import plantuml

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
    """The PlantUML source of every diagram on the resolved pages, as it is drawn.

    Every diagram here is PlantUML (needflow's default engine) and is read from the
    resolved page, so no renderer is needed."""
    sources: list[str] = []

    def collect(app_, doctree, docname):
        for node in doctree.findall(plantuml):
            sources.append(node["uml"])

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
            assert f" as {need_id} " in sources[0]
        assert "line:FF0000" not in sources[0]
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
        reports[0],
        text,
        None,
        " (from constraint 'c1', check 'check_0', first on need 'CON_A')",
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


TWO_STARTS = """\
Index
=====

.. req:: A1
   :id: STA_1
   :links: MSG_1

.. req:: M1
   :id: MSG_1
   :links: REC_1

.. req:: R1
   :id: REC_1

.. req:: A2
   :id: STA_2
   :links: MSG_2

.. req:: M2
   :id: MSG_2
   :links: REC_2

.. req:: R2
   :id: REC_2

.. needsequence::
   :start: STA_1, STA_2
   :filter: ab == 1
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [(Path("conf.py"), CONF), (Path("index.rst"), TWO_STARTS)],
        }
    ],
    indirect=True,
)
def test_a_needsequence_with_two_start_needs_reports_it_once(test_app: Sphinx):
    """The place is the directive, not each walk from one of its start needs."""
    app = test_app
    app.build()

    warnings = build_warnings(app)
    assert len(warnings) == 1, warnings
    assert _is_reported(warnings[0], "ab == 1", 26), warnings[0]


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            ".. req:: A\n   :id: CON_A\n   :constraints: c1, c2\n",
            CONF + "needs_constraints = {"
            "'c1': {'check_0': 'ab == 1', 'severity': 'LOW'}, "
            "'c2': {'check_0': 'ab == 1', 'severity': 'LOW'}"
            "}\n"
            "needs_constraint_failed_options = {'LOW': {'on_fail': ['warn']}}\n",
        )
    ],
    indirect=True,
)
def test_each_constraint_check_is_reported(test_app: Sphinx):
    """Two checks written alike are two places: each is reported, by its name."""
    app = test_app
    app.build()

    warnings = build_warnings(app)
    assert len(warnings) == 2, warnings
    assert _is_reported(
        warnings[0],
        "ab == 1",
        None,
        " (from constraint 'c1', check 'check_0', first on need 'CON_A')",
    ), warnings[0]
    assert _is_reported(
        warnings[1],
        "ab == 1",
        None,
        " (from constraint 'c2', check 'check_0', first on need 'CON_A')",
    ), warnings[1]


# --- a filter failing on some needs answers the others -------------------------------

SOME = "int(status) > 1"
"""Fails on a need whose status is no number (``open``), and answers the others."""

SOME_NEEDS = """\
Index
=====

.. req:: N1
   :id: SOME_1
   :status: open
   :duration: 1
   {extra}

.. req:: N2
   :id: SOME_2
   :status: 0
   :duration: 1
   {extra}

.. req:: N3
   :id: SOME_3
   :status: 2
   :duration: 1
   :links: SOME_2
   {extra}

"""
"""Three needs, tested in this order: the filter fails on the first, is false on the
second and true on the third; a directive after them starts on line 23."""

SOME_SEQUENCE = """\
Index
=====

.. req:: S
   :id: SOME_S
   :links: SOME_M

.. spec:: M
   :id: SOME_M
   :links: SOME_1, SOME_2, SOME_3

.. req:: R1
   :id: SOME_1
   :status: open

.. req:: R2
   :id: SOME_2
   :status: 0

.. req:: R3
   :id: SOME_3
   :status: 2

.. needsequence::
   :start: SOME_S
   :filter: int(status) > 1
"""
"""A message to three receivers, tested in this order; the directive is on line 24."""


def _index(index: str, conf: str = CONF) -> dict[str, object]:
    return {
        "buildername": "html",
        "files": [(Path("conf.py"), conf), (Path("index.rst"), index)],
    }


def _some(directive: str) -> dict[str, object]:
    return _index(SOME_NEEDS.format(extra="") + directive)


@pytest.mark.parametrize(
    ("test_app", "place", "line"),
    [
        pytest.param(
            _some(f".. needflow::\n   :highlight: {SOME}\n"),
            "needflow-highlight",
            23,
            id="needflow-highlight",
        ),
        pytest.param(
            _some(
                ".. needgantt::\n   :starts_after_links: links\n"
                f"   :milestone_filter: {SOME}\n"
            ),
            "needgantt-milestone_filter",
            23,
            id="needgantt-milestone_filter",
        ),
        pytest.param(
            _index(SOME_SEQUENCE), "needsequence-filter", 24, id="needsequence-filter"
        ),
    ],
    indirect=["test_app"],
)
def test_a_directive_answers_the_needs_its_filter_does_not_fail_on(
    test_app: Sphinx, place: str, line: int
):
    """The filter fails on the FIRST need it is tested on: it is reported once, and
    a later need it is true on is matched."""
    app = test_app
    sources = _capture(app)
    app.build()

    warnings = build_warnings(app)
    assert len(warnings) == 1, warnings
    assert _is_reported(warnings[0], SOME, line), warnings[0]

    assert len(sources) == 1
    lines = sources[0].splitlines()
    if place == "needflow-highlight":
        highlighted = [ln for ln in lines if "line:FF0000" in ln]
        assert len(highlighted) == 1, highlighted
        assert " as SOME_3 " in highlighted[0]
    elif place == "needgantt-milestone_filter":
        assert [ln for ln in lines if " lasts " in ln] == [
            "[N1] as [SOME_1] lasts 1 days",
            "[N2] as [SOME_2] lasts 1 days",
            "[N3] as [SOME_3] lasts 0 days",
        ]
        assert [ln for ln in lines if " at [" in ln] == [
            "[SOME_3] happens at [SOME_2]'s end"
        ]
    else:
        assert [ln for ln in lines if " -> " in ln] == ["SOME_S -> SOME_3: M"]


@pytest.mark.parametrize(
    "test_app",
    [
        _index(
            SOME_NEEDS.format(extra=":constraints: c1"),
            CONF + "needs_constraints = {'c1': {"
            f"'check_0': {SOME!r}, 'severity': 'LOW'"
            "}}\n"
            "needs_constraint_failed_options = {'LOW': {'on_fail': ['warn']}}\n",
        )
    ],
    indirect=True,
)
def test_a_constraint_check_is_evaluated_on_the_needs_it_does_not_fail_on(
    test_app: Sphinx,
):
    """The check fails on the FIRST need it is tested on, which its report names; it
    is evaluated on the later needs, false on one and true on the other."""
    app = test_app
    app.build()

    warnings = build_warnings(app)
    reports = [w for w in warnings if "[needs.filter]" in w]
    assert len(reports) == 1, warnings
    assert _is_reported(
        reports[0],
        SOME,
        None,
        " (from constraint 'c1', check 'check_0', first on need 'SOME_1')",
    ), reports[0]
    assert [w for w in warnings if w not in reports] == [
        f"<srcdir>/index.rst:10: WARNING: Constraint {SOME} for need SOME_2 "
        "FAILED! severity: LOW None [needs.constraint]"
    ]

    needs = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    stored = needs["versions"][""]["needs"]
    assert stored["SOME_1"]["constraints_results"] == {"c1": {}}
    assert stored["SOME_2"]["constraints_results"] == {"c1": {"check_0": False}}
    assert stored["SOME_2"]["constraints_passed"] is False
    assert stored["SOME_3"]["constraints_results"] == {"c1": {"check_0": True}}
    assert stored["SOME_3"]["constraints_passed"] is True


@pytest.mark.parametrize(
    "test_app",
    [
        _index(
            """\
Index
=====

.. req:: A
   :id: FIRST_A
   :status: 2
   :constraints: c1

.. req:: B
   :id: FIRST_B
   :status: open
   :constraints: c1
""",
            CONF + "needs_constraints = {'c1': {"
            f"'check_0': {SOME!r}, 'severity': 'LOW'"
            "}}\n"
            "needs_constraint_failed_options = {'LOW': {'on_fail': ['warn']}}\n",
        )
    ],
    indirect=True,
)
def test_a_constraint_report_names_the_first_need_the_check_fails_on(
    test_app: Sphinx,
):
    """The check passes on the first need it is tested on and fails on the second: the
    report names the second, where it failed, not the first."""
    app = test_app
    app.build()

    warnings = build_warnings(app)
    assert len(warnings) == 1, warnings
    assert _is_reported(
        warnings[0],
        SOME,
        None,
        " (from constraint 'c1', check 'check_0', first on need 'FIRST_B')",
    ), warnings[0]


# --- a filter that works acts where it acted ------------------------------------------


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF),
                (
                    Path("index.rst"),
                    "Index\n=====\n\n.. toctree::\n\n   other\n\n"
                    ".. req:: A\n   :id: DOC_A\n   :links: DOC_B\n\n"
                    ".. needflow::\n   :highlight: c.this_doc()\n",
                ),
                (Path("other.rst"), "Other\n=====\n\n.. req:: B\n   :id: DOC_B\n"),
            ],
        }
    ],
    indirect=True,
)
def test_a_needflow_highlight_tests_the_need_against_its_document(test_app: Sphinx):
    """``c.this_doc()`` in ``:highlight:`` is the needflow's document: its need is
    highlighted, the need of the other document is not, and nothing is reported."""
    app = test_app
    sources = _capture(app)
    app.build()

    assert build_warnings(app) == []
    assert len(sources) == 1
    drawn = {
        need_id: ln
        for ln in sources[0].splitlines()
        for need_id in ("DOC_A", "DOC_B")
        if f" as {need_id} " in ln
    }
    assert "line:FF0000" in drawn["DOC_A"]
    assert "line:FF0000" not in drawn["DOC_B"]


@pytest.mark.parametrize(
    "test_app",
    [
        _index(
            """\
Index
=====

.. req:: A
   :id: DEEP_A
   :status: open
   :links: DEEP_M1

.. spec:: M1
   :id: DEEP_M1
   :links: DEEP_B

.. req:: B
   :id: DEEP_B
   :status: open
   :links: DEEP_M2

.. spec:: M2
   :id: DEEP_M2
   :links: DEEP_C

.. req:: C
   :id: DEEP_C
   :status: closed

.. needsequence::
   :start: DEEP_A
   :filter: status == "open"
"""
        )
    ],
    indirect=True,
)
def test_a_needsequence_filter_acts_down_the_walk(test_app: Sphinx):
    """The filter is tested on the receivers of the receivers too: a receiver two
    messages away that it excludes is not drawn."""
    app = test_app
    sources = _capture(app)
    app.build()

    assert build_warnings(app) == []
    assert len(sources) == 1
    assert [ln for ln in sources[0].splitlines() if " -> " in ln] == [
        "DEEP_A -> DEEP_B: M1"
    ]


@pytest.mark.parametrize(
    "test_app",
    [
        _index(
            """\
Index
=====

.. req:: Task
   :id: GNT_T
   :duration: 2

.. req:: Milestone
   :id: GNT_M
   :status: done
   :links: GNT_T

.. needgantt::
   :starts_after_links: links
   :milestone_filter: status == "done"
"""
        )
    ],
    indirect=True,
)
def test_a_needgantt_milestone_happens_at_its_links(test_app: Sphinx):
    """A milestone's constraint reads ``happens at``, where a task's reads ``starts
    at``: the milestone filter is tested in the constraints too."""
    app = test_app
    sources = _capture(app)
    app.build()

    assert build_warnings(app) == []
    assert len(sources) == 1
    lines = sources[0].splitlines()
    assert "[Milestone] as [GNT_M] lasts 0 days" in lines
    assert [ln for ln in lines if " at [" in ln] == ["[GNT_M] happens at [GNT_T]'s end"]
