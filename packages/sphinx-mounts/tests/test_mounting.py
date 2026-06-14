"""End-to-end mounting tests.

These exercise the full Sphinx build pipeline with sphinx-mounts loaded,
to confirm that external RST files are read in place (not copied) and that
the resulting HTML contains the bundle content.

The default config path is ``ubproject.toml`` written into the host
project's confdir — that is the primary, declarative config target. A
couple of tests at the bottom still cover the legacy
``mounts = [...] in conf.py`` path to guard the fallback.
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
from typing import TYPE_CHECKING
import zlib

from docutils import nodes
import pytest
from sphinx import addnodes
from sphinx.testing.fixtures import SharedResult  # noqa: F401  (registers fixture)

from tests.conftest import patch_conf_py, write_ubproject_toml

if TYPE_CHECKING:
    pass


def _read_html(outdir: Path, docname: str) -> str:
    """Read built HTML for a docname (POSIX-separated)."""
    return (outdir / f"{docname}.html").read_text(encoding="utf-8")


def _build(make_app, host_dir: Path) -> Path:
    """Build the host project and return its ``outdir``."""
    app = make_app(srcdir=host_dir, freshenv=True)
    app.build()
    return Path(app.outdir)


# ---------- TOML-driven tests (primary path) ----------


def test_basic_mount_makes_external_files_readable(
    make_app, make_host_project, bundle_simple
):
    host = make_host_project()
    write_ubproject_toml(
        host,
        [{"dir": str(bundle_simple), "mount_at": "_generated/api-foo"}],
    )

    outdir = _build(make_app, host)

    html = _read_html(outdir, "_generated/api-foo/details")
    assert "BUNDLE_SIMPLE_DETAILS_MARKER" in html
    # The external file path was never copied into srcdir.
    assert not (host / "_generated").exists()


def test_bundle_internal_toctree_is_navigable_from_host(
    make_app, make_host_project, bundle_simple
):
    """A bundle author often ships their own ``.. toctree::`` inside
    the bundle's entry doc (e.g. ``index.rst``) to describe the
    bundle's internal structure. After mounting, that toctree must
    still render in the host build and produce working navigation
    links to the bundle's siblings.

    bundle_simple ships with ``index.rst`` whose toctree lists
    ``intro`` and ``details``. This test mounts it under
    ``_generated/api-foo`` and verifies the *whole* navigation chain
    that an end user follows in the rendered host docs:

    host index ─(host toctree)─▶ mount index
              ─(bundle toctree)─▶ intro / details
    """
    host = make_host_project()
    write_ubproject_toml(
        host,
        [{"dir": str(bundle_simple), "mount_at": "_generated/api-foo"}],
    )
    _replace_index_toctree(host, "_generated/api-foo/index")

    outdir = _build(make_app, host)

    # 1) The host's toctree (maxdepth=2) nests the bundle's siblings
    #    transitively, so the host's index.html already links to all
    #    three docs in the mount.
    host_index = (outdir / "index.html").read_text(encoding="utf-8")
    assert "_generated/api-foo/index.html" in host_index
    assert "_generated/api-foo/intro.html" in host_index
    assert "_generated/api-foo/details.html" in host_index

    # 2) The mount's index.html carries the *bundle's own* toctree,
    #    rendered into a compound list with internal references to
    #    its siblings. This is the toctree the bundle author wrote.
    mount_index = (outdir / "_generated" / "api-foo" / "index.html").read_text(
        encoding="utf-8"
    )
    assert "toctree-wrapper" in mount_index, (
        "bundle's own toctree was dropped during rendering"
    )
    assert 'href="intro.html"' in mount_index, (
        "bundle toctree's link to sibling intro is missing"
    )
    assert 'href="details.html"' in mount_index, (
        "bundle toctree's link to sibling details is missing"
    )

    # 3) Sibling pages actually exist and carry their content, so the
    #    above links go somewhere real.
    intro_html = (outdir / "_generated" / "api-foo" / "intro.html").read_text(
        encoding="utf-8"
    )
    details_html = (outdir / "_generated" / "api-foo" / "details.html").read_text(
        encoding="utf-8"
    )
    assert "Introduction" in intro_html
    assert "BUNDLE_SIMPLE_DETAILS_MARKER" in details_html


def test_internal_doc_reference_within_bundle_resolves(
    make_app, make_host_project, bundle_simple
):
    host = make_host_project()
    write_ubproject_toml(
        host,
        [{"dir": str(bundle_simple), "mount_at": "_generated/api-foo"}],
    )

    outdir = _build(make_app, host)

    # intro.rst has `:doc:\`details\`` which should resolve to the sibling
    # mounted doc and produce a hyperlink in the HTML.
    intro_html = _read_html(outdir, "_generated/api-foo/intro")
    assert "details.html" in intro_html


def test_nested_subdirectory_docnames(make_app, make_host_project, bundle_nested):
    host = make_host_project()
    write_ubproject_toml(
        host,
        [{"dir": str(bundle_nested), "mount_at": "_generated/nested"}],
    )
    _replace_index_toctree(host, "_generated/nested/index")

    outdir = _build(make_app, host)

    page_a = _read_html(outdir, "_generated/nested/subdir/page_a")
    page_b = _read_html(outdir, "_generated/nested/subdir/page_b")
    assert "BUNDLE_NESTED_PAGE_A_MARKER" in page_a
    assert "BUNDLE_NESTED_PAGE_B_MARKER" in page_b


def test_rst_host_mounts_rst_and_markdown_bundles_together(
    make_app, make_host_project, bundle_simple, bundle_markdown
):
    """RST host project + one RST mount + one Markdown mount in a
    single build. Proves the mix: the host's own RST file, the mounted
    RST bundle, and the mounted Markdown bundle all render in the same
    pipeline, and cross-mount toctree references resolve."""
    pytest.importorskip("myst_parser")

    host = make_host_project()
    # Host stays a pure RST project; only myst_parser is added so the
    # build can parse mounted .md files.
    conf_path = host / "conf.py"
    conf_path.write_text(
        conf_path.read_text(encoding="utf-8").replace(
            'extensions = ["sphinx_mounts"]',
            'extensions = ["sphinx_mounts", "myst_parser"]',
        ),
        encoding="utf-8",
    )
    write_ubproject_toml(
        host,
        [
            {"dir": str(bundle_simple), "mount_at": "_generated/rst"},
            {"dir": str(bundle_markdown), "mount_at": "_generated/md"},
        ],
    )
    # The host's RST index.rst pulls in both mounts via a single toctree.
    (host / "index.rst").write_text(
        "Host project\n"
        "============\n\n"
        "HOST_RST_MARKER paragraph in the host index.\n\n"
        ".. toctree::\n"
        "   :maxdepth: 2\n\n"
        "   _generated/rst/index\n"
        "   _generated/md/index\n",
        encoding="utf-8",
    )

    outdir = _build(make_app, host)

    # 1) Host's own RST content renders.
    host_html = (outdir / "index.html").read_text(encoding="utf-8")
    assert "HOST_RST_MARKER" in host_html

    # 2) The RST mount renders.
    rst_html = _read_html(outdir, "_generated/rst/details")
    assert "BUNDLE_SIMPLE_DETAILS_MARKER" in rst_html

    # 3) The Markdown mount renders.
    md_html = _read_html(outdir, "_generated/md/index")
    assert "BUNDLE_MARKDOWN_INDEX_MARKER" in md_html

    # 4) Host's toctree linked both mounts — links to both appear in
    # the host index.
    assert "_generated/rst/index.html" in host_html
    assert "_generated/md/index.html" in host_html

    # 5) Nothing was copied into srcdir.
    assert not (host / "_generated").exists()


def test_markdown_mount_with_myst_parser(make_app, make_host_project, bundle_markdown):
    """``.md`` files in a mount are discovered when the host project
    loads ``myst_parser`` — sphinx-mounts iterates whatever Sphinx has
    registered in ``source_suffix``, so any parser-backed extension
    just works."""
    pytest.importorskip("myst_parser")

    host = make_host_project()
    # Add myst_parser to the host's extensions list.
    conf_path = host / "conf.py"
    conf_path.write_text(
        conf_path.read_text(encoding="utf-8").replace(
            'extensions = ["sphinx_mounts"]',
            'extensions = ["sphinx_mounts", "myst_parser"]',
        ),
        encoding="utf-8",
    )
    write_ubproject_toml(
        host,
        [{"dir": str(bundle_markdown), "mount_at": "_generated/md"}],
    )
    _replace_index_toctree(host, "_generated/md/index", "_generated/md/page")

    outdir = _build(make_app, host)

    idx = _read_html(outdir, "_generated/md/index")
    page = _read_html(outdir, "_generated/md/page")
    assert "BUNDLE_MARKDOWN_INDEX_MARKER" in idx
    assert "BUNDLE_MARKDOWN_PAGE_MARKER" in page
    # The Markdown files were never copied into the Sphinx srcdir.
    assert not (host / "_generated").exists()


def test_two_mounts_coexist(make_app, make_host_project, bundle_simple, bundle_nested):
    host = make_host_project()
    write_ubproject_toml(
        host,
        [
            {"dir": str(bundle_simple), "mount_at": "_generated/api-foo"},
            {"dir": str(bundle_nested), "mount_at": "_generated/api-bar"},
        ],
    )
    _replace_index_toctree(
        host,
        "_generated/api-foo/index",
        "_generated/api-bar/index",
    )

    outdir = _build(make_app, host)

    foo = _read_html(outdir, "_generated/api-foo/details")
    bar = _read_html(outdir, "_generated/api-bar/subdir/page_a")
    assert "BUNDLE_SIMPLE_DETAILS_MARKER" in foo
    assert "BUNDLE_NESTED_PAGE_A_MARKER" in bar


def test_mount_at_omitted_places_bundle_at_root(
    make_app, make_host_project, bundle_simple
):
    """A mount entry with no ``mount_at`` lands at the host project
    root. A bundle file ``intro.rst`` becomes docname ``intro``."""
    host = make_host_project()
    # Exclude the bundle's index.rst — the host already has one at the
    # root, and the collision is covered by the next test. This test
    # focuses on the bare-docname semantics of the surviving files.
    write_ubproject_toml(host, [{"dir": str(bundle_simple), "exclude": ["index.rst"]}])
    # Host's own index.rst names the bundle's bare docnames in its
    # toctree (no prefix, because the mount is at root).
    _replace_index_toctree(host, "intro", "details")

    outdir = _build(make_app, host)

    # Bundle files render at the top level, without any prefix.
    assert (outdir / "intro.html").exists()
    assert (outdir / "details.html").exists()
    details_html = (outdir / "details.html").read_text(encoding="utf-8")
    assert "BUNDLE_SIMPLE_DETAILS_MARKER" in details_html
    # No prefix directory was materialised.
    assert not (host / "_generated").exists()


def test_root_mount_shadowing_host_doc_raises(
    make_app, make_host_project, bundle_simple
):
    """When a root-mounted bundle would shadow a host doc that already
    exists at that docname, the existing collision check fires. The
    error message must label the mount as ``<root>`` (not as the
    string representation of None)."""
    host = make_host_project()
    # host_project's index.rst exists; bundle_simple ships an index.rst
    # too. Without a prefix the two docnames collide at "index".
    write_ubproject_toml(host, [{"dir": str(bundle_simple)}])

    with pytest.raises(Exception, match=r"docname conflict.*mount <root>"):
        app = make_app(srcdir=host, freshenv=True)
        app.build()


def test_root_mount_with_attach_to_wires_bare_entry_doc(
    make_app, make_host_project, tmp_path
):
    """Root-mounting plus ``attach_to`` wires the bundle's entry doc
    into the host toctree as a bare docname (no leading slash)."""
    # Use a custom bundle so the entry doc is NOT named "index" — that
    # would collide with the host's own index.rst at the root.
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "tutorial.rst").write_text(
        "Tutorial\n========\n\nTUTORIAL_MARKER\n", encoding="utf-8"
    )

    host = make_host_project()
    _set_index_rst(host, "Host\n====\n\n.. toctree::\n   :maxdepth: 2\n")
    write_ubproject_toml(
        host,
        [
            {
                "dir": str(bundle),
                "attach_to": "index",
                "entry_doc": "tutorial",
            }
        ],
    )

    outdir = _build(make_app, host)

    # The mount produced a bare docname.
    assert (outdir / "tutorial.html").exists()
    # The host's toctree references the bare docname (no leading slash).
    index_html = (outdir / "index.html").read_text(encoding="utf-8")
    assert "tutorial.html" in index_html


# ---------- image / binary asset bundling ----------


def _solid_color_png(
    size: int = 32, rgb: tuple[int, int, int] = (220, 60, 60)
) -> bytes:
    """Build a ``size`` x ``size`` solid-RGB PNG in pure stdlib. Used as
    the asset for the image-bundling tests so the rendered HTML is
    visibly meaningful when a developer opens it — a 1x1 transparent
    pixel passes the test but tells you nothing about whether the
    image actually got there."""
    r, g, b = rgb
    # Filter byte 0 (None) prefix for each scanline.
    scanline = b"\x00" + bytes([r, g, b]) * size
    raw = scanline * size

    def chunk(name: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(name + data)
        return struct.pack(">I", len(data)) + name + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


# 32x32 red square — small but clearly visible on a white page.
_DEMO_PNG = _solid_color_png()


def test_directory_mount_carries_image_assets(make_app, make_host_project, tmp_path):
    """Image assets next to (or beneath) an RST file in a mounted
    bundle render correctly: Sphinx resolves ``.. image::`` paths
    relative to each doc's source location, and the source location
    of a mounted doc is its absolute external path (the value stored
    in ``project._docname_to_path``). No special handling in
    sphinx-mounts — Sphinx's own image-collection pass does the rest,
    so the assets are copied into the build's ``_images/`` directory
    and the resulting HTML references them there."""
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "diagram.png").write_bytes(_DEMO_PNG)
    (bundle / "assets").mkdir()
    (bundle / "assets" / "nested.png").write_bytes(_DEMO_PNG)
    (bundle / "index.rst").write_text(
        "Bundle\n======\n\n"
        "Reference an image next to the RST:\n\n"
        ".. image:: diagram.png\n"
        "   :alt: A diagram beside the RST\n\n"
        "Reference an image in a subdirectory:\n\n"
        ".. image:: assets/nested.png\n"
        "   :alt: Diagram in a subdirectory\n",
        encoding="utf-8",
    )

    host = make_host_project()
    write_ubproject_toml(host, [{"dir": str(bundle), "mount_at": "_generated/m"}])
    _replace_index_toctree(host, "_generated/m/index")

    outdir = _build(make_app, host)

    # Both images land in Sphinx's _images/ output dir. The names may
    # be deduplicated/suffixed by Sphinx if collisions occur, so check
    # via prefix rather than exact match.
    images_dir = outdir / "_images"
    assert images_dir.is_dir(), "_images/ output directory missing"
    names = {p.name for p in images_dir.iterdir()}
    assert any(n.startswith("diagram") and n.endswith(".png") for n in names), names
    assert any(n.startswith("nested") and n.endswith(".png") for n in names), names

    # The rendered HTML references both via the shared _images/ path.
    html = (outdir / "_generated" / "m" / "index.html").read_text(encoding="utf-8")
    assert "_images/diagram" in html
    assert "_images/nested" in html

    # The source images still live in the bundle on disk (no
    # materialisation into the host srcdir).
    assert not (host / "_images").exists()
    assert (bundle / "diagram.png").exists()
    assert (bundle / "assets" / "nested.png").exists()


def test_markdown_mount_carries_image_assets(make_app, make_host_project, tmp_path):
    """Same for Markdown mounts via myst-parser: ``![alt](image.png)``
    resolves relative to the markdown file's source directory."""
    pytest.importorskip("myst_parser")

    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "logo.png").write_bytes(_DEMO_PNG)
    (bundle / "index.md").write_text(
        "# MD Bundle\n\nA logo:\n\n![logo](logo.png)\n",
        encoding="utf-8",
    )

    host = make_host_project()
    conf_path = host / "conf.py"
    conf_path.write_text(
        conf_path.read_text(encoding="utf-8").replace(
            'extensions = ["sphinx_mounts"]',
            'extensions = ["sphinx_mounts", "myst_parser"]',
        ),
        encoding="utf-8",
    )
    write_ubproject_toml(host, [{"dir": str(bundle), "mount_at": "_generated/m"}])
    _replace_index_toctree(host, "_generated/m/index")

    outdir = _build(make_app, host)

    images_dir = outdir / "_images"
    assert images_dir.is_dir()
    names = {p.name for p in images_dir.iterdir()}
    assert any(n.startswith("logo") and n.endswith(".png") for n in names), names

    html = (outdir / "_generated" / "m" / "index.html").read_text(encoding="utf-8")
    assert "_images/logo" in html


