"""Tests for the :ref:`needreport` directive."""

import importlib.util
import os
import re
from pathlib import Path, PurePosixPath, PureWindowsPath

import pytest
from sphinx.util.console import strip_colors

from sphinx_needs.directives.needreport import DROPDOWN_MARKER

SPHINX_DESIGN_INSTALLED = importlib.util.find_spec("sphinx_design") is not None


def visible_text(html: str) -> str:
    """Return the page's text with its tags removed and whitespace collapsed.

    Table cells are wrapped in enough markup that asserting on a rendered
    number is unreadable otherwise.
    """
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def highlighted_block(html: str) -> str:
    """Return the page's first syntax-highlighted literal block.

    Its content is one ``<span>`` per token, so asserting on the page text does
    not work: the tags collapse to spaces and split the directive marker up.
    """
    match = re.search(r'<div class="highlight[^"]*">.*?</div>', html, re.S)
    assert match is not None, "no highlighted block on the page"
    return match.group(0)


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
# pin the wrapper, so the template loader is the only thing that can warn here
needs_render_context = {"report_directive": "admonition"}
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
    """What an absolute ``needs_report_template`` does, on each platform.

    The value is joined onto the source directory, and ``pathlib`` gives that
    join two different meanings.  A POSIX-style absolute value has its leading
    ``/`` stripped first, so it is appended and the file is looked for at a path
    nobody wrote down.  A drive-letter absolute value is not relative at all, so
    the join *replaces* the source directory with it and the file is read from
    where it points -- ``lstrip("/")`` never touches a ``D:\\...`` value either.

    So the rebase this warning explains is POSIX-only, and the two halves are
    asserted rather than one of them skipped.
    """
    app = test_app
    app.build()

    warnings = build_warnings(app)

    if os.name == "nt":
        # the configured path is used as it stands: the template is found, and
        # there is nothing to warn about
        assert warnings == []
        text = visible_text(Path(app.outdir, "index.html").read_text(encoding="utf8"))
        assert "Need Types" in text
        assert "Requirement" in text
    else:
        assert len(warnings) == 1, warnings
        assert "Could not load needs report template file" in warnings[0]
        assert (
            "needs_report_template is resolved relative to the source directory"
            in warnings[0]
        )
        assert warnings[0].endswith("[needs.needreport]")


@pytest.mark.parametrize(
    ("srcdir", "configured", "expected"),
    [
        # POSIX: the leading "/" is stripped, so the value is appended and the
        # file is looked for somewhere nobody wrote down
        ("/srcdir", "/templates/t.need", "/srcdir/templates/t.need"),
        ("/srcdir", "templates/t.need", "/srcdir/templates/t.need"),
        # Windows: a drive-letter value is not relative, so the join replaces the
        # source directory with it -- and lstrip("/") never touches it
        (r"D:\srcdir", r"D:\elsewhere\t.need", r"D:\elsewhere\t.need"),
        (r"D:\srcdir", r"templates\t.need", r"D:\srcdir\templates\t.need"),
    ],
)
def test_report_template_join_semantics(srcdir, configured, expected):
    """Pin the ``pathlib`` behaviour the resolution of the config key rests on.

    ``needreport.py`` resolves it as ``Path(srcdir) / value.lstrip("/")``, and
    what that means differs by platform: appended on POSIX, replaced on Windows.
    The test above asserts the consequence for a whole build on whichever
    platform it runs; this asserts the cause on both, everywhere.
    """
    pure = PureWindowsPath if "\\" in srcdir else PurePosixPath
    assert pure(srcdir) / configured.lstrip("/") == pure(expected)


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


# -- the fallback only fires when it changes the report ----------------------
#
# Deciding on the raw template text -- "does the file mention report_directive?"
# -- warned three shapes that build correctly today and cannot be helped by the
# substitution: a Jinja comment naming the variable, a ``{% set %}`` shadowing
# it, and the name appearing in rendered prose.  All three kept their output but
# gained a warning, which under ``sphinx-build -W`` is a red CI.  The decision is
# therefore made on the *rendered* text, and the substitution is adopted only
# when re-rendering actually removes the dropdown usage.

NO_PROVIDER_CONF = """\
extensions = ["sphinx_needs"]
needs_report_template = "/report_template.need"
"""

