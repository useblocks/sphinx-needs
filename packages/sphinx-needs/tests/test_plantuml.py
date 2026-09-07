from pathlib import Path

import pytest


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
def test_plantuml_from_ext_list(test_app, get_warnings_list):
    test_app.build()
    assert test_app.statuscode == 0
    index_html = Path(test_app.outdir, "index.html").read_text(encoding="utf8")
    assert "PlantUML is not available" not in index_html
    warnings = get_warnings_list(test_app)
    assert len(warnings) == 0


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
def test_plantuml_from_app_extension(test_app, get_warnings_list):
    test_app.build()
    assert test_app.statuscode == 0
    index_html = Path(test_app.outdir, "index.html").read_text(encoding="utf8")
    assert "PlantUML is not available" not in index_html
    warnings = get_warnings_list(test_app)
    assert len(warnings) == 0


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/plantuml_unconfigured"}],
    indirect=True,
)
def test_plantuml_unconfigured(test_app, get_warnings_list):
    test_app.build()
    assert test_app.statuscode == 0

    # ONE warning now, where there used to be two. The fixture injected a `plantuml`
    # confoverride into EVERY build, and this project deliberately does not load the
    # extension, so the build also collected "unknown config value 'plantuml' in
    # override, ignoring" -- a warning about the test fixture rather than about
    # sphinx-needs. Rendering is opt in now and this test does not opt in, so nothing is
    # injected and that warning is gone.
    #
    # Still two ENTRIES, though: `get_warnings_list` splits the stream on "WARNING: ", so
    # a located warning arrives as its bare location followed by its message.
    warnings = get_warnings_list(test_app)
    assert len(warnings) == 2
    assert "index.rst" in warnings[0]
    # the page says so, but a build nobody reads the output of said nothing at all
    assert (
        "PlantUML is not available, so the diagram was not rendered. "
        "Install 'sphinxcontrib-plantuml' and add it to the 'extensions' list "
        "to render it." in warnings[1]
    )

    index_html = Path(test_app.outdir, "index.html").read_text(encoding="utf8")
    assert "PlantUML is not available" in index_html