# ---------- referencing a pre-built HTML artifact (no copy) ----------


def test_mounted_bundle_links_html_extra_path_report(
    make_app, make_host_project, tmp_path
):
    """A shipped bundle RST links to and embeds a pre-built HTML report
    (e.g. an lcov tree) that Sphinx's ``html_extra_path`` copies verbatim
    into the build *output*.

    The report is read in place — never staged into the source tree — and
    the rendered site is *self-contained*: the report's bytes are in the
    output, so the site can be published to any server with the report
    travelling alongside it. This is the supported pattern for referencing
    an external HTML artifact from a mounted bundle without duplicating
    sources. A plain link/iframe records no Sphinx dependency, so the
    bundle's mount machinery is not involved beyond hosting the page.
    """
    # A pre-built HTML report living OUTSIDE the bundle and the srcdir.
    # ``html_extra_path`` copies the *contents* of a listed directory into
    # the output root, so we list the report's parent; the ``coverage``
    # directory name is then preserved at ``<out>/coverage/``.
    extra = tmp_path / "artifacts"
    report = extra / "coverage"
    report.mkdir(parents=True)
    (report / "index.html").write_text(
        "<h1>COVERAGE_REPORT_HOME</h1>\n", encoding="utf-8"
    )
    (report / "mod.py.html").write_text("<p>per-file coverage</p>\n", encoding="utf-8")

    # The bundle's entry doc links to + embeds the report. Mounted at
    # ``_generated/m``, the doc renders at ``_generated/m/index.html``
    # (depth 2), so ``../../coverage/index.html`` reaches the site-root
    # report.
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "index.rst").write_text(
        "Bundle\n======\n\nBUNDLE_WITH_REPORT\n\n"
        ".. raw:: html\n\n"
        '   <a href="../../coverage/index.html">Open coverage</a>\n'
        '   <iframe src="../../coverage/index.html"></iframe>\n',
        encoding="utf-8",
    )

    host = make_host_project()
    # ``html_extra_path`` lives in conf.py; point it at the external
    # report's parent directory (absolute, repr-quoted for any OS).
    conf = host / "conf.py"
    conf.write_text(
        conf.read_text(encoding="utf-8") + f"\nhtml_extra_path = [{str(extra)!r}]\n",
        encoding="utf-8",
    )
    write_ubproject_toml(host, [{"dir": str(bundle), "mount_at": "_generated/m"}])
    _replace_index_toctree(host, "_generated/m/index")

    outdir = _build(make_app, host)

    # 1) The report was copied verbatim into the OUTPUT → self-contained.
    assert (outdir / "coverage" / "index.html").exists()
    assert (outdir / "coverage" / "mod.py.html").exists()
    assert "COVERAGE_REPORT_HOME" in (outdir / "coverage" / "index.html").read_text(
        encoding="utf-8"
    )
    # 2) The shipped bundle page links to + embeds the report.
    page = (outdir / "_generated" / "m" / "index.html").read_text(encoding="utf-8")
    assert 'href="../../coverage/index.html"' in page
    assert 'src="../../coverage/index.html"' in page
    # 3) Read in place: the report was NOT staged into the docs srcdir; the
    #    original still lives where it was.
    assert not (host / "coverage").exists()
    assert (report / "index.html").exists()