# Mentions the name in a Jinja comment, and hardcodes the directive it wants.
COMMENT_MENTION_TEMPLATE = """\
{# report_directive is deliberately not used here #}
.. admonition:: Need Types

   {% for type in types %}
   * {{ type.title }}
   {% endfor %}
"""

# Overrides the directive inside the template rather than in conf.py, which is
# the docs' "choose the directive yourself" advice taken by a different route.
SET_SHADOW_TEMPLATE = """\
{% set report_directive = "admonition" %}
.. {{ report_directive }}:: Need Types

   {% for type in types %}
   * {{ type.title }}
   {% endfor %}
"""

# The name survives only into rendered prose, never into a directive.
PROSE_MENTION_TEMPLATE = """\
.. admonition:: Need Types

   Set report_directive to choose how this block is rendered.

   {% for type in types %}
   * {{ type.title }}
   {% endfor %}
"""


@pytest.mark.parametrize(
    "test_app",
    [
        pytest.param(
            {
                "buildername": "html",
                "no_plantuml": True,
                "files": [
                    (Path("conf.py"), NO_PROVIDER_CONF),
                    (Path("index.rst"), REPORT_INDEX),
                    (Path("report_template.need"), template),
                ],
            },
            id=name,
        )
        for name, template in (
            ("comment-mention", COMMENT_MENTION_TEMPLATE),
            ("set-shadow", SET_SHADOW_TEMPLATE),
            ("prose-mention", PROSE_MENTION_TEMPLATE),
        )
    ],
    indirect=True,
)
def test_template_that_renders_no_dropdown_is_left_alone(test_app):
    """A report that never renders a ``dropdown`` is not warned about.

    Each of these projects builds cleanly today with no ``dropdown`` provider
    loaded, so each must keep building cleanly: a new warning here would fail a
    ``-W`` build that has nothing to fix.
    """
    app = test_app
    app.build()

    assert build_warnings(app) == []

    html = Path(app.outdir, "index.html").read_text(encoding="utf8")
    # the report is on the page, rendered by the template's own choice
    assert 'class="admonition-need-types admonition"' in html
    assert "Requirement" in visible_text(html)


HARDCODED_DROPDOWN_TEMPLATE = """\
.. dropdown:: Need Types

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
                (Path("conf.py"), NO_PROVIDER_CONF),
                (Path("index.rst"), REPORT_INDEX),
                (Path("report_template.need"), HARDCODED_DROPDOWN_TEMPLATE),
            ],
        }
    ],
    indirect=True,
)
def test_hardcoded_dropdown_template_keeps_todays_errors(test_app):
    """A template that writes ``.. dropdown::`` itself is not claimed to be fixed.

    Substituting the context variable cannot reach a literal in the template, so
    re-rendering changes nothing.  Announcing "rendered with admonition instead"
    would be false, and the warning would name no remedy the author could apply,
    so this configuration keeps exactly the diagnostics it has today.
    """
    app = test_app
    app.build()

    reported = "\n".join(build_warnings(app))
    assert 'ERROR: Unknown directive type "dropdown".' in reported
    assert "No loaded extension provides" not in reported

    html = Path(app.outdir, "index.html").read_text(encoding="utf8")
    assert "admonition-need-types" not in html


# Mentions the name, and cannot be rendered: the fallback decision must not run
# ahead of the render and announce a substitution that never happened.
UNRENDERABLE_MENTION_TEMPLATE = """\
{# report_directive #}
{% if no_such_variable|length != 0 %}
Never rendered.
{% endif %}
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "no_plantuml": True,
            "files": [
                (Path("conf.py"), NO_PROVIDER_CONF),
                (Path("index.rst"), REPORT_INDEX),
                (Path("report_template.need"), UNRENDERABLE_MENTION_TEMPLATE),
            ],
        }
    ],
    indirect=True,
)
def test_unrenderable_template_warns_only_about_the_render(test_app):
    """A template that cannot render gets one warning, about the render.

    The fallback decision is made on rendered text, so there is nothing for it
    to decide here -- and the author is not told the report was "rendered with
    admonition instead" when nothing was rendered at all.
    """
    app = test_app
    app.build()

    warnings = build_warnings(app)
    assert len(warnings) == 1, warnings
    assert "Could not render needs report template file" in warnings[0]
    assert "No loaded extension provides" not in warnings[0]


