import platform

import pytest
from sphinx.util.console import strip_colors


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/broken_links", "no_plantuml": True}],
    indirect=True,
)
def test_doc_build_html(test_app):
    app = test_app
    app.build()

    # check there are expected warnings
    warnings = strip_colors(app._warning.getvalue().replace(str(app.srcdir), "srcdir"))
    print(warnings.splitlines())

    expected_warnings = [
        "srcdir/index.rst:12: WARNING: Need 'SP_TOO_002' has unknown outgoing link 'NOT_WORKING_LINK' in field 'links' [needs.link_outgoing]",
        "srcdir/index.rst:21: WARNING: linked need BROKEN_LINK not found [needs.link_ref]",
    ]

    if platform.system() == "windows":
        for i in range(len(expected_warnings)):
            expected_warnings[i] = expected_warnings[i].replace("/", "\\", 1)

    assert warnings.splitlines() == expected_warnings
