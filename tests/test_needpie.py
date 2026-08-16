from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from sphinx import version_info
from sphinx.testing.util import SphinxTestApp


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
    sphinx_app.build()
    assert sphinx_app.statuscode == 0

    # touch file to force sphinx to purge stuff
    with tmp_path.joinpath("index.rst").open("a") as f:
        f.write("\n\nNew content to force rebuild")

    sphinx_app.build()
    assert sphinx_app.statuscode == 0