# -- the render-failure report cannot itself end the build -------------------

# ``getattr(exc, "message", exc)`` only swallows ``AttributeError``; an exception
# whose own reporting raises would escape the handler and end the build -- the
# very failure the handler exists to prevent.
NASTY_DETAIL_CONF = '''\
extensions = ["sphinx_needs"]
needs_report_template = "/report_template.need"


class NastyError(RuntimeError):
    """An exception that cannot be asked to describe itself."""

    @property
    def message(self):
        raise RuntimeError("message property exploded")


def explode():
    raise NastyError("boom")


needs_render_context = {"explode": explode}
'''

NASTY_DETAIL_TEMPLATE = "{{ explode() }}\n"


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "no_plantuml": True,
            "files": [
                (Path("conf.py"), NASTY_DETAIL_CONF),
                (Path("index.rst"), REPORT_INDEX),
                (Path("report_template.need"), NASTY_DETAIL_TEMPLATE),
            ],
        }
    ],
    indirect=True,
)
def test_render_failure_detail_that_raises_cannot_end_the_build(test_app):
    """Reporting the failure falls back to the exception's type name."""
    app = test_app
    app.build()

    warnings = build_warnings(app)
    # Sphinx separately notes that ``needs_render_context`` cannot be cached
    # because it holds a function, which has nothing to do with the directive
    reported = [warning for warning in warnings if "needs.needreport" in warning]
    assert len(reported) == 1, warnings
    assert "Could not render needs report template file" in reported[0]
    # the one thing that can still be said about it
    assert reported[0].endswith(": NastyError [needs.needreport]"), reported[0]

    # and the page is still there
    assert "<h1>Report" in Path(app.outdir, "index.html").read_text(encoding="utf8")


# -- the marker used to recognise a rendered dropdown ------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (".. dropdown:: Title", True),
        ("   .. dropdown:: Title", True),
        ("\t.. dropdown::", True),
        (".. dropdown::", True),
        # docutils allows a single space before the ``::`` marker
        (".. dropdown ::", True),
        ("Intro\n\n.. dropdown:: Title\n", True),
        # not explicit markup: docutils needs whitespace after the ``..``
        ("..dropdown:: Title", False),
        # a different directive whose name merely starts the same way
        (".. dropdowns:: Title", False),
        # docutils requires whitespace or end-of-line after ``::``; without it the
        # line is a comment, so this must not count as a usage
        (".. dropdown::x", False),
        # not at the start of a line
        ("see the .. dropdown:: directive", False),
        # the name in prose, and in a Jinja comment, are not directives
        ("Set report_directive to dropdown.", False),
        ("{# report_directive #}\n.. admonition:: Title", False),
        ("", False),
    ],
)
def test_dropdown_marker_matches_docutils_recognition(text, expected):
    """The marker follows docutils' own recognition of a directive.

    Tabs are tolerated where docutils writes a space, because docutils expands
    them before the line is ever matched.  What the marker cannot know is RST
    block context: example markup inside a literal block matches too, which is
    the documented limitation recorded on ``DROPDOWN_MARKER`` and pinned by
    ``test_example_markup_in_a_literal_block_is_substituted`` below.
    """
    assert bool(DROPDOWN_MARKER.search(text)) is expected


# -- one configuration mistake, one warning ----------------------------------

MANY_REPORTS_INDEX = """\
Report
======

.. needreport::
   :types:

.. needreport::
   :links:

.. needreport::
   :usage:
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "no_plantuml": True,
            "files": [
                (Path("conf.py"), RESERVED_KEY_CONF),
                (Path("index.rst"), MANY_REPORTS_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_reserved_context_key_warns_once_per_build(test_app):
    """The reserved-key warning is a fact about ``conf.py``, so it is said once.

    It does not depend on the directive that happened to notice it, and a
    project with a report on every page would otherwise get the same line once
    per directive.
    """
    app = test_app
    app.build()

    warnings = build_warnings(app)
    assert len(warnings) == 1, warnings
    assert (
        "needs_render_context replaces the needreport context key 'types'"
        in (warnings[0])
    )


# -- the heuristic's known edge, and its safety net ---------------------------
#
# The decision is a textual scan of the rendered report, so it cannot tell a
# directive from example markup showing one.  A template that prints
# ``{{ report_directive }}`` inside a literal block -- to document the report's
# own markup, say -- therefore looks like a live usage.  These two tests pin what
# that costs: the displayed example changes, and nothing else does.

LITERAL_BLOCK_TEMPLATE = """\
.. code-block:: rst

   .. {{ report_directive }}:: Need Types