# ---------- include / gitignore opt-out ----------


def test_include_allowlist_restricts_walk(make_app, make_host_project, tmp_path):
    """A non-empty ``include`` list allowlists files; non-matching
    docs in the same directory are filtered out before they ever
    reach Sphinx."""
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "public.rst").write_text(
        "Public\n======\n\nPUBLIC_MARKER\n", encoding="utf-8"
    )
    (bundle / "internal.rst").write_text(
        "Internal\n========\n\nINTERNAL_MARKER\n", encoding="utf-8"
    )

    host = make_host_project()
    write_ubproject_toml(
        host,
        [
            {
                "dir": str(bundle),
                "mount_at": "_generated/m",
                "include": ["public.rst"],
            }
        ],
    )
    _replace_index_toctree(host, "_generated/m/public")

    outdir = _build(make_app, host)

    assert (outdir / "_generated" / "m" / "public.html").exists()
    assert not (outdir / "_generated" / "m" / "internal.html").exists()


def test_directory_mount_can_disable_gitignore(make_app, make_host_project, tmp_path):
    """A sibling repo's ``.gitignore`` should not be allowed to silently
    drop content the host project actually wants to mount. Setting
    ``gitignore = false`` on the mount makes the walker treat
    in-tree ``.gitignore`` files as data, not as filter rules."""
    bundle = tmp_path / "sibling_repo"
    bundle.mkdir()
    (bundle / "kept.rst").write_text("Kept\n====\n\nKEPT_MARKER\n", encoding="utf-8")
    (bundle / "release-notes.rst").write_text(
        "Release\n=======\n\nRELEASE_MARKER\n", encoding="utf-8"
    )
    (bundle / ".gitignore").write_text("release-notes.rst\n", encoding="utf-8")
    # Make the bundle a git repo so .gitignore would normally apply.
    subprocess.run(["git", "init", "-q"], cwd=bundle, check=True)

    host = make_host_project()
    write_ubproject_toml(
        host,
        [
            {
                "dir": str(bundle),
                "mount_at": "_generated/m",
                "gitignore": False,
            }
        ],
    )
    _replace_index_toctree(host, "_generated/m/kept", "_generated/m/release-notes")

    outdir = _build(make_app, host)

    # Both files render — the gitignore rule is suppressed.
    assert (outdir / "_generated" / "m" / "kept.html").exists()
    assert (outdir / "_generated" / "m" / "release-notes.html").exists()
    release = (outdir / "_generated" / "m" / "release-notes.html").read_text(
        encoding="utf-8"
    )
    assert "RELEASE_MARKER" in release


