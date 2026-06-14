"""File-referencing directives inside a mounted bundle resolve relative to
the bundle root; the build fails when a reference escapes that root.

Covers literalinclude, include, csv-table :file:, raw :file:, image,
figure, graphviz, uml, mermaid, plus the path_check enforcement. The tests
are renderer-independent: mermaid uses 'raw' output, and graphviz/uml are
asserted via the recorded dependency rather than the rendered image, so no
mmdc/java/dot binary is required.
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import struct
from typing import TYPE_CHECKING
import zlib

import pytest

from tests.conftest import write_ubproject_toml

if TYPE_CHECKING:
    from sphinx.testing.util import SphinxTestApp


def _build(make_app, host: Path) -> SphinxTestApp:
    """Build the host project and return the app (for env/outdir/warnings)."""
    app = make_app(srcdir=host, freshenv=True)
    app.build()
    return app


def _resolved_deps(app: SphinxTestApp, docname: str) -> list[Path]:
    """Resolve every recorded dependency of ``docname`` to an absolute path."""
    srcdir = Path(app.srcdir)
    return [(srcdir / dep).resolve() for dep in app.env.dependencies.get(docname, ())]


def _replace_index_toctree(host: Path, *docnames: str) -> None:
    """Rewrite host index.rst with a toctree referencing the given docnames."""
    body = "Host project\n============\n\n.. toctree::\n   :maxdepth: 2\n\n"
    for d in docnames:
        body += f"   {d}\n"
    (host / "index.rst").write_text(body, encoding="utf-8")


def _add_extensions(host: Path, *exts: str) -> None:
    """Append extra extensions to the host conf.py extensions list."""
    conf = host / "conf.py"
    text = conf.read_text(encoding="utf-8")
    joined = ", ".join(f'"{e}"' for e in exts)
    conf.write_text(
        text.replace(
            'extensions = ["sphinx_mounts"]',
            f'extensions = ["sphinx_mounts", {joined}]',
        ),
        encoding="utf-8",
    )


def _append_conf(host: Path, line: str) -> None:
    """Append a single config line to the host conf.py."""
    conf = host / "conf.py"
    conf.write_text(conf.read_text(encoding="utf-8") + f"\n{line}\n", encoding="utf-8")


def _tiny_png(rgb: tuple[int, int, int] = (0xFF, 0x00, 0x00)) -> bytes:
    """A minimal 1x1 PNG of the given color, built with the stdlib (no Pillow
    dependency). The default (red) is byte-for-byte the original fixture;
    passing a different color yields genuinely different bytes, used to
    simulate an edited image between incremental builds."""

    def chunk(name: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + name
            + data
            + struct.pack(">I", zlib.crc32(name + data))
        )

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    idat = zlib.compress(bytes((0x00, *rgb)))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", idat)
        + chunk(b"IEND", b"")
    )


# ---------- Task 3: discovery records docname -> (root, path_check) ----------


def test_doc_roots_records_bundle_root_and_path_check(
    make_app, make_host_project, tmp_path
):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "index.rst").write_text("Bundle\n======\n", encoding="utf-8")

    host = make_host_project()
    write_ubproject_toml(host, [{"dir": str(bundle), "mount_at": "_g/api"}])
    _replace_index_toctree(host, "_g/api/index")

    app = _build(make_app, host)

    roots = app.env.project._doc_roots
    assert roots["_g/api/index"] == (bundle.resolve(), "error")


def test_doc_roots_files_mode_uses_file_parent_dir(
    make_app, make_host_project, tmp_path
):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "page.rst").write_text("Page\n====\n", encoding="utf-8")

    host = make_host_project()
    write_ubproject_toml(
        host,
        [
            {
                "files": [str(pkg / "page.rst")],
                "mount_at": "_g/api",
                "path_check": "warn",
            }
        ],
    )
    _replace_index_toctree(host, "_g/api/page")

    app = _build(make_app, host)

    assert app.env.project._doc_roots["_g/api/page"] == (pkg.resolve(), "warn")


# ---------- Task 4: happy path — directives resolve inside the bundle ----------


TEXT_CASES = [
    pytest.param(
        ".. literalinclude:: snippet.py\n",
        "snippet.py",
        "SNIP_MARKER = 1\n",
        "SNIP_MARKER",
        id="literalinclude",
    ),
    pytest.param(
        ".. include:: inc.txt\n",
        "inc.txt",
        "Included\n--------\n\nINC_MARKER\n",
        "INC_MARKER",
        id="include",
    ),
    pytest.param(
        ".. csv-table::\n   :file: data.csv\n",
        "data.csv",
        "h1,h2\nCSV_MARKER,2\n",
        "CSV_MARKER",
        id="csv-table-file",
    ),
    pytest.param(
        ".. raw:: html\n   :file: snippet.html\n",
        "snippet.html",
        "<p>RAW_MARKER</p>\n",
        "RAW_MARKER",
        id="raw-file",
    ),
]


@pytest.mark.parametrize(
    "directive_rst, target_name, target_content, marker", TEXT_CASES
)
def test_text_directive_reads_file_from_bundle(
    make_app,
    make_host_project,
    tmp_path,
    directive_rst,
    target_name,
    target_content,
    marker,
):
    """A relative file reference resolves to the file inside the bundle, and
    the recorded dependency points there (not into the host srcdir).

    ``inc.txt`` / ``snippet.html`` / ``data.csv`` / ``snippet.py`` all have
    extensions outside ``source_suffix``, so they are not discovered as docs
    of their own — only referenced by the directive.
    """
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / target_name).write_text(target_content, encoding="utf-8")
    (bundle / "index.rst").write_text(
        f"Bundle\n======\n\n{directive_rst}", encoding="utf-8"
    )

    host = make_host_project()
    write_ubproject_toml(host, [{"dir": str(bundle), "mount_at": "_g/api"}])
    _replace_index_toctree(host, "_g/api/index")

    app = _build(make_app, host)

    html = (Path(app.outdir) / "_g" / "api" / "index.html").read_text(encoding="utf-8")
    assert marker in html
    assert (bundle / target_name).resolve() in _resolved_deps(app, "_g/api/index")


def test_literalinclude_prefers_bundle_over_host_decoy(
    make_app, make_host_project, tmp_path
):
    """With a same-named decoy in the host srcdir, the bundle's file wins —
    proving resolution is relative to the bundle, not the host srcdir."""
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "snippet.py").write_text("BUNDLE_REAL = 1\n", encoding="utf-8")
    (bundle / "index.rst").write_text(
        "Bundle\n======\n\n.. literalinclude:: snippet.py\n", encoding="utf-8"
    )

    host = make_host_project()
    # Decoy at the same relative name; .py is not a source suffix, so it is
    # not picked up as a doc.
    (host / "snippet.py").write_text("HOST_DECOY = 0\n", encoding="utf-8")
    write_ubproject_toml(host, [{"dir": str(bundle), "mount_at": "_g/api"}])
    _replace_index_toctree(host, "_g/api/index")

    app = _build(make_app, host)

    html = (Path(app.outdir) / "_g" / "api" / "index.html").read_text(encoding="utf-8")
    assert "BUNDLE_REAL" in html
    assert "HOST_DECOY" not in html


def test_image_and_figure_resolve_within_bundle(make_app, make_host_project, tmp_path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "pic.png").write_bytes(_tiny_png())
    (bundle / "index.rst").write_text(
        "Bundle\n======\n\n"
        ".. image:: pic.png\n\n"
        ".. figure:: pic.png\n\n"
        "   A caption.\n",
        encoding="utf-8",
    )

    host = make_host_project()
    write_ubproject_toml(host, [{"dir": str(bundle), "mount_at": "_g/api"}])
    _replace_index_toctree(host, "_g/api/index")

    app = _build(make_app, host)

    assert (bundle / "pic.png").resolve() in _resolved_deps(app, "_g/api/index")
    assert (Path(app.outdir) / "_images").is_dir()


def test_graphviz_file_resolves_within_bundle(make_app, make_host_project, tmp_path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "g.dot").write_text("digraph { A -> B }\n", encoding="utf-8")
    (bundle / "index.rst").write_text(
        "Bundle\n======\n\n.. graphviz:: g.dot\n", encoding="utf-8"
    )

    host = make_host_project()
    _add_extensions(host, "sphinx.ext.graphviz")
    write_ubproject_toml(host, [{"dir": str(bundle), "mount_at": "_g/api"}])
    _replace_index_toctree(host, "_g/api/index")

    app = _build(make_app, host)

    assert (bundle / "g.dot").resolve() in _resolved_deps(app, "_g/api/index")
    assert "not found" not in app._warning.getvalue()


def test_uml_file_resolves_within_bundle(make_app, make_host_project, tmp_path):
    pytest.importorskip("sphinxcontrib.plantuml")
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "d.puml").write_text("@startuml\nA -> B\n@enduml\n", encoding="utf-8")
    (bundle / "index.rst").write_text(
        "Bundle\n======\n\n.. uml:: d.puml\n", encoding="utf-8"
    )

    host = make_host_project()
    _add_extensions(host, "sphinxcontrib.plantuml")
    write_ubproject_toml(host, [{"dir": str(bundle), "mount_at": "_g/api"}])
    _replace_index_toctree(host, "_g/api/index")

    app = _build(make_app, host)

    assert (bundle / "d.puml").resolve() in _resolved_deps(app, "_g/api/index")
    assert "not found" not in app._warning.getvalue()


def test_mermaid_file_resolves_within_bundle(make_app, make_host_project, tmp_path):
    pytest.importorskip("sphinxcontrib.mermaid")
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "f.mmd").write_text("graph TD\n  A[MERMAID_MARKER]\n", encoding="utf-8")
    (bundle / "index.rst").write_text(
        "Bundle\n======\n\n.. mermaid:: f.mmd\n", encoding="utf-8"
    )

    host = make_host_project()
    _add_extensions(host, "sphinxcontrib.mermaid")
    _append_conf(host, "mermaid_output_format = 'raw'")
    write_ubproject_toml(host, [{"dir": str(bundle), "mount_at": "_g/api"}])
    _replace_index_toctree(host, "_g/api/index")

    app = _build(make_app, host)

    assert (bundle / "f.mmd").resolve() in _resolved_deps(app, "_g/api/index")
    assert "not found" not in app._warning.getvalue()
    html = (Path(app.outdir) / "_g" / "api" / "index.html").read_text(encoding="utf-8")
    assert "MERMAID_MARKER" in html


# ---------- Task 5: enforcement (path_check) ----------


def _leaking_literalinclude_bundle(tmp_path: Path, ref: str) -> Path:
    """A directory bundle whose index.rst literalinclude's ``ref``."""
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "index.rst").write_text(
        f"Bundle\n======\n\n.. literalinclude:: {ref}\n", encoding="utf-8"
    )
    return bundle


