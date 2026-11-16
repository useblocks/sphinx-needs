"""A filter string that is not a Python expression is reported, and matches nothing.

``needextract:: nc::MISSING`` (an id the default ``needs_id_regex`` refuses, so the
argument is taken as a filter) used to abort the build with ``invalid syntax``; so did
the same string as the ``:filter:`` of every view and as the text of ``need_count``.
It is now one ``needs.filter`` warning naming the string and the error, at the
directive's location, and the build goes on. The callers that reported such a string
themselves -- ``needextend``'s filter form, ``copy(filter=…)``, ``needimport``'s
``:filter:`` -- keep their own messages.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sphinx.application import Sphinx

from sphinx_needs_testkit import build_warnings

CONF = """\
extensions = ["sphinx_needs"]
needs_flow_engine = "graphviz"
"""

PLANTUML_CONF = """\
extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]
"""

HEADER = """\
Index
=====

.. req:: One
   :id: REQ_001
   :status: open

"""
"""The caller under test starts on line 8."""


def _is_not_valid(warning: str, line: int | None, append: str = "") -> bool:
    """Whether ``warning`` is the report of ``nc::MISSING`` at ``line``.

    The stable parts are matched: the start, and the end after the interpreter's own
    text of the error.
    """
    where = f"<srcdir>/index.rst:{line}: " if line is not None else ""
    return warning.startswith(
        f"{where}WARNING: Filter 'nc::MISSING' not valid. Error: "
    ) and warning.endswith(f".{append} [needs.filter]")


CALLERS = [
    ("needextract-argument", CONF, ".. needextract:: nc::MISSING\n", 8),
    ("needextract-filter", CONF, ".. needextract::\n   :filter: nc::MISSING\n", 8),
    ("needtable", CONF, ".. needtable::\n   :filter: nc::MISSING\n", 8),
    ("needlist", CONF, ".. needlist::\n   :filter: nc::MISSING\n", 8),
    ("needflow", CONF, ".. needflow::\n   :filter: nc::MISSING\n", 8),
    ("needgantt", PLANTUML_CONF, ".. needgantt::\n   :filter: nc::MISSING\n", 8),
    ("needpie", CONF, ".. needpie:: Pie\n\n   nc::MISSING\n", 8),
    ("needbar", CONF, ".. needbar:: Bar\n\n   a\n   nc::MISSING\n", 8),
    ("need_count", CONF, "Count: :need_count:`nc::MISSING`.\n", 8),
    (
        "needpie-filter",
        CONF,
        '.. needpie:: Pie\n   :filter: nc::MISSING\n\n   status == "open"\n',
        8,
    ),
    (
        "needbar-filter",
        CONF,
        '.. needbar:: Bar\n   :filter: nc::MISSING\n\n   a\n   status == "open"\n',
        8,
    ),
]


@pytest.mark.parametrize(
    ("test_app", "line"),
    [
        pytest.param(
            {
                "buildername": "html",
                "files": [(Path("conf.py"), conf), (Path("index.rst"), HEADER + body)],
            },
            line,
            id=name,
        )
        for name, conf, body, line in CALLERS
    ],
    indirect=["test_app"],
)
def test_reported_at_the_caller(test_app: Sphinx, line: int):
    app = test_app
    app.build()

    warnings = [w for w in build_warnings(app) if "nc::MISSING" in w]
    assert len(warnings) == 1
    assert _is_not_valid(warnings[0], line), warnings[0]


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF),
                (Path("index.rst"), HEADER + ".. needextract:: nc::MISSING\n"),
            ],
        }
    ],
    indirect=True,
)
def test_needextract_of_a_missing_namespaced_id(test_app: Sphinx):
    """The build goes on, and the needextract shows no need."""
    app = test_app
    app.build()

    warnings = build_warnings(app)
    assert len(warnings) == 1
    assert _is_not_valid(warnings[0], 8), warnings[0]
    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    assert html.count('id="REQ_001"') == 1


PLANTUML_INDEX = (
    HEADER
    + """\
.. needuml::

   {% for need in filter("nc::MISSING") %}node "{{ need.id }}"
   {% endfor %}node "x"
