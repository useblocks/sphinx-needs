"""Tests for sphinx-ai-index extension."""

import io
import json
from pathlib import Path

from sphinx.application import Sphinx

FIXTURE_ROOT = Path(__file__).parent / "roots" / "test-basic"


def _build(srcdir: Path, tmp_path: Path) -> Path:
    outdir = tmp_path / "_build" / "html"
    doctreedir = tmp_path / "_build" / ".doctrees"
    outdir.mkdir(parents=True)
    app = Sphinx(
        srcdir=str(srcdir),
        confdir=str(srcdir),
        outdir=str(outdir),
        doctreedir=str(doctreedir),
        buildername="html",
        status=io.StringIO(),
        warning=io.StringIO(),
    )
    app.build()
    return outdir


def test_index_file_is_generated(tmp_path: Path) -> None:
    outdir = _build(FIXTURE_ROOT, tmp_path)
    assert (outdir / "ai_docs_index.json").exists()


def test_index_version(tmp_path: Path) -> None:
    outdir = _build(FIXTURE_ROOT, tmp_path)
    data = json.loads((outdir / "ai_docs_index.json").read_text())
    assert data["version"] == "1.0"


def test_index_page_title(tmp_path: Path) -> None:
    outdir = _build(FIXTURE_ROOT, tmp_path)
    data = json.loads((outdir / "ai_docs_index.json").read_text())
    assert len(data["pages"]) >= 1
    assert data["pages"][0]["title"] == "Test Project"


def test_index_page_sections(tmp_path: Path) -> None:
    outdir = _build(FIXTURE_ROOT, tmp_path)
    data = json.loads((outdir / "ai_docs_index.json").read_text())
    sections = data["pages"][0]["sections"]
    assert "Section One" in sections
    assert "Section Two" in sections


def test_index_page_summary(tmp_path: Path) -> None:
    outdir = _build(FIXTURE_ROOT, tmp_path)
    data = json.loads((outdir / "ai_docs_index.json").read_text())
    assert data["pages"][0]["summary"] == "This is the test project summary."


def test_index_page_paths(tmp_path: Path) -> None:
    outdir = _build(FIXTURE_ROOT, tmp_path)
    data = json.loads((outdir / "ai_docs_index.json").read_text())
    page = data["pages"][0]
    assert page["html_path"] == "index.html"
    assert page["rst_source_path"].endswith("index.rst.txt")


def test_empty_summary_when_directive_absent(tmp_path: Path) -> None:
    srcdir = tmp_path / "src"
    srcdir.mkdir()
    (srcdir / "conf.py").write_text(
        "project = 'no-summary'\n"
        "extensions = ['sphinx_ai_index']\n"
        "html_theme = 'alabaster'\n"
    )
    (srcdir / "index.rst").write_text(
        "No Summary Page\n===============\n\nJust content.\n"
    )
    outdir = _build(srcdir, tmp_path)
    data = json.loads((outdir / "ai_docs_index.json").read_text())
    assert data["pages"][0]["summary"] == ""


def test_non_html_builder_produces_no_index(tmp_path: Path) -> None:
    outdir = tmp_path / "_build" / "text"
    doctreedir = tmp_path / "_build" / ".doctrees"
    outdir.mkdir(parents=True)
    app = Sphinx(
        srcdir=str(FIXTURE_ROOT),
        confdir=str(FIXTURE_ROOT),
        outdir=str(outdir),
        doctreedir=str(doctreedir),
        buildername="text",
        status=io.StringIO(),
        warning=io.StringIO(),
    )
    app.build()
    assert not (outdir / "ai_docs_index.json").exists()


def test_custom_sourcelink_suffix(tmp_path: Path) -> None:
    srcdir = tmp_path / "src"
    srcdir.mkdir()
    (srcdir / "conf.py").write_text(
        "project = 'custom-suffix'\n"
        "extensions = ['sphinx_ai_index']\n"
        "html_theme = 'alabaster'\n"
        "html_sourcelink_suffix = '.rst_src'\n"
    )
    (srcdir / "index.rst").write_text(
        "Custom Suffix Page\n==================\n\nContent.\n"
    )
    outdir = _build(srcdir, tmp_path)
    data = json.loads((outdir / "ai_docs_index.json").read_text())
    page = data["pages"][0]
    assert page["rst_source_path"].endswith("index.rst.rst_src")


