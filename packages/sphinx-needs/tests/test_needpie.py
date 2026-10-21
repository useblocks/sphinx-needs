from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from sphinx import version_info
from sphinx.testing.util import SphinxTestApp

from sphinx_needs_testkit import build_warnings
from tests.util import chart_images, pie_slice_counts


def _assert_no_default_renderer(app: SphinxTestApp) -> None:
    """This suite's `make_app` rule, asserted where it is easiest to lose.

    A build that chose no renderer -- neither in `confoverrides` nor in its project's own
    `conf.py` -- must not be left on sphinxcontrib-plantuml's DEFAULT command, the bare
    word ``plantuml``: that is whatever unpinned renderer the developer's machine happens
    to carry, and nothing at all on a CI runner. `doc_needpie` loads the extension and
    asserts on no diagram, and these two builds were measured drawing six of them with a
    homebrew PlantUML 1.2026.1 against the 1.2026.8 this repository pins -- silently, and
    for years. The suite's own `make_app` fixture is what neutralises such a build now;
    this is the assertion that says so.

    A project that does not load the extension has no such config value at all, which is
    equally fine -- hence the ``getattr``.
    """
    assert getattr(app.config, "plantuml", None) != "plantuml", (
        "this build chose no renderer and was left on sphinxcontrib-plantuml's default "
        "command, so it would draw with whatever `plantuml` is on PATH -- the suite's "
        "`make_app` fixture should have made it inert"
    )


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needpie"}],
    indirect=True,
)
def test_doc_build_html(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert "SPEC_1" in html
    # the title is used as the alt text
    assert '<img alt="Test pie" id="needpie-index-0" src="_images/need_pie_' in html
    assert '<img alt="Test pie 2" id="needpie-index-1" src="_images/need_pie_' in html


@pytest.mark.parametrize(
    "srcdir", ["doc_test/doc_needpie", "doc_test/doc_needbar"], ids=["pie", "bar"]
)
def test_chart_images_are_reproducible(
    srcdir: str, tmp_path: Path, make_app: type[SphinxTestApp]
):
    """Two builds of unchanged sources must write byte-identical chart images.

    Matplotlib's SVG backend otherwise embeds the wall clock time and, without a
    hash salt, ``uuid4``-derived element ids, which makes every rebuild differ.

    ``needbar`` is covered from here rather than from ``test_needbar.py`` because
    both directives share the one writer, ``utils._savefig_reproducibly``, and this
    keeps its two fixtures in a single parametrisation.
    """
    src_dir = tmp_path / "src"
    shutil.copytree(os.path.join(os.path.dirname(__file__), srcdir), src_dir)

    builds: list[dict[str, bytes]] = []
    for name in ("build_1", "build_2"):
        app = make_app(
            srcdir=src_dir,
            builddir=tmp_path / name,
            buildername="html",
            freshenv=True,
        )
        _assert_no_default_renderer(app)
        app.build()
        assert app.statuscode == 0
        builds.append(
            {
                path.name: path.read_bytes()
                for path in sorted(Path(app.outdir, "_images").glob("*.svg"))
            }
        )
        app.cleanup()

    assert builds[0], "no chart images were written"
    assert list(builds[0]) == list(builds[1]), "image file names differ"
    assert [name for name in builds[0] if builds[0][name] != builds[1][name]] == []


def test_sphinx_api_needpie(tmp_path: Path, make_app: type[SphinxTestApp]):
    """
    Tests a build via the Sphinx Build API.
    """
    build_dir = tmp_path / "_build"
    src_dir = os.path.join(os.path.dirname(__file__), "doc_test/doc_needpie")
    shutil.copytree(src_dir, tmp_path, dirs_exist_ok=True)

    if version_info >= (7, 2):
        src_dir = Path(src_dir)
    else:
        from sphinx.testing.path import path

        src_dir = path(src_dir)
        build_dir = path(build_dir)

    sphinx_app = make_app(
        srcdir=src_dir,
        builddir=build_dir,
        buildername="html",
        parallel=4,
    )
    _assert_no_default_renderer(sphinx_app)
    sphinx_app.build()
    assert sphinx_app.statuscode == 0

    # touch file to force sphinx to purge stuff
    with tmp_path.joinpath("index.rst").open("a") as f:
        f.write("\n\nNew content to force rebuild")

    sphinx_app.build()
    assert sphinx_app.statuscode == 0


#: The needs every chart below counts: two of the three carry tags.
CHART_NEEDS = """\
.. req:: One
   :id: REQ_1
   :tags: a

.. req:: Two
   :id: REQ_2
   :tags: b

.. req:: Three
   :id: REQ_3
"""

CHART_CONF = 'extensions = ["sphinx_needs"]\n'


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CHART_CONF),
                (
                    Path("index.rst"),
                    "Pie\n===\n\n"
                    + CHART_NEEDS
                    + "\n.. needpie:: lines\n\n   10\n   10.5\n   -5\n   tags\n   True\n",
                ),
            ],
        }
    ],
    indirect=True,
)
def test_a_line_is_a_static_value_or_counts_the_needs_it_is_true_for(test_app):
    """A non-negative integer is a static value; anything else is a filter, which counts
    the needs it is true for (``tags``: the two with tags, ``True``: all three), and a
    filter that is any other constant (``10.5``, ``-5``) says nothing about a need: it is
    warned about and counts zero."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        f"<srcdir>/index.rst:15: WARNING: Filter {line!r} not valid. Error: it is a "
        "constant, which says nothing about a need, so it selects none. [needs.filter]"
        for line in ("10.5", "-5")
    ]
    images = chart_images(Path(app.outdir, "index.html").read_text())
    svg = Path(app.outdir, "_images", images["lines"]).read_text()
    assert pie_slice_counts(svg) == [10, 0, 0, 2, 3]