# ---------- gitignore handling ----------


def test_directory_mount_respects_in_bundle_gitignore(
    make_app, make_host_project, tmp_path
):
    """A ``.gitignore`` inside a mount source (when that source is a git
    repository) filters out matching files. Same library as
    sphinx-codelinks and ubCode use, so editor previews and the build
    see the same set of mounted docs."""
    bundle = tmp_path / "bundle_with_gitignore"
    bundle.mkdir()
    (bundle / "keep.rst").write_text("Keep\n====\n\nKEEP_MARKER\n", encoding="utf-8")
    (bundle / "drop.rst").write_text("Drop\n====\n\nDROP_MARKER\n", encoding="utf-8")
    (bundle / "index.rst").write_text(
        "Idx\n===\n\n.. toctree::\n\n   keep\n", encoding="utf-8"
    )
    (bundle / ".gitignore").write_text("drop.rst\n", encoding="utf-8")
    # Make the bundle a git repo so the Rust ignore crate activates
    # gitignore handling for files inside this tree.
    subprocess.run(["git", "init", "-q"], cwd=bundle, check=True)

    host = make_host_project()
    write_ubproject_toml(
        host,
        [{"dir": str(bundle), "mount_at": "_generated/api"}],
    )
    _replace_index_toctree(host, "_generated/api/index")

    outdir = _build(make_app, host)

    # Survivor renders.
    assert (outdir / "_generated/api/keep.html").exists()
    # gitignored file does NOT become a docname.
    assert not (outdir / "_generated/api/drop.html").exists()