def test_escape_via_leading_slash_fails_by_default(
    make_app, make_host_project, tmp_path
):
    """A leading-slash reference resolves to the host srcdir (outside the
    bundle); the default path_check='error' fails the build."""
    bundle = _leaking_literalinclude_bundle(tmp_path, "/host_secret.py")
    host = make_host_project()
    (host / "host_secret.py").write_text("HOST_SECRET = 1\n", encoding="utf-8")
    write_ubproject_toml(host, [{"dir": str(bundle), "mount_at": "_g/api"}])
    _replace_index_toctree(host, "_g/api/index")

    with pytest.raises(Exception, match=r"outside its bundle root"):
        app = make_app(srcdir=host, freshenv=True)
        app.build()


def test_escape_via_parent_climb_fails_by_default(
    make_app, make_host_project, tmp_path
):
    """A ``../`` reference that climbs above the bundle root fails by default."""
    bundle = tmp_path / "bundle"
    (bundle / "sub").mkdir(parents=True)
    (tmp_path / "outside.py").write_text("OUTSIDE = 1\n", encoding="utf-8")
    (bundle / "sub" / "page.rst").write_text(
        "Page\n====\n\n.. literalinclude:: ../../outside.py\n", encoding="utf-8"
    )
    (bundle / "index.rst").write_text(
        "Idx\n===\n\n.. toctree::\n\n   sub/page\n", encoding="utf-8"
    )
    host = make_host_project()
    write_ubproject_toml(host, [{"dir": str(bundle), "mount_at": "_g/api"}])
    _replace_index_toctree(host, "_g/api/index")

    with pytest.raises(Exception, match=r"outside its bundle root"):
        app = make_app(srcdir=host, freshenv=True)
        app.build()