def test_empty_sourcelink_suffix(tmp_path: Path) -> None:
    srcdir = tmp_path / "src"
    srcdir.mkdir()
    (srcdir / "conf.py").write_text(
        "project = 'empty-suffix'\n"
        "extensions = ['sphinx_ai_index']\n"
        "html_theme = 'alabaster'\n"
        "html_sourcelink_suffix = ''\n"
    )
    (srcdir / "index.rst").write_text(
        "Empty Suffix Page\n=================\n\nContent.\n"
    )
    outdir = _build(srcdir, tmp_path)
    data = json.loads((outdir / "ai_docs_index.json").read_text())
    page = data["pages"][0]
    assert page["rst_source_path"] == "_sources/index.rst"


def test_dirhtml_builder(tmp_path: Path) -> None:
    srcdir = tmp_path / "src"
    srcdir.mkdir()
    (srcdir / "conf.py").write_text(
        "project = 'dirhtml-test'\nextensions = ['sphinx_ai_index']\n"
    )
    (srcdir / "index.rst").write_text(
        "Dirhtml Page\n============\n\n.. toctree::\n\n   subpage\n"
    )
    (srcdir / "subpage.rst").write_text("Subpage\n=======\n\nContent.\n")
    outdir = tmp_path / "_build" / "dirhtml"
    doctreedir = tmp_path / "_build" / ".doctrees"
    outdir.mkdir(parents=True)
    app = Sphinx(
        srcdir=str(srcdir),
        confdir=str(srcdir),
        outdir=str(outdir),
        doctreedir=str(doctreedir),
        buildername="dirhtml",
        status=io.StringIO(),
        warning=io.StringIO(),
    )
    app.build()

    data = json.loads((outdir / "ai_docs_index.json").read_text())
    # Sort pages to easily assert index then subpage
    pages = sorted(data["pages"], key=lambda p: p["html_path"])

    # Empty string for index in dirhtml, subpage/ for subpage
    assert pages[0]["html_path"] == ""
    assert pages[1]["html_path"] == "subpage/"
    assert pages[0]["rst_source_path"].endswith("index.rst.txt")
    assert pages[1]["rst_source_path"].endswith("subpage.rst.txt")


def test_html_copy_source_false(tmp_path: Path) -> None:
    srcdir = tmp_path / "src"
    srcdir.mkdir()
    (srcdir / "conf.py").write_text(
        "project = 'no-copy-source-test'\n"
        "extensions = ['sphinx_ai_index']\n"
        "html_copy_source = False\n"
    )
    (srcdir / "index.rst").write_text("No Copy Source\n==============\n\nContent.\n")
    outdir = _build(srcdir, tmp_path)

    data = json.loads((outdir / "ai_docs_index.json").read_text())
    page = data["pages"][0]
    assert page["html_path"] == "index.html"
    assert page["rst_source_path"] == ""


def test_linkcheck_builder_produces_no_index(tmp_path: Path) -> None:
    srcdir = tmp_path / "src"
    srcdir.mkdir()
    (srcdir / "conf.py").write_text(
        "project = 'linkcheck-test'\nextensions = ['sphinx_ai_index']\n"
    )
    (srcdir / "index.rst").write_text(
        "Linkcheck Page\n==============\n\nLink to https://www.google.com.\n"
    )
    outdir = tmp_path / "_build" / "linkcheck"
    doctreedir = tmp_path / "_build" / ".doctrees"
    outdir.mkdir(parents=True)
    app = Sphinx(
        srcdir=str(srcdir),
        confdir=str(srcdir),
        outdir=str(outdir),
        doctreedir=str(doctreedir),
        buildername="linkcheck",
        status=io.StringIO(),
        warning=io.StringIO(),
    )
    app.build()

    assert not (outdir / "ai_docs_index.json").exists()