def test_directory_mount_ignores_parent_gitignore(
    make_app, make_host_project, tmp_path
):
    """A ``.gitignore`` in a parent directory of the mount source must
    NOT bleed into the walk. This matters for the typical Bazel layout
    where ``bazel-bin/`` is gitignored at the workspace root but the
    mounted ``bazel-bin/docs/`` contents are exactly what we want."""
    # workspace/.gitignore says "bin/", and the bundle lives under bin/.
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / ".gitignore").write_text("bin/\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=workspace, check=True)
    bundle = workspace / "bin" / "docs"
    bundle.mkdir(parents=True)
    (bundle / "index.rst").write_text(
        "Idx\n===\n\nGENERATED_MARKER\n", encoding="utf-8"
    )

    host = make_host_project()
    write_ubproject_toml(
        host,
        [{"dir": str(bundle), "mount_at": "_generated/api"}],
    )
    _replace_index_toctree(host, "_generated/api/index")

    outdir = _build(make_app, host)

    # The generated doc must render despite workspace/.gitignore
    # excluding "bin/" — the walker only honours gitignore inside the
    # mounted tree.
    assert (outdir / "_generated/api/index.html").exists()
    html = (outdir / "_generated/api/index.html").read_text(encoding="utf-8")
    assert "GENERATED_MARKER" in html


# ---------- file-list mode ----------


def test_mount_single_file_via_files(make_app, make_host_project, bundle_simple):
    """A `files = [...]` mount with one entry registers exactly that doc."""
    host = make_host_project()
    write_ubproject_toml(
        host,
        [
            {
                "files": [str(bundle_simple / "intro.rst")],
                "mount_at": "_generated/api",
            }
        ],
    )
    _replace_index_toctree(host, "_generated/api/intro")

    outdir = _build(make_app, host)

    intro = _read_html(outdir, "_generated/api/intro")
    # The intro section title from the source RST should render.
    assert "Introduction" in intro
    # Only the listed file should have rendered; details.rst and index.rst
    # are siblings in the bundle but were not listed.
    assert not (outdir / "_generated/api/details.html").exists()
    assert not (outdir / "_generated/api/index.html").exists()


def test_mount_multiple_files_via_files(make_app, make_host_project, bundle_simple):
    """A `files = [...]` mount with multiple entries registers all of them
    flat under ``mount_at`` (basename → docname tail)."""
    host = make_host_project()
    write_ubproject_toml(
        host,
        [
            {
                "files": [
                    str(bundle_simple / "intro.rst"),
                    str(bundle_simple / "details.rst"),
                ],
                "mount_at": "_generated/api",
            }
        ],
    )
    _replace_index_toctree(host, "_generated/api/intro", "_generated/api/details")

    outdir = _build(make_app, host)

    intro = _read_html(outdir, "_generated/api/intro")
    details = _read_html(outdir, "_generated/api/details")
    assert (outdir / "_generated/api/intro.html").exists()
    assert (outdir / "_generated/api/details.html").exists()
    assert "BUNDLE_SIMPLE_DETAILS_MARKER" in details
    # intro.rst should still have rendered as text-only content.
    assert intro  # non-empty


def test_mount_files_with_attach_to_wires_entry_doc(
    make_app, make_host_project, bundle_simple
):
    """File-list mode honors attach_to + entry_doc just like directory mode."""
    host = make_host_project()
    _set_index_rst(host, "Host\n====\n\n.. toctree::\n   :maxdepth: 2\n")
    write_ubproject_toml(
        host,
        [
            {
                "files": [
                    str(bundle_simple / "intro.rst"),
                    str(bundle_simple / "details.rst"),
                ],
                "mount_at": "_generated/api",
                "attach_to": "index",
                "entry_doc": "intro",
            }
        ],
    )

    outdir = _build(make_app, host)

    # The host toctree should now contain the wired-up entry doc.
    index_html = (outdir / "index.html").read_text(encoding="utf-8")
    assert "_generated/api/intro.html" in index_html


def test_mount_files_unknown_suffix_raises(make_app, make_host_project, tmp_path):
    """A listed file whose extension is not in source_suffix is an error —
    the user explicitly asked for it to be mounted, so silently skipping
    would be the wrong behaviour."""
    host = make_host_project()
    odd = tmp_path / "notes.adoc"
    odd.write_text("= AsciiDoc not configured\n", encoding="utf-8")
    write_ubproject_toml(
        host,
        [{"files": [str(odd)], "mount_at": "_generated/api"}],
    )

    with pytest.raises(Exception, match="source_suffix"):
        app = make_app(srcdir=host, freshenv=True)
        app.build()


def test_mount_files_missing_file_raises(make_app, make_host_project, tmp_path):
    host = make_host_project()
    write_ubproject_toml(
        host,
        [
            {
                "files": [str(tmp_path / "does_not_exist.rst")],
                "mount_at": "_generated/api",
            }
        ],
    )

    with pytest.raises(Exception, match="does not exist or is not a file"):
        make_app(srcdir=host, freshenv=True)


def test_missing_mount_dir_raises(make_app, make_host_project, tmp_path):
    host = make_host_project()
    missing = tmp_path / "does_not_exist"
    write_ubproject_toml(
        host,
        [{"dir": str(missing), "mount_at": "_generated/api-foo"}],
    )

    # Sphinx wraps handler exceptions in ExtensionError; match on the
    # underlying message instead of the exception type.
    with pytest.raises(Exception, match="does not exist"):
        make_app(srcdir=host, freshenv=True)


def test_exclude_filter_bundle_files(make_app, make_host_project, bundle_simple):
    host = make_host_project()
    write_ubproject_toml(
        host,
        [
            {
                "dir": str(bundle_simple),
                "mount_at": "_generated/api-foo",
                "exclude": ["details.rst"],
            },
        ],
    )
    _replace_index_toctree(host, "_generated/api-foo/intro")

    outdir = _build(make_app, host)

    assert (outdir / "_generated/api-foo/intro.html").exists()
    assert not (outdir / "_generated/api-foo/details.html").exists()


def test_docname_conflict_raises(make_app, make_host_project, bundle_simple, tmp_path):
    """Two mounts producing the same docname must be rejected."""
    host = make_host_project()
    # Duplicate the bundle at a second source dir; both mount at the same
    # prefix so docnames collide.
    second = tmp_path / "dup"
    second.mkdir()
    (second / "index.rst").write_text("Dup\n===\n", encoding="utf-8")
    write_ubproject_toml(
        host,
        [
            {"dir": str(bundle_simple), "mount_at": "_generated/clash"},
            {"dir": str(second), "mount_at": "_generated/clash"},
        ],
    )

    # Conflict is raised during discover(), which runs as part of build();
    # Sphinx wraps it in ExtensionError.
    with pytest.raises(Exception, match="docname conflict"):
        app = make_app(srcdir=host, freshenv=True)
        app.build()


def test_strict_mount_at_rejects_preexisting_host_dir(
    make_app, make_host_project, bundle_simple
):
    """With ``strict_mount_at = true``, a host directory at the mount
    point is a misconfiguration even when no concrete docname collides.
    """
    host = make_host_project()
    (host / "_generated" / "api-foo").mkdir(parents=True)
    write_ubproject_toml(
        host,
        [
            {
                "dir": str(bundle_simple),
                "mount_at": "_generated/api-foo",
                "strict_mount_at": True,
            }
        ],
    )

    with pytest.raises(Exception, match=r"strict_mount_at.*_generated/api-foo"):
        app = make_app(srcdir=host, freshenv=True)
        app.build()


def test_strict_mount_at_passes_when_no_host_dir(
    make_app, make_host_project, bundle_simple
):
    """With ``strict_mount_at = true`` and no host directory at the
    mount point, the build proceeds normally."""
    host = make_host_project()
    assert not (host / "_generated").exists()
    write_ubproject_toml(
        host,
        [
            {
                "dir": str(bundle_simple),
                "mount_at": "_generated/api-foo",
                "strict_mount_at": True,
            }
        ],
    )

    outdir = _build(make_app, host)
    assert (outdir / "_generated" / "api-foo" / "details.html").exists()


def test_strict_mount_at_default_permissive_allows_host_dir(
    make_app, make_host_project, bundle_simple
):
    """Regression check: with ``strict_mount_at`` unset (default False),
    a host directory at the mount point is fine as long as no individual
    docname collides — the existing per-docname check is the only gate."""
    host = make_host_project()
    # A host-owned staging dir at the mount point, containing a
    # non-source sibling (Sphinx ignores extensions outside source_suffix).
    (host / "_generated" / "api-foo").mkdir(parents=True)
    (host / "_generated" / "api-foo" / "notes.txt").write_text(
        "host-owned notes\n", encoding="utf-8"
    )
    write_ubproject_toml(
        host,
        [{"dir": str(bundle_simple), "mount_at": "_generated/api-foo"}],
    )

    outdir = _build(make_app, host)
    assert (outdir / "_generated" / "api-foo" / "details.html").exists()


def test_strict_mount_at_rejects_preexisting_host_dir_in_files_mode(
    make_app, make_host_project, bundle_simple
):
    """The strict check is mode-agnostic — file-list mounts honour it
    the same way directory mounts do."""
    host = make_host_project()
    (host / "_generated" / "release-notes").mkdir(parents=True)
    write_ubproject_toml(
        host,
        [
            {
                "files": [str(bundle_simple / "intro.rst")],
                "mount_at": "_generated/release-notes",
                "strict_mount_at": True,
            }
        ],
    )

    with pytest.raises(Exception, match=r"strict_mount_at.*_generated/release-notes"):
        app = make_app(srcdir=host, freshenv=True)
        app.build()


def test_toml_overrides_conf_py_mounts(
    make_app, make_host_project, bundle_simple, bundle_nested
):
    """If both ubproject.toml and conf.py declare mounts, TOML wins."""
    host = make_host_project()
    # conf.py declares one mount...
    patch_conf_py(
        host,
        f"[{{'dir': r'{bundle_nested}', 'mount_at': '_generated/from-py'}}]",
    )
    # ...but ubproject.toml declares a different one. TOML should win, so
    # only the TOML-declared mount appears in the build.
    write_ubproject_toml(
        host,
        [{"dir": str(bundle_simple), "mount_at": "_generated/from-toml"}],
    )

    outdir = _build(make_app, host)

    assert (outdir / "_generated/from-toml/details.html").exists()
    assert not (outdir / "_generated/from-py/index.html").exists()


def test_toml_in_subdir_anchors_paths_to_toml_directory(
    make_app, make_host_project, bundle_simple
):
    """When ``mounts_from_toml`` points at a TOML in a subdirectory of
    confdir, relative paths inside that TOML resolve against the TOML's
    own directory — not against confdir. This keeps the TOML
    self-describing across moves."""
    host = make_host_project()

    # Stage a copy of the bundle at <host>/../files/bundle so we can
    # express its location as a TOML-anchored relative path.
    staged = host.parent / "files" / "bundle"
    staged.mkdir(parents=True, exist_ok=True)
    for f in bundle_simple.iterdir():
        (staged / f.name).write_bytes(f.read_bytes())

    # Place the TOML one level below confdir. A path like
    # ``../../files/bundle`` is meaningful only if anchored to the TOML's
    # own directory; anchored to confdir (``host/``) it would point at
    # ``host/../files/bundle`` — *one level too high*.
    subdir = host / "configs"
    subdir.mkdir()
    toml = subdir / "mounts.toml"
    toml.write_text(
        '[[mounts]]\ndir = "../../files/bundle"\nmount_at = "_generated/api-foo"\n',
        encoding="utf-8",
    )
    (host / "conf.py").write_text(
        (host / "conf.py").read_text(encoding="utf-8")
        + '\nmounts_from_toml = "configs/mounts.toml"\n',
        encoding="utf-8",
    )

    outdir = _build(make_app, host)

    # The bundle's docs rendered, proving the relative path resolved
    # against the TOML's directory (configs/), not against confdir.
    assert (outdir / "_generated/api-foo/details.html").exists()


def test_custom_toml_path(make_app, make_host_project, bundle_simple):
    """``mounts_from_toml`` accepts a non-default file name."""
    host = make_host_project()
    write_ubproject_toml(
        host,
        [{"dir": str(bundle_simple), "mount_at": "_generated/api-foo"}],
        filename="custom-config.toml",
    )
    # Tell conf.py where to find it.
    (host / "conf.py").write_text(
        (host / "conf.py").read_text(encoding="utf-8")
        + '\nmounts_from_toml = "custom-config.toml"\n',
        encoding="utf-8",
    )

    outdir = _build(make_app, host)

    assert (outdir / "_generated/api-foo/details.html").exists()


# ---------- Legacy conf.py-driven coverage ----------


def test_conf_py_mounts_used_when_no_toml(make_app, make_host_project, bundle_simple):
    """No ubproject.toml present → mounts from conf.py are used."""
    host = make_host_project()
    patch_conf_py(
        host,
        f"[{{'dir': r'{bundle_simple}', 'mount_at': '_generated/api-foo'}}]",
    )
    # Ensure no ubproject.toml exists in confdir.
    assert not (host / "ubproject.toml").exists()

    outdir = _build(make_app, host)

    assert (outdir / "_generated/api-foo/details.html").exists()


def test_mounts_from_toml_disabled_with_none(
    make_app, make_host_project, bundle_simple
):
    """Setting ``mounts_from_toml = None`` skips TOML loading entirely."""
    host = make_host_project()
    # Both conf.py and TOML declare mounts; setting mounts_from_toml=None
    # must make conf.py win because TOML loading is disabled.
    write_ubproject_toml(
        host,
        [{"dir": str(bundle_simple), "mount_at": "_generated/ignored"}],
    )
    (host / "conf.py").write_text(
        (host / "conf.py").read_text(encoding="utf-8")
        + "\nmounts_from_toml = None\n"
        + f"\nmounts = [{{'dir': r'{bundle_simple}', 'mount_at': '_generated/from-py'}}]\n",
        encoding="utf-8",
    )

    outdir = _build(make_app, host)

    assert (outdir / "_generated/from-py/details.html").exists()
    assert not (outdir / "_generated/ignored/details.html").exists()


# ---------- attach_to: toctree integration ----------


def test_attach_to_extends_existing_toctree(make_app, make_host_project, bundle_simple):
    """A mount with attach_to extends the host doc's existing toctree."""
    host = make_host_project()
    _set_index_rst(host, "Host\n====\n\n.. toctree::\n   :maxdepth: 2\n")
    write_ubproject_toml(
        host,
        [
            {
                "dir": str(bundle_simple),
                "mount_at": "_generated/api-foo",
                "attach_to": "index",
            }
        ],
    )

    outdir = _build(make_app, host)

    assert (outdir / "_generated/api-foo/index.html").exists()
    index_html = (outdir / "index.html").read_text(encoding="utf-8")
    assert "_generated/api-foo/index.html" in index_html


def test_attach_to_targets_specific_toctree_by_index(
    make_app, make_host_project, bundle_simple
):
    """toctree_index picks the right toctree in a multi-toctree doc."""
    host = make_host_project()
    _set_index_rst(
        host,
        "Host\n====\n\n"
        "First section\n-------------\n\n"
        ".. toctree::\n   :maxdepth: 1\n   :caption: FirstCaption\n\n"
        "Second section\n--------------\n\n"
        ".. toctree::\n   :maxdepth: 2\n   :caption: SecondCaption\n",
    )
    write_ubproject_toml(
        host,
        [
            {
                "dir": str(bundle_simple),
                "mount_at": "_generated/api-foo",
                "attach_to": "index",
                "toctree_index": 1,
            }
        ],
    )

    app = make_app(srcdir=host, freshenv=True)
    app.build()

    # Inspect the parsed doctree directly: the mount entry must be in
    # the *second* toctree node (index 1, the SecondCaption one), not
    # the first. Counting links in rendered HTML is unreliable because
    # furo and other themes render toctrees in multiple places
    # (sidebar, body, breadcrumbs) and the body order doesn't always
    # follow source order.
    doctree = app.env.get_doctree("index")
    toctrees = list(doctree.findall(addnodes.toctree))
    assert len(toctrees) == 2, f"expected 2 toctrees, got {len(toctrees)}"
    entry = "_generated/api-foo/index"
    assert entry not in toctrees[0]["includefiles"], (
        "mount entry leaked into the first toctree"
    )
    assert entry in toctrees[1]["includefiles"], (
        "mount entry did not land in the second toctree"
    )


def test_attach_to_index_out_of_range_raises(
    make_app, make_host_project, bundle_simple
):
    """Asking for a toctree that doesn't exist must fail loudly."""
    host = make_host_project()
    _set_index_rst(host, "Host\n====\n\n.. toctree::\n   :maxdepth: 1\n")
    write_ubproject_toml(
        host,
        [
            {
                "dir": str(bundle_simple),
                "mount_at": "_generated/api-foo",
                "attach_to": "index",
                "toctree_index": 5,
            }
        ],
    )

    with pytest.raises(Exception, match="only 1 toctree"):
        _build(make_app, host)


def test_attach_to_creates_toctree_when_absent(
    make_app, make_host_project, bundle_simple
):
    """If the host doc has no toctree, the extension adds one."""
    host = make_host_project()
    _set_index_rst(
        host,
        "Host\n====\n\nJust a paragraph, no toctree at all.\n",
    )
    write_ubproject_toml(
        host,
        [
            {
                "dir": str(bundle_simple),
                "mount_at": "_generated/api-foo",
                "attach_to": "index",
            }
        ],
    )

    outdir = _build(make_app, host)

    assert (outdir / "_generated/api-foo/index.html").exists()
    index_html = (outdir / "index.html").read_text(encoding="utf-8")
    assert "_generated/api-foo/index.html" in index_html


def test_attach_to_appends_new_toctree_at_section_end(
    make_app, make_host_project, bundle_simple
):
    """When no toctree exists, the new one lands at the END of the first
    top-level section — after every existing child the host author wrote.

    The host keeps full control of its content prefix; injected mount
    entries are always below it. This is asserted directly on the
    parsed doctree (not on rendered HTML, which themes can re-order).
    """
    host = make_host_project()
    _set_index_rst(
        host,
        "Host\n====\n\n"
        "Intro paragraph that must stay first.\n\n"
        "Second paragraph that must stay second.\n\n"
        "Subsection\n----------\n\n"
        "Content inside the subsection.\n",
    )
    write_ubproject_toml(
        host,
        [
            {
                "dir": str(bundle_simple),
                "mount_at": "_generated/api-foo",
                "attach_to": "index",
            }
        ],
    )

    app = make_app(srcdir=host, freshenv=True)
    app.build()

    doctree = app.env.get_doctree("index")
    first_section = next(doctree.findall(nodes.section))
    last_child = first_section.children[-1]
    assert isinstance(last_child, addnodes.toctree), (
        f"expected toctree as the last child of the first section, "
        f"got {type(last_child).__name__}"
    )
    # Every existing child the host author wrote must come before the
    # toctree — no exceptions, including nested subsections.
    toctree_idx = first_section.children.index(last_child)
    assert toctree_idx == len(first_section.children) - 1
    for sibling in first_section.children[:toctree_idx]:
        assert not isinstance(sibling, addnodes.toctree), (
            "found a second toctree — only one should have been added"
        )


def test_attach_to_with_custom_entry_doc(make_app, make_host_project, bundle_simple):
    """entry_doc selects which file inside the mount to wire up."""
    host = make_host_project()
    _set_index_rst(host, "Host\n====\n\n.. toctree::\n   :maxdepth: 1\n")
    # bundle_simple has intro.rst alongside index.rst — point at it.
    write_ubproject_toml(
        host,
        [
            {
                "dir": str(bundle_simple),
                "mount_at": "_generated/api-foo",
                "attach_to": "index",
                "entry_doc": "intro",
            }
        ],
    )

    outdir = _build(make_app, host)

    index_html = (outdir / "index.html").read_text(encoding="utf-8")
    assert "_generated/api-foo/intro.html" in index_html


def test_attach_to_idempotent_with_static_entry(
    make_app, make_host_project, bundle_simple
):
    """If the host already names the mount entry, attach_to is a no-op."""
    host = make_host_project()
    _set_index_rst(
        host,
        "Host\n====\n\n.. toctree::\n   :maxdepth: 1\n\n   _generated/api-foo/index\n",
    )
    write_ubproject_toml(
        host,
        [
            {
                "dir": str(bundle_simple),
                "mount_at": "_generated/api-foo",
                "attach_to": "index",
            }
        ],
    )

    app = make_app(srcdir=host, freshenv=True)
    app.build()

    # Inspect the env's resolved toctree includes — the dedup guarantee is
    # that ``_generated/api-foo/index`` appears once for the host index doc,
    # not twice. Counting rendered HTML links is unreliable because themes
    # render each entry in multiple places (sidebar, breadcrumbs, ...).
    includes = list(app.env.toctree_includes.get("index", []))
    assert includes.count("_generated/api-foo/index") == 1


def test_attach_to_warns_when_target_docname_missing(
    make_app, make_host_project, bundle_simple
):
    """A mount whose ``attach_to`` names a docname that does not exist in
    the host project must surface a warning at env-check-consistency
    time. Without the warning, a typo in ``attach_to`` would silently
    leave the mount un-wired and the misconfiguration would be hard to
    diagnose."""
    host = make_host_project()
    write_ubproject_toml(
        host,
        [
            {
                "dir": str(bundle_simple),
                "mount_at": "_generated/api-foo",
                "attach_to": "nonexistent_host_doc",
            }
        ],
    )
    _replace_index_toctree(host, "_generated/api-foo/index")

    app = make_app(srcdir=host, freshenv=True)
    app.build()

    warnings = app._warning.getvalue()
    assert "nonexistent_host_doc" in warnings
    assert "attach_to" in warnings


# ---------- helpers ----------


def _replace_index_toctree(host: Path, *docnames: str) -> None:
    """Rewrite index.rst to reference the given docnames in a toctree."""
    body = "Host project\n============\n\n.. toctree::\n   :maxdepth: 2\n\n"
    for d in docnames:
        body += f"   {d}\n"
    (host / "index.rst").write_text(body, encoding="utf-8")


def _set_index_rst(host: Path, body: str) -> None:
    """Overwrite ``index.rst`` in ``host`` with the given body."""
    (host / "index.rst").write_text(body, encoding="utf-8")


def _bump_mtime(p: Path, seconds: float = 60.0) -> None:
    """Push ``p``'s mtime forward to defeat coarse filesystem mtime
    resolution. Linux ``ext4`` + ``relatime`` and macOS HFS+ can
    report whole-second precision; without this, two writes inside
    the same second can leave Sphinx thinking nothing changed."""
    bump = p.stat().st_mtime + seconds
    os.utime(p, (bump, bump))


_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


def _docs_read_in_log(log: str) -> set[str]:
    """Extract the set of docnames Sphinx reports as ``reading
    sources...`` in a build log. Ignores ANSI escape codes and
    everything after the reading phase, so warnings that happen to
    mention a docname's path do not leak into the result."""
    plain = _ANSI_ESCAPE_RE.sub("", log)
    read: set[str] = set()
    for line in plain.splitlines():
        idx = line.find("reading sources...")
        if idx == -1:
            continue
        after = line[idx + len("reading sources...") :]
        # Drop the ``[NN%]`` progress marker if present.
        after = re.sub(r"^\s*\[\s*\d+%?\s*\]\s*", "", after)
        doc = after.strip()
        if doc:
            read.add(doc)
    return read


# ---------- incremental rebuild ----------


def test_incremental_only_reads_changed_mount_file(
    make_app, make_host_project, tmp_path, bundle_simple
):
    """Editing a single file in a directory mount makes Sphinx re-read
    only that file on the next incremental build. Sphinx's standard
    mtime-based change detection works for mounted docs because their
    absolute paths live in ``project._docname_to_path`` — Sphinx
    inspects ``getmtime(stored_path)`` on each rebuild."""
    host = make_host_project()
    # Writable copy of the bundle so we can edit one of its files.
    bundle = tmp_path / "bundle"
    shutil.copytree(bundle_simple, bundle)
    write_ubproject_toml(host, [{"dir": str(bundle), "mount_at": "_generated/m"}])
    _replace_index_toctree(
        host,
        "_generated/m/index",
        "_generated/m/intro",
        "_generated/m/details",
    )

    app = make_app(srcdir=host, freshenv=True)
    app.build()
    # Capture log offset so we only inspect the second build's output.
    offset = len(app._status.getvalue())

    target = bundle / "intro.rst"
    target.write_text(
        target.read_text(encoding="utf-8") + "\nMODIFIED_LINE\n", encoding="utf-8"
    )
    _bump_mtime(target)

    app.build()
    warm_log = app._status.getvalue()[offset:]

    # Only the edited mount doc should appear in the "reading sources"
    # output of the warm rebuild.
    read = _docs_read_in_log(warm_log)
    assert "_generated/m/intro" in read, f"intro not re-read; read={read}"
    assert "_generated/m/details" not in read, f"details re-read; read={read}"
    assert "_generated/m/index" not in read, f"mount index re-read; read={read}"


def test_incremental_skips_mount_when_nothing_changed(
    make_app, make_host_project, tmp_path, bundle_simple
):
    """No file changed between builds → no mount doc is re-read.
    Confirms the extension does not force re-parsing on every build."""
    host = make_host_project()
    bundle = tmp_path / "bundle"
    shutil.copytree(bundle_simple, bundle)
    write_ubproject_toml(host, [{"dir": str(bundle), "mount_at": "_generated/m"}])
    _replace_index_toctree(
        host,
        "_generated/m/index",
        "_generated/m/intro",
        "_generated/m/details",
    )

    app = make_app(srcdir=host, freshenv=True)
    app.build()
    offset = len(app._status.getvalue())

    # Rebuild without changing anything.
    app.build()
    warm_log = app._status.getvalue()[offset:]

    read = _docs_read_in_log(warm_log)
    mount_docs_read = {d for d in read if d.startswith("_generated/m/")}
    assert mount_docs_read == set(), (
        f"mount docs were re-read despite no changes: {mount_docs_read}"
    )


def test_host_toctree_change_does_not_reparse_mount_files(
    make_app, make_host_project, tmp_path
):
    """When the host's toctree changes to reference a different set of
    mount entries, Sphinx re-reads only the host doc — the mount files
    themselves are NOT re-parsed because their mtimes are unchanged.

    This documents Sphinx's actual incremental-build behaviour. Sphinx
    re-resolves cross-references against the cached mount doctrees,
    which is enough to surface the new toctree state in the rendered
    host HTML; the expensive parse step is correctly skipped for
    files that did not change. (If you expected the mount files to be
    re-parsed when the host's toctree is edited: that is not how
    Sphinx incremental builds work, and it is the right design —
    re-parsing unchanged files would defeat the cache.)
    """
    # Custom flat bundle with two independent files (no internal
    # toctree, no cross-refs). Lets us toggle each as a host-toctree
    # entry without worrying about transitive inclusion via the mount's
    # own ``index.rst``.
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "foo.rst").write_text("Foo\n===\n\nFOO_MARKER\n", encoding="utf-8")
    (bundle / "bar.rst").write_text("Bar\n===\n\nBAR_MARKER\n", encoding="utf-8")

    host = make_host_project()
    write_ubproject_toml(host, [{"dir": str(bundle), "mount_at": "_generated/m"}])
    # Cold: host toctree references foo only (bar is mounted but
    # orphan — Sphinx logs the standard ``toc.not_included`` warning,
    # which is fine without ``-W``).
    _replace_index_toctree(host, "_generated/m/foo")

    app = make_app(srcdir=host, freshenv=True)
    app.build()
    cold_html = (Path(app.outdir) / "index.html").read_text(encoding="utf-8")
    assert "_generated/m/foo.html" in cold_html

    offset = len(app._status.getvalue())

    # Edit host index.rst — toctree now references foo AND bar.
    _replace_index_toctree(host, "_generated/m/foo", "_generated/m/bar")
    _bump_mtime(host / "index.rst")

    app.build()
    warm_log = app._status.getvalue()[offset:]
    warm_html = (Path(app.outdir) / "index.html").read_text(encoding="utf-8")

    read = _docs_read_in_log(warm_log)

    # The host doc was re-read (mtime changed).
    assert "index" in read, f"host index not re-read; read={read}"
    # The mount files were NOT re-parsed — their mtimes did not change.
    assert "_generated/m/foo" not in read, f"foo re-parsed; read={read}"
    assert "_generated/m/bar" not in read, f"bar re-parsed; read={read}"

    # ...yet the new toctree state is reflected in the host's HTML.
    assert "_generated/m/foo.html" in warm_html
    assert "_generated/m/bar.html" in warm_html