def test_enforcement_is_directive_agnostic_include(
    make_app, make_host_project, tmp_path
):
    """A docutils-native ``include`` that climbs out is caught too — the
    check keys off env.dependencies, not the directive type."""
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (tmp_path / "outside_inc.txt").write_text(
        "Outside\n-------\n\nOUTSIDE_INC\n", encoding="utf-8"
    )
    (bundle / "index.rst").write_text(
        "Bundle\n======\n\n.. include:: ../outside_inc.txt\n", encoding="utf-8"
    )
    host = make_host_project()
    write_ubproject_toml(host, [{"dir": str(bundle), "mount_at": "_g/api"}])
    _replace_index_toctree(host, "_g/api/index")

    with pytest.raises(Exception, match=r"outside its bundle root"):
        app = make_app(srcdir=host, freshenv=True)
        app.build()


def test_path_check_warn_emits_warning_not_error(make_app, make_host_project, tmp_path):
    bundle = _leaking_literalinclude_bundle(tmp_path, "/host_secret.py")
    host = make_host_project()
    (host / "host_secret.py").write_text("HOST_SECRET = 1\n", encoding="utf-8")
    write_ubproject_toml(
        host, [{"dir": str(bundle), "mount_at": "_g/api", "path_check": "warn"}]
    )
    _replace_index_toctree(host, "_g/api/index")

    app = _build(make_app, host)  # must NOT raise

    assert "outside its bundle root" in app._warning.getvalue()


