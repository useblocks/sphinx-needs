"""Tests for the :ref:`needreport` directive."""

import os
from pathlib import Path

import pytest
from sphinx.util.console import strip_colors


def build_warnings(app) -> list[str]:
    """Return the warnings of a finished build, one per line.

    The source directory is randomised per test run, so it is collapsed to
    ``<srcdir>/`` to keep the expected strings readable and stable.
    """
    return (
        strip_colors(app._warning.getvalue())
        .replace(str(app.srcdir) + os.path.sep, "<srcdir>/")
        .strip()
    ).splitlines()


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needreport", "no_plantuml": True}],
    indirect=True,
)
def test_doc_needreport(test_app):
    app = test_app
    app.build()
    # check for warning about missing options
    warnings = build_warnings(app)
    assert warnings == [
        "<srcdir>/index.rst:6: WARNING: No options specified to generate need report [needs.needreport]",
        "<srcdir>/index.rst:8: WARNING: Could not load needs report template file <srcdir>/unknown.rst [needs.needreport]",
    ]

    html = Path(app.outdir, "index.html").read_text(encoding="utf8")
    assert "Need Types" in html
    assert "Need Links" in html
    assert "Need Fields" in html
    assert "Need Metrics" in html


# -- render failures --------------------------------------------------------
#
# A template that cannot be rendered used to escape ``run()`` as a
# ``minijinja.TemplateError`` and end the whole build, which is precisely what
# :pr:`1105` set out to stop ("Change errors in the directive to emit warnings,
# rather than excepting the whole build").  The missing-file path got that
# treatment; the render path did not.

REPORT_INDEX = """\
Report
======

.. needreport::
   :types:
"""

RENDER_FAIL_CONF = """\
extensions = ["sphinx_needs"]
needs_report_template = "/report_template.need"
"""

# ``{% for %}`` is never closed
SYNTAX_ERROR_TEMPLATE = """\
{% for type in types %}
* {{ type.title }}
"""

# MiniJinja tolerates an undefined value printed on its own, but not one passed
# through a filter -- and this is exactly what the stale template in the docs
# did with its non-existent ``fields`` variable.
UNDEFINED_FILTER_TEMPLATE = """\
{% if no_such_variable|length != 0 %}
Never rendered.
{% endif %}
"""


@pytest.mark.parametrize(
    ("test_app", "expected_detail"),
    [
        pytest.param(
            {
                "buildername": "html",
                "no_plantuml": True,
                "files": [
                    (Path("conf.py"), RENDER_FAIL_CONF),
                    (Path("index.rst"), REPORT_INDEX),
                    (Path("report_template.need"), SYNTAX_ERROR_TEMPLATE),
                ],
            },
            "syntax error: unexpected end of input",
            id="syntax-error",
        ),
        pytest.param(
            {
                "buildername": "html",
                "no_plantuml": True,
                "files": [
                    (Path("conf.py"), RENDER_FAIL_CONF),
                    (Path("index.rst"), REPORT_INDEX),
                    (Path("report_template.need"), UNDEFINED_FILTER_TEMPLATE),
                ],
            },
            "cannot calculate length of value of type undefined",
            id="undefined-through-filter",
        ),
    ],
    indirect=["test_app"],
)
def test_render_failure_warns_and_build_survives(test_app, expected_detail):
    """A template that cannot be rendered warns, like a template that is missing."""
    app = test_app
    app.build()

    warnings = build_warnings(app)
    assert len(warnings) == 1, warnings
    assert warnings[0].startswith(
        "<srcdir>/index.rst:4: WARNING: Could not render needs report template file "
        "<srcdir>/report_template.need: "
    ), warnings[0]
    # the engine's own explanation is carried through, so the author can act on it
    assert expected_detail in warnings[0]
    assert warnings[0].endswith("[needs.needreport]")

    # the build still produced its page, and the directive contributed nothing to it
    html = Path(app.outdir, "index.html").read_text(encoding="utf8")
    assert "<h1>Report" in html
    assert "Never rendered." not in html


# -- reserved context keys --------------------------------------------------

RESERVED_KEY_CONF = """\
extensions = ["sphinx_needs"]
needs_render_context = {
    "report_directive": "admonition",
    "types": [
        {
            "directive": "injected",
            "title": "Injected By Context",
            "prefix": "I_",
            "style": "node",
        }
    ],
}
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "no_plantuml": True,
            "files": [
                (Path("conf.py"), RESERVED_KEY_CONF),
                (Path("index.rst"), REPORT_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_reserved_context_key_warns_but_still_overrides(test_app):
    """A reserved key taken over by ``needs_render_context`` warns, and still wins.

    The warning is new; the override is not.  Silently replacing ``types`` with
    whatever the configuration happens to hold has produced convincing nonsense
    for years, but changing who wins would break the projects relying on it, so
    this only makes the swap visible.
    """
    app = test_app
    app.build()

    warnings = build_warnings(app)
    assert warnings == [
        "<srcdir>/index.rst:4: WARNING: needs_render_context replaces the needreport "
        "context key 'types'; only 'report_directive' is meant to be set this way "
        "[needs.needreport]"
    ]

    # today's behaviour, unchanged: the configured value is what gets rendered
    html = Path(app.outdir, "index.html").read_text(encoding="utf8")
    assert "Injected By Context" in html
    assert "Requirement" not in html


# ``report_directive`` is the documented override and must stay silent.  That is
# asserted by ``test_doc_needreport`` above: its project sets exactly that key,
# and its warning list is compared for equality, so a warning here would fail it.


# -- an absolute needs_report_template --------------------------------------

# ``needs_report_template`` is always resolved against the source directory, so
# a path that is absolute on the file system is stripped and rebased under it,
# and the resulting "not found" names a path the author never wrote down.
ABS_TEMPLATE_CONF = """\
import pathlib

extensions = ["sphinx_needs"]
needs_report_template = str(pathlib.Path(__file__).parent / "report_template.need")
"""

TYPES_TEMPLATE = """\
.. {{ report_directive }}:: Need Types

   {% for type in types %}
   * {{ type.title }}
   {% endfor %}
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "no_plantuml": True,
            "files": [
                (Path("conf.py"), ABS_TEMPLATE_CONF),
                (Path("index.rst"), REPORT_INDEX),
                (Path("report_template.need"), TYPES_TEMPLATE),
            ],
        }
    ],
    indirect=True,
)
def test_absolute_report_template_explains_the_rebase(test_app):
    """The nonsense path in the warning is explained rather than left bare."""
    app = test_app
    app.build()

    warnings = build_warnings(app)
    assert len(warnings) == 1, warnings
    assert "Could not load needs report template file" in warnings[0]
    assert (
        "needs_report_template is resolved relative to the source directory"
        in warnings[0]
    )
    assert warnings[0].endswith("[needs.needreport]")