def test_incremental_rereads_mount_doc_when_dependency_changes(
    make_app, make_host_project, tmp_path
):
    """A mounted doc that pulls in a sibling file via ``literalinclude`` is
    re-read when that *included* file changes — even though the doc's own
    source is untouched.

    This exercises a different change-detection path than
    :func:`test_incremental_only_reads_changed_mount_file`: the mounted
    doc's own mtime does not move, so the re-read is driven solely by
    Sphinx's dependency-mtime check (``env.dependencies``). It works for
    mounted docs because the include target is recorded with its absolute
    external path, which ``BuildEnvironment._has_doc_changed`` stats
    directly on each build."""
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    snippet = bundle / "snippet.py"
    # Use distinct single-token identifiers per version: Pygments wraps each
    # token in its own <span>, so a bare identifier survives verbatim in the
    # HTML while a multi-token string like "X = 2" would not.
    snippet.write_text("SNIP_OLD = 1\n", encoding="utf-8")
    (bundle / "index.rst").write_text(
        "Bundle\n======\n\n.. literalinclude:: snippet.py\n", encoding="utf-8"
    )

    host = make_host_project()
    write_ubproject_toml(host, [{"dir": str(bundle), "mount_at": "_generated/m"}])
    _replace_index_toctree(host, "_generated/m/index")

    app = make_app(srcdir=host, freshenv=True)
    app.build()

    # Precondition: the include target is a recorded dependency of the
    # mounted doc, pointing at the external file (not into the host srcdir).
    # Without this, a "re-read" below could be a false positive unrelated
    # to the dependency path under test.
    srcdir = Path(app.srcdir)
    deps = {
        (srcdir / d).resolve()
        for d in app.env.dependencies.get("_generated/m/index", ())
    }
    assert snippet.resolve() in deps, (
        f"include target not recorded as dependency; deps={deps}"
    )

    offset = len(app._status.getvalue())

    # Change ONLY the included file; the mounted doc's own source (and
    # therefore its own mtime) is left untouched.
    snippet.write_text("SNIP_NEW = 1\n", encoding="utf-8")
    _bump_mtime(snippet)

    app.build()
    warm_log = app._status.getvalue()[offset:]
    read = _docs_read_in_log(warm_log)

    assert "_generated/m/index" in read, (
        f"mounted doc not re-read after its dependency changed; read={read}"
    )
    # The re-read really re-rendered with the new content (and dropped the old).
    html = (Path(app.outdir) / "_generated" / "m" / "index.html").read_text(
        encoding="utf-8"
    )
    assert "SNIP_NEW" in html, "rebuilt HTML missing new dependency content"
    assert "SNIP_OLD" not in html, "rebuilt HTML still shows stale dependency content"


