import os.path
from pathlib import Path

import pytest
from lxml import html as html_parser
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
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_needextract",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_needextract_basic(test_app):
    app = test_app
    app.build()
    assert not app._warning.getvalue()

    def run_checks(checks, html_path):
        html_path = str(Path(app.outdir, html_path))
        tree = html_parser.parse(html_path)
        for check in checks:
            img_src = tree.xpath(
                f"//table[@id='{check[0]}']//td[@class='need content']//img/@src"
            )[0]
            assert img_src == check[1]
            assert os.path.exists(
                str(Path(app.outdir, os.path.dirname(html_path), img_src))
            )

    checks = [
        ("US_SUB_001", "_images/smile.png"),
        ("US_SUB_002", "_images/smile.png"),
        ("US_SUB_003", "_images/smile1.png"),
        ("US_SUB_004", "_images/smile1.png"),
        ("US_SUB_005", "_images/smile1.png"),
        ("US_SUB_005", "_images/smile1.png"),
        ("US_002", "_images/smile.png"),
        ("US_003", "_images/smile.png"),
    ]
    run_checks(checks, "check_images.html")

    checks = [
        ("US_002", "../_images/smile.png"),
        ("US_003", "../_images/smile.png"),
    ]
    run_checks(checks, "subfolder/check_images_2.html")

    index_html = Path(app.outdir, "check_need_refs.html").read_text()
    assert "Awesome Sphinx-Needs" in index_html


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/needextract_with_nested_needs",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_needextract_with_nested_needs(test_app):
    app = test_app
    app.build()
    warnings = strip_colors(
        app._warning.getvalue().replace(str(app.srcdir) + os.sep, "srcdir/")
    ).splitlines()
    # print(warnings)
    # note these warnings are emitted twice because they are resolved twice: once when first specified and once when copied with needextract
    assert warnings == [
        'srcdir/index.rst:13: WARNING: The [[copy("id")]] syntax in need content is deprecated. Replace with :ndf:`copy("id")` instead. [needs.deprecated]',
        'srcdir/index.rst:33: WARNING: The [[copy("id")]] syntax in need content is deprecated. Replace with :ndf:`copy("id")` instead. [needs.deprecated]',
        'srcdir/index.rst:13: WARNING: The [[copy("id")]] syntax in need content is deprecated. Replace with :ndf:`copy("id")` instead. [needs.deprecated]',
        'srcdir/index.rst:33: WARNING: The [[copy("id")]] syntax in need content is deprecated. Replace with :ndf:`copy("id")` instead. [needs.deprecated]',
    ]

    needextract_html = Path(app.outdir, "needextract.html").read_text()

    # ensure that the needs exist and that their hrefs point to the correct location
    assert (
        '<span class="needs-id"><a class="reference internal" href="index.html#SPEC_1" title="SPEC_1">SPEC_1</a>'
        in needextract_html
    )
    assert (
        '<span class="needs-id"><a class="reference internal" href="index.html#SPEC_1_1" title="SPEC_1_1">SPEC_1_1</a>'
        in needextract_html
    )
    assert (
        '<span class="needs-id"><a class="reference internal" '
        'href="index.html#SPEC_1_1_1" title="SPEC_1_1_1">SPEC_1_1_1</a>'
        in needextract_html
    )
    assert (
        '<span class="needs-id"><a class="reference internal" '
        'href="index.html#SPEC_1_1_2" title="SPEC_1_1_2">SPEC_1_1_2</a>'
        in needextract_html
    )

    # dynamic functions should be executed
    assert "This is id SPEC_1 SPEC_1" in needextract_html
    assert "This is grandchild id SPEC_1_1_2 SPEC_1_1_2" in needextract_html


# -- inputs that used to end the build ---------------------------------------
#
# ``found_needs`` was assigned inside the loop over a document's needextract
# nodes and read once after it, so a node that took one of the three early
# exits left the name unbound whenever it was the last (or only) one, and the
# build ended with ``cannot access local variable 'found_needs' where it is not
# associated with a value``.  Two of the three inputs below warn first and used
# to end the build anyway; the third gave no diagnostic at all.

CONF = """\
extensions = ["sphinx_needs"]
"""

CONF_NEEDS_HIDDEN = """\
extensions = ["sphinx_needs"]
needs_include_needs = False
"""

UNKNOWN_ID_INDEX = """\
Extract
=======

.. req:: One
   :id: R_ONE

   Body one.

.. needextract:: R_NOPE
"""

ARG_AND_FILTER_INDEX = """\
Extract
=======

.. req:: One
   :id: R_ONE

   Body one.

.. needextract:: R_ONE
   :filter: id == "R_ONE"
"""

PLAIN_EXTRACT_INDEX = """\
Extract
=======

.. req:: One
   :id: R_ONE

   Body one.

.. needextract:: R_ONE
"""


@pytest.mark.parametrize(
    ("test_app", "expected_warnings", "expected_cards"),
    [
        pytest.param(
            {
                "buildername": "html",
                "no_plantuml": True,
                "files": [
                    (Path("conf.py"), CONF),
                    (Path("index.rst"), UNKNOWN_ID_INDEX),
                ],
            },
            [
                "<srcdir>/index.rst:9: WARNING: Requested need 'R_NOPE' not found. "
                "[needs.needextract]"
            ],
            1,
            id="unknown-id-argument",
        ),
        pytest.param(
            {
                "buildername": "html",
                "no_plantuml": True,
                "files": [
                    (Path("conf.py"), CONF),
                    (Path("index.rst"), ARG_AND_FILTER_INDEX),
                ],
            },
            [
                "<srcdir>/index.rst:9: WARNING: filter arguments and option filter "
                "at the same time are disallowed. [needs.needextract]"
            ],
            1,
            id="argument-and-filter-option",
        ),
        pytest.param(
            {
                "buildername": "html",
                "no_plantuml": True,
                "files": [
                    (Path("conf.py"), CONF_NEEDS_HIDDEN),
                    (Path("index.rst"), PLAIN_EXTRACT_INDEX),
                ],
            },
            [],
            0,
            id="needs_include_needs-off",
        ),
    ],
    indirect=["test_app"],
)
def test_needextract_early_exit_does_not_end_the_build(
    test_app, expected_warnings, expected_cards
):
    """A needextract node that contributes nothing leaves the build standing.

    Each input is reported (or, for ``needs_include_needs = False``, silently
    dropped, exactly as every other view directive drops itself) and the page is
    still written.  ``expected_cards`` counts the cards carrying the authored
    need's anchor: one for the need itself, and none from the directive.
    """
    app = test_app
    app.build()

    assert build_warnings(app) == expected_warnings

    # the page exists, and the directive contributed no need card to it
    html = Path(app.outdir, "index.html").read_text(encoding="utf8")
    assert "<h1>Extract" in html
    assert html.count('id="R_ONE"') == expected_cards