def test_path_check_off_allows_escape(make_app, make_host_project, tmp_path):
    bundle = _leaking_literalinclude_bundle(tmp_path, "/host_secret.py")
    host = make_host_project()
    (host / "host_secret.py").write_text("HOST_SECRET = 1\n", encoding="utf-8")
    write_ubproject_toml(
        host, [{"dir": str(bundle), "mount_at": "_g/api", "path_check": "off"}]
    )
    _replace_index_toctree(host, "_g/api/index")

    app = _build(make_app, host)

    assert "outside its bundle root" not in app._warning.getvalue()
    # The leaked host file content really did render (documents the leak).
    html = (Path(app.outdir) / "_g" / "api" / "index.html").read_text(encoding="utf-8")
    assert "HOST_SECRET" in html


def test_self_contained_bundle_passes_under_default_error(
    make_app, make_host_project, tmp_path
):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "snippet.py").write_text("OK = 1\n", encoding="utf-8")
    (bundle / "index.rst").write_text(
        "Bundle\n======\n\n.. literalinclude:: snippet.py\n", encoding="utf-8"
    )
    host = make_host_project()
    write_ubproject_toml(host, [{"dir": str(bundle), "mount_at": "_g/api"}])
    _replace_index_toctree(host, "_g/api/index")

    app = _build(make_app, host)

    assert "outside its bundle root" not in app._warning.getvalue()