def test_incremental_rereads_changed_file_in_file_list_mount(
    make_app, make_host_project, tmp_path
):
    """File-list-mode mounts get the same mtime-based re-read as directory
    mounts: editing one listed file re-reads exactly that doc on the next
    build, and leaves the sibling untouched. Guards parity between the two
    mount-attach paths (``_attach_mount_files`` vs ``_attach_mount_dir``)."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    page_a = pkg / "page_a.rst"
    page_b = pkg / "page_b.rst"
    page_a.write_text("Page A\n======\n\nA_MARKER\n", encoding="utf-8")
    page_b.write_text("Page B\n======\n\nB_MARKER\n", encoding="utf-8")

    host = make_host_project()
    write_ubproject_toml(
        host, [{"files": [str(page_a), str(page_b)], "mount_at": "_generated/m"}]
    )
    _replace_index_toctree(host, "_generated/m/page_a", "_generated/m/page_b")

    app = make_app(srcdir=host, freshenv=True)
    app.build()
    offset = len(app._status.getvalue())

    page_a.write_text("Page A\n======\n\nA_MARKER_MODIFIED\n", encoding="utf-8")
    _bump_mtime(page_a)

    app.build()
    warm_log = app._status.getvalue()[offset:]
    read = _docs_read_in_log(warm_log)

    assert "_generated/m/page_a" in read, (
        f"edited file-list doc not re-read; read={read}"
    )
    assert "_generated/m/page_b" not in read, (
        f"unchanged file-list doc re-read; read={read}"
    )
