from pathlib import Path

import pytest

from sphinx_needs_testkit import assert_no_warnings, build_warnings

# WHY THE FIRST TWO TESTS OPT INTO RENDERING when their assertions look as though they do
# not need it, and why a tidy-up of the opt-in list must not remove them.
#
# Both assert `"PlantUML is not available" not in index_html` and that the build was
# silent. With the renderer inert BOTH are true of a build that drew nothing at all, so
# without `"plantuml": True` each test passes while testing nothing whatever -- measured,
# one at a time, when the opt-in list was checked for minimality. WITH it they test what
# their names claim: that sphinx-needs finds `sphinxcontrib.plantuml` however it was
# registered (in `extensions`, or by `app.setup_extension`), and that finding it produces
# a clean render. They are the only two opt-ins in this suite whose necessity is invisible
# from the assertions, and they cost about two seconds each.


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/plantuml_from_ext_list",
            "plantuml": True,
        }
    ],
    indirect=True,
)
def test_plantuml_from_ext_list(test_app):
    test_app.build()
    assert test_app.statuscode == 0
    index_html = Path(test_app.outdir, "index.html").read_text(encoding="utf8")
    assert "PlantUML is not available" not in index_html
    assert_no_warnings(test_app)


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/plantuml_from_app_extension",
            "plantuml": True,
        }
    ],
    indirect=True,
)
def test_plantuml_from_app_extension(test_app):
    test_app.build()
    assert test_app.statuscode == 0
    index_html = Path(test_app.outdir, "index.html").read_text(encoding="utf8")
    assert "PlantUML is not available" not in index_html
    assert_no_warnings(test_app)


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/plantuml_unconfigured"}],
    indirect=True,
)
def test_plantuml_unconfigured(test_app):
    test_app.build()
    assert test_app.statuscode == 0

    # ONE warning now, where there used to be two. The fixture injected a `plantuml`
    # confoverride into EVERY build, and this project deliberately does not load the
    # extension, so the build also collected "unknown config value 'plantuml' in
    # override, ignoring" -- a warning about the test fixture rather than about
    # sphinx-needs. Rendering is opt in now and this test does not opt in, so nothing is
    # injected and that warning is gone.
    #
    # ONE record, location and message together. The helper this replaced split the
    # stream on the substring "WARNING: ", so a located warning arrived as a bare
    # location entry followed by its message and this assertion had to say "two".
    records = build_warnings(test_app)
    assert len(records) == 1
    assert records[0].startswith("<srcdir>/index.rst:")
    # the page says so, but a build nobody reads the output of said nothing at all
    assert (
        "PlantUML is not available, so the diagram was not rendered. "
        "Install 'sphinxcontrib-plantuml' and add it to the 'extensions' list "
        "to render it." in records[0]
    )

    index_html = Path(test_app.outdir, "index.html").read_text(encoding="utf8")
    assert "PlantUML is not available" in index_html