def test_files_mode_escape_fails(make_app, make_host_project, tmp_path):
    """In file-list mode the bundle root is the listed file's parent dir."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (tmp_path / "secret.py").write_text("SECRET = 1\n", encoding="utf-8")  # outside pkg
    (pkg / "page.rst").write_text(
        "Page\n====\n\n.. literalinclude:: ../secret.py\n", encoding="utf-8"
    )
    host = make_host_project()
    write_ubproject_toml(
        host, [{"files": [str(pkg / "page.rst")], "mount_at": "_g/api"}]
    )
    _replace_index_toctree(host, "_g/api/page")

    with pytest.raises(Exception, match=r"outside its bundle root"):
        app = make_app(srcdir=host, freshenv=True)
        app.build()


# ---------- Task 6: leak boundaries (documented with path_check='off') ----------


def test_leading_slash_resolves_to_host_srcdir_not_bundle(
    make_app, make_host_project, tmp_path
):
    """Documents that a leading-slash path is 'absolute from the source
    root' = the HOST srcdir, not the bundle. This is why such a reference
    is an escape."""
    bundle = _leaking_literalinclude_bundle(tmp_path, "/host_secret.py")
    host = make_host_project()
    (host / "host_secret.py").write_text("HOST_SECRET = 1\n", encoding="utf-8")
    write_ubproject_toml(
        host, [{"dir": str(bundle), "mount_at": "_g/api", "path_check": "off"}]
    )
    _replace_index_toctree(host, "_g/api/index")

    app = _build(make_app, host)

    deps = _resolved_deps(app, "_g/api/index")
    assert (host / "host_secret.py").resolve() in deps
    assert (bundle / "host_secret.py").resolve() not in deps


def test_parent_climb_escapes_bundle_root(make_app, make_host_project, tmp_path):
    """Documents that ``../`` climbing above the bundle root resolves to a
    path outside the bundle."""
    bundle = tmp_path / "bundle"
    (bundle / "sub").mkdir(parents=True)
    (tmp_path / "outside.py").write_text("OUTSIDE = 1\n", encoding="utf-8")
    (bundle / "sub" / "page.rst").write_text(
        "Page\n====\n\n.. literalinclude:: ../../outside.py\n", encoding="utf-8"
    )
    (bundle / "index.rst").write_text(
        "Idx\n===\n\n.. toctree::\n\n   sub/page\n", encoding="utf-8"
    )
    host = make_host_project()
    write_ubproject_toml(
        host, [{"dir": str(bundle), "mount_at": "_g/api", "path_check": "off"}]
    )
    _replace_index_toctree(host, "_g/api/index")

    app = _build(make_app, host)

    deps = _resolved_deps(app, "_g/api/sub/page")
    assert (tmp_path / "outside.py").resolve() in deps
    # The escaped path is a sibling of the bundle, not under it.
    bundle_root = bundle.resolve()
    assert all(
        d != bundle_root and bundle_root not in d.parents
        for d in deps
        if d.name == "outside.py"
    )


def test_path_check_is_resolved_per_mount(make_app, make_host_project, tmp_path):
    """Two mounts, different path_check values, resolved independently: an
    'off' mount with an escaping reference is allowed, while a sibling
    'error' mount (self-contained) does not fire on the other mount's docs.
    Proves the check keys off each doc's own mount, not a global setting."""
    # Mount A: escapes its bundle root, but path_check='off' allows it.
    a = tmp_path / "a"
    a.mkdir()
    (tmp_path / "a_escape.py").write_text("A_ESCAPE = 1\n", encoding="utf-8")
    (a / "index.rst").write_text(
        "A\n=\n\n.. literalinclude:: ../a_escape.py\n", encoding="utf-8"
    )
    # Mount B: self-contained, path_check='error'.
    b = tmp_path / "b"
    b.mkdir()
    (b / "snippet.py").write_text("B_OK = 1\n", encoding="utf-8")
    (b / "index.rst").write_text(
        "B\n=\n\n.. literalinclude:: snippet.py\n", encoding="utf-8"
    )

    host = make_host_project()
    write_ubproject_toml(
        host,
        [
            {"dir": str(a), "mount_at": "_g/a", "path_check": "off"},
            {"dir": str(b), "mount_at": "_g/b", "path_check": "error"},
        ],
    )
    _replace_index_toctree(host, "_g/a/index", "_g/b/index")

    app = _build(make_app, host)  # must NOT raise — A's escape allowed by A's own 'off'

    assert "outside its bundle root" not in app._warning.getvalue()
    # A's escaped content really rendered (the 'off' mount was not blocked).
    a_html = (Path(app.outdir) / "_g" / "a" / "index.html").read_text(encoding="utf-8")
    assert "A_ESCAPE" in a_html


# ---------- Task 7: a changed include target re-reads the mounted doc ----------


def _bump_mtime(p: Path, seconds: float = 60.0) -> None:
    """Push ``p``'s mtime forward to defeat coarse filesystem mtime
    resolution. Linux ``ext4`` + ``relatime`` and macOS HFS+ can report
    whole-second precision; without this, two writes within the same second
    can leave Sphinx thinking nothing changed."""
    bump = p.stat().st_mtime + seconds
    os.utime(p, (bump, bump))


_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


def _docs_read_in_log(log: str) -> set[str]:
    """Extract the set of docnames Sphinx reports as ``reading sources...``
    in a build log (ANSI codes and the ``[NN%]`` progress marker stripped)."""
    plain = _ANSI_ESCAPE_RE.sub("", log)
    read: set[str] = set()
    for line in plain.splitlines():
        idx = line.find("reading sources...")
        if idx == -1:
            continue
        after = line[idx + len("reading sources...") :]
        after = re.sub(r"^\s*\[\s*\d+%?\s*\]\s*", "", after)
        doc = after.strip()
        if doc:
            read.add(doc)
    return read


def _write_payload(path: Path, content: str | bytes) -> None:
    """Write ``content`` to ``path`` as bytes or text depending on its type."""
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")


_RED_PNG = _tiny_png((0xFF, 0x00, 0x00))
_GREEN_PNG = _tiny_png((0x00, 0xFF, 0x00))


