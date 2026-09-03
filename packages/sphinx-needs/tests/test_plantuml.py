from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/plantuml_from_ext_list"}],
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
    [{"buildername": "html", "srcdir": "doc_test/plantuml_from_app_extension"}],
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

    warnings = get_warnings_list(test_app)
    assert len(warnings) == 2
    assert "unknown config value 'plantuml' in override, ignoring" in warnings[0]
    # the page says so, but a build nobody reads the output of said nothing at all
    assert (
        "PlantUML is not available, so the diagram was not rendered. "
        "Install 'sphinxcontrib-plantuml' and add it to the 'extensions' list "
        "to render it." in warnings[1]
    )

    index_html = Path(test_app.outdir, "index.html").read_text(encoding="utf8")
    assert "PlantUML is not available" in index_html