"""
)


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), PLANTUML_CONF),
                (Path("index.rst"), PLANTUML_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_needuml_filter(test_app: Sphinx):
    app = test_app
    app.build()

    warnings = [w for w in build_warnings(app) if "nc::MISSING" in w]
    assert len(warnings) == 1
    assert _is_not_valid(warnings[0], None), warnings[0]


@pytest.mark.parametrize(
    ("test_app", "append"),
    [
        pytest.param(
            {
                "buildername": "html",
                "files": [
                    (
                        Path("conf.py"),
                        CONF + 'needs_warnings = {"w": "nc::MISSING"}\n',
                    ),
                    (Path("index.rst"), HEADER),
                ],
            },
            " (from warning filter 'w')",
            id="needs_warnings",
        ),
        pytest.param(
            {
                "buildername": "html",
                "files": [
                    (
                        Path("conf.py"),
                        CONF
                        + "needs_build_json = True\n"
                        + 'needs_builder_filter = "nc::MISSING"\n',
                    ),
                    (Path("index.rst"), HEADER),
                ],
            },
            " (from need_builder_filter)",
            id="needs_builder_filter",
        ),
    ],
    indirect=["test_app"],
)
def test_configured_filters(test_app: Sphinx, append: str):
    app = test_app
    app.build()

    warnings = [w for w in build_warnings(app) if "nc::MISSING" in w]
    assert len(warnings) == 1
    assert _is_not_valid(warnings[0], None, append), warnings[0]


SAFE_CALLERS = [
    (
        "needextend",
        CONF,
        '.. needextend:: "nc::MISSING"\n   :+tags: x\n',
        (
            "<srcdir>/index.rst:8: WARNING: Invalid filter 'nc::MISSING': ",
            " [needs.needextend]",
        ),
    ),
    (
        "copy",
        CONF + 'needs_fields = {"ref": {"nullable": True}}\n',
        '.. req:: Two\n   :id: REQ_002\n   :ref: [[copy("title", filter="nc::MISSING")]]\n',
        (
            "<srcdir>/index.rst:8: WARNING: Error while resolving dynamic values for "
            "field 'ref', of need 'REQ_002': Error while executing function 'copy': ",
            " [needs.dynamic_function]",
        ),
    ),
]


@pytest.mark.parametrize(
    ("test_app", "expected"),
    [
        pytest.param(
            {
                "buildername": "html",
                "files": [(Path("conf.py"), conf), (Path("index.rst"), HEADER + body)],
            },
            expected,
            id=name,
        )
        for name, conf, body, expected in SAFE_CALLERS
    ],
    indirect=["test_app"],
)
def test_callers_that_reported_it_keep_their_message(
    test_app: Sphinx, expected: tuple[str, str]
):
    app = test_app
    app.build()

    warnings = build_warnings(app)
    assert len(warnings) == 1
    start, end = expected
    assert warnings[0].startswith(start), warnings[0]
    assert warnings[0].endswith(end), warnings[0]
    assert "Filter 'nc::MISSING' not valid" not in warnings[0]


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (
                    Path("conf.py"),
                    CONF + 'needs_warnings = {"w": " status == \'open\'"}\n',
                ),
                (Path("index.rst"), HEADER),
            ],
        }
    ],
    indirect=True,
)
def test_a_filter_with_leading_white_space_does_not_abort(test_app: Sphinx):
    """A configured filter may keep leading white space; the build goes on.

    What it is reported as is not pinned: whether such a string is read past, as
    ``eval`` reads it, is not decided here.
    """
    app = test_app
    app.build()


def test_an_error_of_a_filter_that_is_python_propagates(monkeypatch):
    """Only a string that is no Python expression is reported by the guard: an error
    the delegate raises for one that is, is not swallowed."""
    from sphinx_needs import filter_common

    def failing(*args, **kwargs):
        raise ValueError("raised by the delegate")

    monkeypatch.setattr(filter_common, "filter_needs_and_parts", failing)
    monkeypatch.setattr(filter_common, "filter_needs", failing)
    python = "status == 'open' or len(tags) > 1"
    with pytest.raises(ValueError, match="raised by the delegate"):
        filter_common.filter_needs_parts([], None, python)
    with pytest.raises(ValueError, match="raised by the delegate"):
        filter_common.filter_needs_view({}, None, python)
