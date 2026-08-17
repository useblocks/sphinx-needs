"""Tests for the :ref:`needreport` directive."""

import importlib.util
import os
import re
from pathlib import Path

import pytest
from sphinx.util.console import strip_colors

SPHINX_DESIGN_INSTALLED = importlib.util.find_spec("sphinx_design") is not None


def visible_text(html: str) -> str:
    """Return the page's text with its tags removed and whitespace collapsed.

    Table cells are wrapped in enough markup that asserting on a rendered
    number is unreadable otherwise.
    """
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


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


# -- the dropdown prerequisite (issue #899) ---------------------------------
#
# The packaged template wraps each section in ``{{ report_directive }}``, which
# defaults to ``dropdown`` -- a directive neither Sphinx nor this extension
# provides.  Without a provider every section used to fail to parse, and because
# Sphinx strips ``system_message`` nodes the report vanished from the page
# entirely: four ERRORs on the console, an empty section in the HTML, exit 0.


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_needreport_no_dropdown",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_no_dropdown_provider_falls_back_to_admonition(test_app):
    """With nothing providing ``dropdown``, the report renders as admonitions."""
    app = test_app
    app.build()

    # one actionable warning naming both remedies, at the directive's own line,
    # in place of four "Unknown directive type" errors at invented line numbers
    assert build_warnings(app) == [
        "<srcdir>/index.rst:15: WARNING: No loaded extension provides a 'dropdown' "
        "directive, so the needs report is rendered with 'admonition' instead. "
        "Load an extension that provides it, for example sphinx-design, or choose "
        "the directive yourself with needs_render_context = "
        "{'report_directive': ...} [needs.needreport]"
    ]

    html = Path(app.outdir, "index.html").read_text(encoding="utf8")
    text = visible_text(html)

    # all four sections are on the page, each as an admonition
    for section in ("need-types", "need-links", "need-fields", "need-metrics"):
        assert f'class="admonition-{section} admonition"' in html

    # and they carry their content, not just their titles
    assert "Requirement req R_ node" in text
    assert "Specification spec S_ node" in text
    assert "Blocks Is blocked by Blocks" in text
    assert "priority" in text

    # the counts come from the :need_count: roles the template emits, so they are
    # resolved project-wide: 2 local reqs + 1 need part + 2 external reqs
    assert "Req 5" in text
    assert "Spec 1" in text
    assert "Total Needs Amount 6" in text


# A stand-in for the ``dropdown`` an extension such as sphinx-design registers.
# The fallback tests whether the *name* resolves, so any provider will do -- and
# this one keeps the check covered wherever sphinx-design is not installed.
STUB_DROPDOWN_CONF = '''\
from docutils import nodes
from docutils.parsers.rst import directives
from sphinx.util.docutils import SphinxDirective

extensions = ["sphinx_needs"]


class StubDropdown(SphinxDirective):
    """Stand in for the dropdown directive that sphinx-design provides."""

    optional_arguments = 1
    final_argument_whitespace = True
    has_content = True
    option_spec = {"class": directives.class_option}

    def run(self):
        container = nodes.container(classes=["stub-dropdown"])
        if self.arguments:
            container += nodes.paragraph(text=self.arguments[0])
        self.state.nested_parse(self.content, self.content_offset, container)
        return [container]


def setup(app):
    app.add_directive("dropdown", StubDropdown)
'''


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "no_plantuml": True,
            "files": [
                (Path("conf.py"), STUB_DROPDOWN_CONF),
                (Path("index.rst"), REPORT_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_dropdown_provider_is_left_alone(test_app):
    """A registered ``dropdown`` is used as before, with nothing warned about."""
    app = test_app
    app.build()

    assert build_warnings(app) == []

    html = Path(app.outdir, "index.html").read_text(encoding="utf8")
    # the dropdown path was taken: the provider rendered the section, and no
    # admonition was substituted for it
    assert '<div class="stub-dropdown' in html
    assert "Need Types" in visible_text(html)
    assert "admonition-need-types" not in html


@pytest.mark.skipif(
    not SPHINX_DESIGN_INSTALLED, reason="sphinx-design is not installed"
)
@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "no_plantuml": True,
            "files": [
                (
                    Path("conf.py"),
                    'extensions = ["sphinx_needs", "sphinx_design"]\n',
                ),
                (Path("index.rst"), REPORT_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_sphinx_design_dropdown_output_is_unchanged(test_app):
    """The real provider still produces its own markup, and warns about nothing."""
    app = test_app
    app.build()

    assert build_warnings(app) == []

    html = Path(app.outdir, "index.html").read_text(encoding="utf8")
    assert "sd-dropdown" in html
    assert "<details" in html
    assert "admonition-need-types" not in html


EXPLICIT_DROPDOWN_CONF = """\
extensions = ["sphinx_needs"]
needs_render_context = {"report_directive": "dropdown"}
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "no_plantuml": True,
            "files": [
                (Path("conf.py"), EXPLICIT_DROPDOWN_CONF),
                (Path("index.rst"), REPORT_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_explicitly_configured_dropdown_is_never_substituted(test_app):
    """An explicit ``report_directive`` is honoured, unavailable or not.

    Asking for ``dropdown`` by name and getting an admonition would be a worse
    surprise than the error, so this configuration keeps failing exactly as it
    always has.
    """
    app = test_app
    app.build()

    # docutils quotes the whole offending block back, so this spans many lines
    reported = "\n".join(build_warnings(app))
    assert 'ERROR: Unknown directive type "dropdown".' in reported
    assert "No loaded extension provides" not in reported

    # and the section is dropped from the page, exactly as it is today
    html = Path(app.outdir, "index.html").read_text(encoding="utf8")
    assert "admonition-need-types" not in html
    assert "Need Types" not in html


# -- needs_report_template, the success path --------------------------------

CUSTOM_TEMPLATE_CONF = """\
extensions = ["sphinx_needs"]
needs_report_template = "/report_templates/types.need"
"""

CUSTOM_TEMPLATE = """\
The project defines {{ types|length }} need types:

{% for type in types %}
* {{ type.title }} (``{{ type.directive }}``)
{% endfor %}
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "no_plantuml": True,
            "files": [
                (Path("conf.py"), CUSTOM_TEMPLATE_CONF),
                (Path("index.rst"), REPORT_INDEX),
                (Path("report_templates/types.need"), CUSTOM_TEMPLATE),
            ],
        }
    ],
    indirect=True,
)
def test_needs_report_template_renders(test_app):
    """A configured template is found under the source directory and rendered.

    ``needs_report_template`` had no passing test at all: it was only ever
    exercised through the ``:template:`` option, and only in its failing form.
    """
    app = test_app
    app.build()

    assert build_warnings(app) == []

    text = visible_text(Path(app.outdir, "index.html").read_text(encoding="utf8"))
    # the leading "/" of the configured path is stripped, not treated as the
    # file system root, so the template is found relative to the source directory
    assert "The project defines 8 need types:" in text
    assert "Requirement" in text
    assert "Specification" in text