# Every file-referencing directive the bundle path tests cover, each paired
# with an "old" and a "new" payload for its target file. Extra ``extensions``
# / ``conf_lines`` are applied to the host conf.py; ``requires`` names a module
# to ``importorskip``. Cases mirror TEXT_CASES and the diagram tests above.
REREAD_CASES = [
    pytest.param(
        ".. literalinclude:: snippet.py\n",
        "snippet.py",
        "LIT_OLD = 1\n",
        "LIT_NEW = 1\n",
        (),
        (),
        None,
        id="literalinclude",
    ),
    pytest.param(
        ".. include:: inc.txt\n",
        "inc.txt",
        "INC_OLD\n",
        "INC_NEW\n",
        (),
        (),
        None,
        id="include",
    ),
    pytest.param(
        ".. csv-table::\n   :file: data.csv\n",
        "data.csv",
        "h1,h2\nOLD,2\n",
        "h1,h2\nNEW,2\n",
        (),
        (),
        None,
        id="csv-table-file",
    ),
    pytest.param(
        ".. raw:: html\n   :file: snippet.html\n",
        "snippet.html",
        "<p>RAW_OLD</p>\n",
        "<p>RAW_NEW</p>\n",
        (),
        (),
        None,
        id="raw-file",
    ),
    pytest.param(
        ".. image:: pic.png\n",
        "pic.png",
        _RED_PNG,
        _GREEN_PNG,
        (),
        (),
        None,
        id="image",
    ),
    pytest.param(
        ".. figure:: pic.png\n\n   A caption.\n",
        "pic.png",
        _RED_PNG,
        _GREEN_PNG,
        (),
        (),
        None,
        id="figure",
    ),
    pytest.param(
        ".. graphviz:: g.dot\n",
        "g.dot",
        "digraph { A -> B }\n",
        "digraph { A -> C }\n",
        ("sphinx.ext.graphviz",),
        (),
        None,
        id="graphviz",
    ),
    pytest.param(
        ".. uml:: d.puml\n",
        "d.puml",
        "@startuml\nA -> B\n@enduml\n",
        "@startuml\nA -> C\n@enduml\n",
        ("sphinxcontrib.plantuml",),
        (),
        "sphinxcontrib.plantuml",
        id="uml",
    ),
    pytest.param(
        ".. mermaid:: f.mmd\n",
        "f.mmd",
        "graph TD\n  A[XX]\n",
        "graph TD\n  A[YY]\n",
        ("sphinxcontrib.mermaid",),
        ("mermaid_output_format = 'raw'",),
        "sphinxcontrib.mermaid",
        id="mermaid",
    ),
]


@pytest.mark.parametrize(
    "directive_rst, target_name, old_content, new_content, extensions, conf_lines, requires",
    REREAD_CASES,
)
def test_changed_include_target_rereads_mounted_doc(
    make_app,
    make_host_project,
    tmp_path,
    directive_rst,
    target_name,
    old_content,
    new_content,
    extensions,
    conf_lines,
    requires,
):
    """For every file-referencing directive, editing the *referenced* file
    re-reads the mounted doc on the next incremental build — even though the
    mounted doc's own source (and mtime) is untouched.

    Each directive records its target in ``env.dependencies`` with the
    target's absolute external path (asserted as a precondition below), so
    Sphinx's dependency-mtime check re-reads the doc when that file changes.
    This locks the behaviour in across the whole file-referencing directive
    set, not just ``literalinclude``."""
    if requires is not None:
        pytest.importorskip(requires)

    bundle = tmp_path / "bundle"
    bundle.mkdir()
    _write_payload(bundle / target_name, old_content)
    (bundle / "index.rst").write_text(
        f"Bundle\n======\n\n{directive_rst}", encoding="utf-8"
    )

    host = make_host_project()
    if extensions:
        _add_extensions(host, *extensions)
    for line in conf_lines:
        _append_conf(host, line)
    write_ubproject_toml(host, [{"dir": str(bundle), "mount_at": "_generated/m"}])
    _replace_index_toctree(host, "_generated/m/index")

    app = make_app(srcdir=host, freshenv=True)
    app.build()

    # Precondition (teeth): the directive recorded its target as a dependency
    # of the mounted doc, pointing at the external file. Without this, a later
    # "re-read" could be a false positive unrelated to the file we change.
    target = (bundle / target_name).resolve()
    assert target in _resolved_deps(app, "_generated/m/index"), (
        f"{target_name} was not recorded as a dependency of the mounted doc"
    )

    offset = len(app._status.getvalue())

    # Change ONLY the referenced file; the mounted doc's own source is left
    # untouched, so any re-read must be driven by the dependency-mtime check.
    _write_payload(bundle / target_name, new_content)
    _bump_mtime(bundle / target_name)

    app.build()
    read = _docs_read_in_log(app._status.getvalue()[offset:])

    assert "_generated/m/index" in read, (
        f"mounted doc not re-read after its {target_name} dependency changed; "
        f"read={read}"
    )