"""

# The same, plus a branch that only breaks when the fallback is being tried.
LITERAL_BLOCK_SECOND_RENDER_FAILS_TEMPLATE = """\
.. code-block:: rst

   .. {{ report_directive }}:: Need Types
{% if report_directive == "admonition" %}{{ no_such_variable|length }}{% endif %}
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "no_plantuml": True,
            "files": [
                (Path("conf.py"), NO_PROVIDER_CONF),
                (Path("index.rst"), REPORT_INDEX),
                (Path("report_template.need"), LITERAL_BLOCK_TEMPLATE),
            ],
        }
    ],
    indirect=True,
)
def test_example_markup_in_a_literal_block_is_substituted(test_app):
    """Example markup showing the directive is treated as though it used it.

    Distinguishing the two needs the parsed document rather than the rendered
    text, which is out of proportion to the problem, so this is pinned as the
    documented cost of the heuristic rather than left to be discovered.
    """
    app = test_app
    app.build()

    assert len(build_warnings(app)) == 1
    assert "No loaded extension provides" in build_warnings(app)[0]

    # the substitution reached the displayed example, which is the whole cost
    block = highlighted_block(Path(app.outdir, "index.html").read_text(encoding="utf8"))
    assert ">admonition<" in block
    assert ">dropdown<" not in block


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "no_plantuml": True,
            "files": [
                (Path("conf.py"), NO_PROVIDER_CONF),
                (Path("index.rst"), REPORT_INDEX),
                (
                    Path("report_template.need"),
                    LITERAL_BLOCK_SECOND_RENDER_FAILS_TEMPLATE,
                ),
            ],
        }
    ],
    indirect=True,
)
def test_a_failed_fallback_render_keeps_the_report(test_app):
    """A fallback render that fails costs the project nothing.

    The default render has already succeeded by then, so the report it produced
    is kept.  The failed attempt is this directive's own idea rather than
    anything the author wrote, so it is not reported either: "could not render"
    would be false of the render the page actually got.  The fallback logic can
    therefore leave a report as it was, but never lose it.
    """
    app = test_app
    app.build()

    assert build_warnings(app) == []

    # the default render is on the page, untouched
    block = highlighted_block(Path(app.outdir, "index.html").read_text(encoding="utf8"))
    assert ">dropdown<" in block
    assert ">admonition<" not in block


# The same safety net on a project that is genuinely broken today: the report
# really does use the directive, and the fallback render really does fail.
REAL_USE_SECOND_RENDER_FAILS_TEMPLATE = """\
.. {{ report_directive }}:: Need Types

   {% for type in types %}
   * {{ type.title }}
   {% endfor %}

{% if report_directive == "admonition" %}{{ no_such_variable|length }}{% endif %}
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "no_plantuml": True,
            "files": [
                (Path("conf.py"), NO_PROVIDER_CONF),
                (Path("index.rst"), REPORT_INDEX),
                (Path("report_template.need"), REAL_USE_SECOND_RENDER_FAILS_TEMPLATE),
            ],
        }
    ],
    indirect=True,
)
def test_failed_fallback_on_a_real_usage_keeps_todays_behaviour(test_app):
    """When the substitution cannot be rendered, today's diagnostics stand.

    Nothing is claimed to have been fixed, and no "could not render" is reported
    for a render that succeeded; the project keeps exactly the docutils error it
    has always had for an unprovided ``dropdown``.
    """
    app = test_app
    app.build()

    reported = "\n".join(build_warnings(app))
    assert 'ERROR: Unknown directive type "dropdown".' in reported
    assert "No loaded extension provides" not in reported
    assert "Could not render" not in reported
