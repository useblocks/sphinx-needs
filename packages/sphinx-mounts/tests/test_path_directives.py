"""File-referencing directives inside a mounted bundle resolve relative to
the bundle root; the build fails when a reference escapes that root.

Covers literalinclude, include, csv-table :file:, raw :file:, image,
figure, graphviz, uml, mermaid, the three Sphinx-Needs directives that take a
doc-relative path (needimport, needreport, needuml), plus the path_check
enforcement. The graphviz/uml cases render for real and **hard-require**
their renderers — the full mounts chain, render included, must be
exercised rather than silently skipped when one is missing. ``dot`` has to be
on ``PATH``; PlantUML is taken either from a ``plantuml`` executable on
``PATH`` or, when ``PLANTUML_JAR`` names one, from a plantuml jar run through
``java`` (which is how CI supplies it — see ``.github/workflows/ci.yaml`` and
the package's ``AGENTS.md``). Mermaid uses 'raw'
output, so no mmdc is needed. The needuml ``!include`` case renders for
real too, since PlantUML resolves that path itself and records no Sphinx
dependency.
"""

from __future__ import annotations

import importlib
import json
import os
import re
import shutil
import struct
import zlib
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import sphinx
from sphinx.errors import ExtensionError

from tests.conftest import count_mount_warnings, count_warnings, write_ubproject_toml

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

    recorded = app.env.project._doc_roots["_g/api/index"]
    # A directory mount has exactly one root: its own dir.
    assert recorded.roots == (bundle.resolve(),)
    # The default, which is "warn".
    assert recorded.path_check == "warn"
    # The mount's label travels with the roots so an escape message can name
    # the mount whose config has to change.
    assert recorded.label == f"mounts[0] (dir={bundle.resolve()})"


def test_doc_roots_files_mode_uses_the_union_of_listed_parents(
    make_app, make_host_project, tmp_path
):
    """A file-list mount's root SET is the parent directory of every listed
    file, and every document of the mount shares the whole set.

    Confining each document to its own file's parent made the ``path_check``
    verdict depend on how deep a file sat — see
    ``test_files_mode_sibling_reference_within_the_mounts_roots_is_allowed``.
    Collapsing to the listed files' common ancestor fixed that but admitted
    directories the mount never named — see
    ``test_files_mode_reference_into_the_unlisted_shared_parent_is_flagged``.
    """
    pkg = tmp_path / "pkg"
    (pkg / "notes").mkdir(parents=True)
    (pkg / "index.rst").write_text("Index\n=====\n", encoding="utf-8")
    (pkg / "notes" / "page.rst").write_text("Page\n====\n", encoding="utf-8")

    host = make_host_project()
    write_ubproject_toml(
        host,
        [
            {
                "files": [str(pkg / "index.rst"), str(pkg / "notes" / "page.rst")],
                "mount_at": "_g/api",
                "path_check": "warn",
            }
        ],
    )
    _replace_index_toctree(host, "_g/api/index", "_g/api/page")

    app = _build(make_app, host)

    roots = app.env.project._doc_roots
    expected = (pkg.resolve(), (pkg / "notes").resolve())
    # Both docs carry the whole set, in ``files`` order.
    assert roots["_g/api/index"].roots == expected
    assert roots["_g/api/page"].roots == expected
    assert roots["_g/api/page"].path_check == "warn"


def test_doc_roots_single_file_mount_root_is_its_parent(
    make_app, make_host_project, tmp_path
):
    """Edge case of the union rule: one listed file contributes exactly one
    root, its own parent directory — the behaviour a single-file mount always
    had."""
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

    recorded = app.env.project._doc_roots["_g/api/page"]
    assert recorded.roots == (pkg.resolve(),)
    assert recorded.path_check == "warn"


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
    _require_renderer(".. graphviz:: g.dot\n")
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
    assert count_warnings(app) == 0, app._warning.getvalue()


def test_uml_file_resolves_within_bundle(make_app, make_host_project, tmp_path):
    pytest.importorskip("sphinxcontrib.plantuml")
    _require_renderer(".. uml:: d.puml\n")
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "d.puml").write_text("@startuml\nA -> B\n@enduml\n", encoding="utf-8")
    (bundle / "index.rst").write_text(
        "Bundle\n======\n\n.. uml:: d.puml\n", encoding="utf-8"
    )

    host = make_host_project()
    _add_extensions(host, "sphinxcontrib.plantuml")
    for line in _plantuml_extra_conf():
        _append_conf(host, line)
    write_ubproject_toml(host, [{"dir": str(bundle), "mount_at": "_g/api"}])
    _replace_index_toctree(host, "_g/api/index")

    app = _build(make_app, host)

    assert (bundle / "d.puml").resolve() in _resolved_deps(app, "_g/api/index")
    assert count_warnings(app) == 0, app._warning.getvalue()


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


# ---------- Sphinx-Needs: its three doc-relative file references ----------
#
# Sphinx-Needs is what the ``showcase/needs`` bundle exercises, and it resolves
# paths in two different ways. ``needimport`` and ``needreport`` go through
# Sphinx's ``relfn2path``, like the directives above. ``needuml`` / ``needarch``
# do not: ``!include`` is handled inside the PlantUML process, whose working
# directory Sphinx-Needs derives from the document's source file — so it needs
# its own coverage, and it is the one case that records no Sphinx dependency
# (hence no ``_resolved_deps`` assertion for it).


def _needs_host(
    make_host_project,
    *extra_extensions: str,
    conf_lines: tuple[str, ...] = (),
) -> Path:
    """A host project with sphinx-needs loaded and explicit need IDs required.

    ``_add_extensions`` rewrites the pristine ``extensions = ["sphinx_mounts"]``
    line, so it works only once per project — every extension this host needs
    must be passed in the same call.
    """
    host = make_host_project()
    _add_extensions(host, "sphinx_needs", *extra_extensions)
    _append_conf(host, "needs_id_required = True")
    for line in conf_lines:
        _append_conf(host, line)
    return host


def test_needimport_resolves_needs_json_within_bundle(
    make_app, make_host_project, tmp_path
):
    """``needimport`` addresses its needs.json relative to the importing doc."""
    _require_sphinx_needs()
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "needs.json").write_text(
        json.dumps(
            {
                "project": "upstream",
                "current_version": "1.0",
                "versions": {
                    "1.0": {
                        "needs": {
                            "IMPORTED_REQ": {
                                "id": "IMPORTED_REQ",
                                "type": "req",
                                "title": "NEEDIMPORT_MARKER",
                                "docname": "index",
                            }
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    (bundle / "index.rst").write_text(
        "Bundle\n======\n\n.. needimport:: needs.json\n", encoding="utf-8"
    )

    host = _needs_host(make_host_project)
    write_ubproject_toml(host, [{"dir": str(bundle), "mount_at": "_g/api"}])
    _replace_index_toctree(host, "_g/api/index")

    app = _build(make_app, host)

    html = (Path(app.outdir) / "_g" / "api" / "index.html").read_text(encoding="utf-8")
    assert "NEEDIMPORT_MARKER" in html
    # needimport notes the file as a dependency, so path_check can see it too.
    assert (bundle / "needs.json").resolve() in _resolved_deps(app, "_g/api/index")


def test_needreport_resolves_template_within_bundle(
    make_app, make_host_project, tmp_path
):
    """``needreport``'s ``:template:`` is relfn2path'd like needimport's arg."""
    _require_sphinx_needs()
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    # Kept out of the doc set by ``exclude``: Jinja input, not a page — but it
    # carries the conventional .rst suffix a directory mount would walk.
    (bundle / "report-template.rst").write_text(
        "NEEDREPORT_MARKER\n\n{% for t in types %}* {{ t.directive }}\n{% endfor %}\n",
        encoding="utf-8",
    )
    (bundle / "index.rst").write_text(
        "Bundle\n======\n\n.. needreport::\n   :types:\n"
        "   :template: report-template.rst\n",
        encoding="utf-8",
    )

    host = _needs_host(make_host_project)
    write_ubproject_toml(
        host,
        [
            {
                "dir": str(bundle),
                "mount_at": "_g/api",
                "exclude": ["report-template.rst"],
            }
        ],
    )
    _replace_index_toctree(host, "_g/api/index")

    app = _build(make_app, host)

    html = (Path(app.outdir) / "_g" / "api" / "index.html").read_text(encoding="utf-8")
    assert "NEEDREPORT_MARKER" in html
    # The excluded template is input, not a document: no page was published.
    assert not (Path(app.outdir) / "_g" / "api" / "report-template.html").exists()


def test_needuml_include_resolves_within_bundle(make_app, make_host_project, tmp_path):
    """``needuml``'s PlantUML ``!include`` resolves against the bundle root.

    The reference case for sphinx-needs
    `#1749 <https://github.com/useblocks/sphinx-needs/issues/1749>`__: the
    working directory PlantUML runs in must come from the document's physical
    source file, not from its logical docname, which does not exist on disk for
    a mounted document. Requires sphinx-needs > 8.3.0 to pass.

    The marker has to travel through the real PlantUML process into the
    rendered SVG, so unlike the other tests here this one needs the
    ``plantuml`` binary on PATH — and it is a hard requirement: without it
    the mounts chain is not really exercised.
    """
    _require_sphinx_needs()
    pytest.importorskip("sphinxcontrib.plantuml")
    _require_renderer(".. uml::\n")

    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "lib.puml").write_text(
        'component "NEEDUML_INCLUDE_MARKER" as Lib\n', encoding="utf-8"
    )
    (bundle / "index.rst").write_text(
        "Bundle\n======\n\n.. needuml::\n\n   !include lib.puml\n", encoding="utf-8"
    )

    host = _needs_host(
        make_host_project,
        "sphinxcontrib.plantuml",
        # The SVG path applies no scaling, so Pillow is not needed for the
        # ``scale`` attribute sphinx-needs stamps onto every diagram node.
        conf_lines=("plantuml_output_format = 'svg_img'", *_plantuml_extra_conf()),
    )
    write_ubproject_toml(host, [{"dir": str(bundle), "mount_at": "_g/api"}])
    _replace_index_toctree(host, "_g/api/index")

    app = _build(make_app, host)

    html = (Path(app.outdir) / "_g" / "api" / "index.html").read_text(encoding="utf-8")
    assert "PlantUML is not available" not in html
    assert "cannot be run" not in app._warning.getvalue()
    rendered = "\n".join(
        svg.read_text(encoding="utf-8")
        for svg in (Path(app.outdir) / "_images").glob("*.svg")
    )
    assert "NEEDUML_INCLUDE_MARKER" in rendered, (
        "the bundle-local lib.puml was not !include-d — PlantUML's working "
        "directory did not point at the bundle root"
    )


# ---------- Task 5: enforcement (path_check) ----------


def _leaking_literalinclude_bundle(tmp_path: Path, ref: str) -> Path:
    """A directory bundle whose index.rst literalinclude's ``ref``."""
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "index.rst").write_text(
        f"Bundle\n======\n\n.. literalinclude:: {ref}\n", encoding="utf-8"
    )
    return bundle


def test_escape_via_leading_slash_fails_at_path_check_error(
    make_app, make_host_project, tmp_path
):
    """A leading-slash reference resolves to the host srcdir (outside the
    bundle); ``path_check = "error"`` fails the build."""
    bundle = _leaking_literalinclude_bundle(tmp_path, "/host_secret.py")
    host = make_host_project()
    (host / "host_secret.py").write_text("HOST_SECRET = 1\n", encoding="utf-8")
    write_ubproject_toml(
        host, [{"dir": str(bundle), "mount_at": "_g/api", "path_check": "error"}]
    )
    _replace_index_toctree(host, "_g/api/index")

    with pytest.raises(Exception, match=r"outside its bundle root"):
        app = make_app(srcdir=host, freshenv=True)
        app.build()


def test_escape_via_parent_climb_fails_at_path_check_error(
    make_app, make_host_project, tmp_path
):
    """A ``../`` reference that climbs above the bundle root fails at
    ``path_check = "error"``."""
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
        host, [{"dir": str(bundle), "mount_at": "_g/api", "path_check": "error"}]
    )
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
    write_ubproject_toml(
        host, [{"dir": str(bundle), "mount_at": "_g/api", "path_check": "error"}]
    )
    _replace_index_toctree(host, "_g/api/index")

    with pytest.raises(Exception, match=r"outside its bundle root"):
        app = make_app(srcdir=host, freshenv=True)
        app.build()


def test_escape_at_the_default_path_check_warns_and_builds(
    make_app, make_host_project, tmp_path
):
    """With no ``path_check`` set, an escape is a warning and the build
    succeeds — and ``sphinx-build -W`` is what turns it into a failure.

    The default was ``"error"``, which fought this extension's own stated
    doctrine (every mount-specific problem is a typed, suppressible warning
    that ``-W`` escalates) and could not deliver the guarantee it implied
    anyway: the check runs from ``env-check-consistency``, which Sphinx skips
    on a build that reads no document, so a hard default was never a standing
    invariant.

    Asserted with no ``path_check`` key at all, so the *default* is what is
    under test rather than an explicit ``"warn"``.
    """
    bundle = _leaking_literalinclude_bundle(tmp_path, "../outside.txt")
    (tmp_path / "outside.txt").write_text("OUTSIDE_AT_DEFAULT\n", encoding="utf-8")
    host = make_host_project()
    write_ubproject_toml(host, [{"dir": str(bundle), "mount_at": "_g/api"}])
    _replace_index_toctree(host, "_g/api/index")

    app = _build(make_app, host)  # must NOT raise

    warnings = app._warning.getvalue()
    assert "mounts.path_escape" in warnings, warnings
    assert "outside its bundle root" in warnings, warnings
    assert count_mount_warnings(app) == 1, warnings
    # The build really completed: the page exists, unlike under "error".
    assert (Path(app.outdir) / "_g" / "api" / "index.html").exists()


def test_escape_at_the_default_path_check_is_suppressible(
    make_app, make_host_project, tmp_path
):
    """The default being a typed warning means it can be suppressed, which an
    abort could not be. That is the point of the doctrine it now follows."""
    bundle = _leaking_literalinclude_bundle(tmp_path, "../outside.txt")
    (tmp_path / "outside.txt").write_text("OUTSIDE\n", encoding="utf-8")
    host = make_host_project()
    conf = host / "conf.py"
    conf.write_text(
        conf.read_text(encoding="utf-8")
        + '\nsuppress_warnings = ["mounts.path_escape"]\n',
        encoding="utf-8",
    )
    write_ubproject_toml(host, [{"dir": str(bundle), "mount_at": "_g/api"}])
    _replace_index_toctree(host, "_g/api/index")

    app = _build(make_app, host)

    assert count_warnings(app) == 0, app._warning.getvalue()


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
    assert "mounts.path_escape" in app._warning.getvalue()
    assert count_warnings(app) == 1  # only the path_escape warning
    assert count_mount_warnings(app) == 1


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
    assert count_warnings(app) == 0
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
    """In file-list mode each listed file contributes its own parent directory
    as a root; with a single listed file that is the only root, so a ``../``
    reference still escapes."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (tmp_path / "secret.py").write_text("SECRET = 1\n", encoding="utf-8")  # outside pkg
    (pkg / "page.rst").write_text(
        "Page\n====\n\n.. literalinclude:: ../secret.py\n", encoding="utf-8"
    )
    host = make_host_project()
    write_ubproject_toml(
        host,
        [
            {
                "files": [str(pkg / "page.rst")],
                "mount_at": "_g/api",
                "path_check": "error",
            }
        ],
    )
    _replace_index_toctree(host, "_g/api/page")

    with pytest.raises(Exception, match=r"outside its bundle root"):
        app = make_app(srcdir=host, freshenv=True)
        app.build()


def test_files_mode_sibling_reference_within_the_mounts_roots_is_allowed(
    make_app, make_host_project, tmp_path
):
    """A deeper listed file may reference a file that sits inside the mount's
    own tree, above that file's own directory.

    This reproduces the shape of the project's own ``release-notes`` example:
    the mount lists ``index.rst`` and ``notes/2026-q1.rst``, so the bundle
    spans ``rn/``. A reference from ``index.rst`` *down* into ``notes/``
    always passed, while the mirror-image reference from
    ``notes/2026-q1.rst`` *up* to ``../shared.txt`` was rejected as leaving
    "the bundle root" — same mount, same tree, opposite verdicts purely
    because of which file was deeper. Both are inside the mount, so both must
    pass.
    """
    rn = tmp_path / "rn"
    (rn / "notes").mkdir(parents=True)
    (rn / "shared.txt").write_text("SHARED_TEXT\n", encoding="utf-8")
    (rn / "index.rst").write_text("RN index\n========\n", encoding="utf-8")
    (rn / "notes" / "2026-q1.rst").write_text(
        "Q1 notes\n========\n\n.. literalinclude:: ../shared.txt\n", encoding="utf-8"
    )

    host = make_host_project()
    write_ubproject_toml(
        host,
        [
            {
                "files": [str(rn / "index.rst"), str(rn / "notes" / "2026-q1.rst")],
                "mount_at": "_g/rn",
            }
        ],
    )
    _replace_index_toctree(host, "_g/rn/index", "_g/rn/2026-q1")

    app = _build(make_app, host)

    assert count_warnings(app) == 0, app._warning.getvalue()
    html = (Path(app.outdir) / "_g" / "rn" / "2026-q1.html").read_text(encoding="utf-8")
    assert "SHARED_TEXT" in html


def test_files_mode_reference_into_the_unlisted_shared_parent_is_flagged(
    make_app, make_host_project, tmp_path
):
    """A directory the mount never named must NOT become in-bundle, even when
    it is the shared parent of two listed files.

    This is the bound on the widening. Collapsing a file-list mount to the
    *common ancestor* of its listed files let the ``files`` list drive the root
    arbitrarily wide: two entries in sibling subtrees promoted their shared
    parent, so every file under it — here ``secret.txt``, which sits in
    neither listed directory — became reachable with no diagnostic at all,
    even at ``path_check = "error"``. Entries on unrelated filesystem
    branches promoted the root to ``/``, permitting the whole machine.

    The union of the listed parents has no such hole: ``treeA/d1`` and
    ``treeB/d2`` are roots, their shared parent is not.
    """
    (tmp_path / "secret.txt").write_text("SECRET_OUTSIDE_BOTH_DIRS\n", encoding="utf-8")
    a = tmp_path / "treeA" / "d1"
    b = tmp_path / "treeB" / "d2"
    a.mkdir(parents=True)
    b.mkdir(parents=True)
    (a / "x.rst").write_text(
        "X\n=\n\n.. literalinclude:: ../../secret.txt\n", encoding="utf-8"
    )
    (b / "y.rst").write_text("Y\n=\n\nplain\n", encoding="utf-8")

    host = make_host_project()
    write_ubproject_toml(
        host,
        [
            {
                "files": [str(a / "x.rst"), str(b / "y.rst")],
                "mount_at": "_g/fl",
                "path_check": "error",
            }
        ],
    )
    _replace_index_toctree(host, "_g/fl/x", "_g/fl/y")

    # path_check = "error" aborts the build, which is what pins the message.
    app = make_app(srcdir=host, freshenv=True)
    with pytest.raises(ExtensionError) as excinfo:
        app.build()

    message = str(excinfo.value)
    assert "outside its bundle root" in message, message
    assert str((tmp_path / "secret.txt").resolve()) in message, message
    # Both roots are named, so the author can see the set they may move into.
    assert str(a.resolve()) in message, message
    assert str(b.resolve()) in message, message
    # ...and the unlisted shared parent is not presented as a root.
    assert f"roots ({a.resolve()}, {b.resolve()})" in message, message


def test_files_mode_disjoint_branches_do_not_widen_to_the_filesystem_root(
    make_app, make_host_project, tmp_path
):
    """Two listed files with no meaningful shared parent must not make every
    path on the machine in-bundle.

    The common-ancestor rule promoted the shared parent of the two branches to
    the sole root, so a third directory beside them became in-bundle. Taken to
    its extreme with entries on unrelated filesystem branches the computed root
    was ``/`` and every path on the machine was permitted. Two sibling
    directories under ``tmp_path`` reproduce the mechanism hermetically.
    """
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (outside / "host_secret.txt").write_text("LEAKED\n", encoding="utf-8")
    a = tmp_path / "branch_a"
    b = tmp_path / "branch_b"
    a.mkdir()
    b.mkdir()
    (a / "x.rst").write_text(
        "X\n=\n\n.. literalinclude:: ../elsewhere/host_secret.txt\n",
        encoding="utf-8",
    )
    (b / "y.rst").write_text("Y\n=\n\nplain\n", encoding="utf-8")

    host = make_host_project()
    write_ubproject_toml(
        host,
        [
            {
                "files": [str(a / "x.rst"), str(b / "y.rst")],
                "mount_at": "_g/fl",
                "path_check": "warn",
            }
        ],
    )
    _replace_index_toctree(host, "_g/fl/x", "_g/fl/y")

    app = _build(make_app, host)

    warnings = app._warning.getvalue()
    assert "mounts.path_escape" in warnings, warnings
    assert count_mount_warnings(app) == 1, warnings


def test_files_mode_escape_above_every_root_still_fails(
    make_app, make_host_project, tmp_path
):
    """Widening to a root set must not disable the check: a reference that
    lands outside every root is still an escape."""
    rn = tmp_path / "rn"
    (rn / "notes").mkdir(parents=True)
    (tmp_path / "above").mkdir()
    (tmp_path / "above" / "outside.txt").write_text("ABOVE_TEXT\n", encoding="utf-8")
    (rn / "index.rst").write_text("RN index\n========\n", encoding="utf-8")
    (rn / "notes" / "2026-q1.rst").write_text(
        "Q1 notes\n========\n\n.. literalinclude:: ../../above/outside.txt\n",
        encoding="utf-8",
    )

    host = make_host_project()
    write_ubproject_toml(
        host,
        [
            {
                "files": [str(rn / "index.rst"), str(rn / "notes" / "2026-q1.rst")],
                "mount_at": "_g/rn",
                "path_check": "error",
            }
        ],
    )
    _replace_index_toctree(host, "_g/rn/index", "_g/rn/2026-q1")

    with pytest.raises(Exception, match=r"outside its bundle root"):
        app = make_app(srcdir=host, freshenv=True)
        app.build()


def test_path_escape_message_names_the_mount(make_app, make_host_project, tmp_path):
    """The escape message must name the mount whose ``path_check`` fired.

    "The bundle root" is ambiguous in a project with several mounts, and it is
    the named mount's config block that has to change.
    """
    a = tmp_path / "a"
    a.mkdir()
    b = tmp_path / "b"
    b.mkdir()
    (a / "index.rst").write_text("A\n=\n", encoding="utf-8")
    (tmp_path / "outside.txt").write_text("OUT\n", encoding="utf-8")
    (b / "index.rst").write_text(
        "B\n=\n\n.. literalinclude:: ../outside.txt\n", encoding="utf-8"
    )

    host = make_host_project()
    write_ubproject_toml(
        host,
        [
            {"dir": str(a), "mount_at": "_g/a"},
            {"dir": str(b), "mount_at": "_g/b", "path_check": "warn"},
        ],
    )
    _replace_index_toctree(host, "_g/a/index", "_g/b/index")

    app = _build(make_app, host)

    warnings = app._warning.getvalue()
    # The SECOND mount is the offender, and it is named as such.
    assert f"mounts[1] (dir={b.resolve()})" in warnings, warnings
    assert f"dir={a.resolve()}" not in warnings, warnings


def test_path_check_error_is_attributed_to_this_extension(
    make_app, make_host_project, tmp_path
):
    """``path_check = "error"`` must name sphinx-mounts and print the
    actionable line before the crash report.

    A bundle-authoring mistake is rendered by Sphinx as a crash: from Sphinx
    8.2 on, ``sphinx/_cli/util/errors.py:handle_exception`` prints Versions /
    Last Messages / Loaded Extensions / Traceback blocks for *every*
    ``SphinxError``, plus an invitation to open an issue against Sphinx
    itself. This raise used to pass no ``modname``, so the header read a bare
    ``Extension error!`` and the sentence explaining what the author did wrong
    was buried in the middle of that report.

    ``ExtensionError.category`` is asserted directly because it is literally
    what the CLI prints as the first line
    (``print_red(f'{exception.category}!')``).
    """
    bundle = _leaking_literalinclude_bundle(tmp_path, "../outside.txt")
    (tmp_path / "outside.txt").write_text("OUTSIDE\n", encoding="utf-8")
    host = make_host_project()
    write_ubproject_toml(
        host, [{"dir": str(bundle), "mount_at": "_g/api", "path_check": "error"}]
    )
    _replace_index_toctree(host, "_g/api/index")

    app = make_app(srcdir=host, freshenv=True)
    with pytest.raises(ExtensionError) as excinfo:
        app.build()

    assert excinfo.value.modname == "sphinx_mounts"
    assert excinfo.value.category == "Extension error (sphinx_mounts)"
    # The human message is logged before the raise, so it is not buried.
    logged = app._warning.getvalue()
    assert "outside its bundle root" in logged, logged
    assert "ERROR" in logged, logged


def test_path_escape_message_names_recorded_and_resolved_paths(
    make_app, make_host_project, tmp_path
):
    """The message must print the recorded dependency next to the resolved
    one, so it is clear which directive argument produced the escape.

    Sphinx records the dependency as ``srcdir / rel_fn`` with the ``..``
    segments still in place; the resolved path alone does not show what was
    written in the source.
    """
    bundle = _leaking_literalinclude_bundle(tmp_path, "../outside.txt")
    (tmp_path / "outside.txt").write_text("OUTSIDE\n", encoding="utf-8")
    host = make_host_project()
    write_ubproject_toml(
        host, [{"dir": str(bundle), "mount_at": "_g/api", "path_check": "warn"}]
    )
    _replace_index_toctree(host, "_g/api/index")

    app = _build(make_app, host)

    warnings = app._warning.getvalue()
    assert "recorded dependency" in warnings, warnings
    # The resolved target is named...
    assert str((tmp_path / "outside.txt").resolve()) in warnings
    # ...and so is the un-normalised form Sphinx actually stored.
    recorded = list(app.env.dependencies["_g/api/index"])
    assert recorded, "no dependency recorded for the mounted doc"
    assert any(str(dep) in warnings for dep in recorded), warnings


@pytest.mark.xfail(
    sphinx.version_info[0] < 8,
    reason=(
        "PRE-EXISTING on main, not introduced by variant sources. On Sphinx 7.4 `env.dependencies` records the authored link path rather than the resolved symlink target, so the message this test looks for is not produced. "
        "Surfaced only once the `sphinx7` tox leg was made to install Sphinx 7 "
        "(it had been installing 9); follow-up issue drafted in the svar "
        "build report."
    ),
    strict=True,
)
@pytest.mark.skipif(
    os.name == "nt", reason="symlink creation needs elevated rights on Windows"
)
def test_path_escape_via_symlink_message_mentions_symlinks(
    make_app, make_host_project, tmp_path
):
    """An escape through an in-bundle symlink must say so.

    The author wrote a plain bundle-relative name — no leading ``/``, no
    ``..`` — so advice to avoid those two things describes something they
    never did. Nothing in the message used to explain why the reference was
    rejected.

    Naming the authored path is not an option here: Sphinx resolves the
    symlink *before* recording the dependency, so ``env.dependencies`` holds
    the link target expressed relative to srcdir and the name written in the
    directive is not recoverable at check time (asserted below, so a future
    Sphinx that keeps the link path makes this visible). That is exactly why
    the message has to state the symlink rule outright.
    """
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("OUTSIDE_VIA_LINK\n", encoding="utf-8")
    (bundle / "looks_local.txt").symlink_to(outside)
    (bundle / "index.rst").write_text(
        "Bundle\n======\n\n.. literalinclude:: looks_local.txt\n", encoding="utf-8"
    )

    host = make_host_project()
    write_ubproject_toml(
        host, [{"dir": str(bundle), "mount_at": "_g/api", "path_check": "warn"}]
    )
    _replace_index_toctree(host, "_g/api/index")

    app = _build(make_app, host)

    warnings = app._warning.getvalue()
    assert "outside its bundle root" in warnings, warnings
    # Match the whole sentence, not the bare word "symlink": the warning
    # quotes filesystem paths that contain pytest's tmp_path, which embeds
    # this test's own name — asserting on the word alone passes vacuously.
    assert "A symlink pointing out of the bundle counts as an escape" in warnings, (
        warnings
    )
    # The escape really did land on the link's target...
    assert str(outside.resolve()) in warnings, warnings
    # ...and Sphinx recorded the target, not the authored link name, which is
    # what makes the explicit symlink sentence necessary.
    recorded = [str(d) for d in app.env.dependencies["_g/api/index"]]
    assert recorded, "no dependency recorded for the mounted doc"
    assert not any("looks_local.txt" in dep for dep in recorded), (
        f"Sphinx now records the authored link path ({recorded}) — the message "
        f"could name it directly"
    )


@pytest.mark.skipif(
    os.name == "nt", reason="symlink creation needs elevated rights on Windows"
)
def test_symlinked_bundle_root_is_not_an_escape(make_app, make_host_project, tmp_path):
    """Reaching the bundle through a symlinked directory must NOT be flagged.

    This is the documented Bazel flow — ``bazel-bin`` is itself a symlink into
    the execroot — so a false positive here would break the extension's
    flagship use case. It holds because both sides of the comparison are
    resolved: ``_resolve_dir`` resolves the configured ``dir`` at config time
    and the check resolves each dependency. Nothing pinned that symmetry.
    """
    real = tmp_path / "real_bundle"
    real.mkdir()
    (real / "snippet.py").write_text("IN_BUNDLE = 1\n", encoding="utf-8")
    (real / "index.rst").write_text(
        "Bundle\n======\n\n.. literalinclude:: snippet.py\n", encoding="utf-8"
    )
    link = tmp_path / "link_bundle"
    link.symlink_to(real, target_is_directory=True)

    host = make_host_project()
    # Mounted through the LINK, with the strictest setting.
    write_ubproject_toml(
        host, [{"dir": str(link), "mount_at": "_g/api", "path_check": "error"}]
    )
    _replace_index_toctree(host, "_g/api/index")

    app = _build(make_app, host)  # must NOT raise

    assert count_warnings(app) == 0, app._warning.getvalue()
    html = (Path(app.outdir) / "_g" / "api" / "index.html").read_text(encoding="utf-8")
    assert "IN_BUNDLE" in html


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


def _require_sphinx_needs() -> None:
    """Fail -- never skip -- when sphinx-needs is not importable.

    These three tests are the only coverage of the sphinx-needs integration,
    and they were added for the release workflow's compat cell, which runs
    this suite against the dependencies as PUBLISHED. A ``importorskip`` here
    made that cell green with all three silently not run: sphinx-needs is a
    test-only dependency, so it is in neither the wheel's ``Requires-Dist``
    nor the workspace's ``test`` group (where the name would resolve to the
    sibling member instead of the release). ``compat-requirements.txt`` is
    what installs it there, and this assertion is what makes that file
    load-bearing. In the workspace it is always installed.

    The predicate really imports rather than asking ``find_spec``: a leftover
    empty ``sphinx_needs/`` directory picked up as a namespace package, or an
    ``__init__.py`` that raises, would satisfy ``find_spec`` and then fail
    several seconds later inside Sphinx with a much worse message.
    """
    assert importlib.import_module("sphinx_needs"), (
        "sphinx-needs is required to run this test and is not installed. In "
        "this workspace it is a sibling member; outside it, install the "
        "packages/sphinx-mounts/compat-requirements.txt list"
    )


def _plantuml_jar_command() -> tuple[str, ...] | None:
    """The ``plantuml`` configuration value for a jar named by ``PLANTUML_JAR``.

    The second of the two ways this suite can reach PlantUML, and the one CI
    uses: no ``plantuml`` package is installed anywhere, and the workflows
    point this variable at the jar ``packages/sphinx-needs`` vendors for its
    own tests. ``java`` has to be on ``PATH`` for it, which it is on every
    GitHub runner image.

    Returns ``None`` when the variable is unset, so the ``plantuml``-on-PATH
    route is used instead; a variable that names a file which is not there is
    a mistake worth failing on rather than falling back from, so it returns
    the command regardless and lets the render fail loudly.
    """
    jar = os.environ.get("PLANTUML_JAR")
    if not jar:
        return None
    # A TUPLE, not a string: sphinxcontrib-plantuml's ``_split_cmdargs`` passes a
    # list or tuple through untouched and ``shlex``-splits anything else, which
    # would break on a checkout under a path containing a space (and, on posix,
    # on a Windows path's backslashes). Headless, like the sphinx-needs fixture
    # that supplies the same jar: a CI runner has no windowing toolkit.
    return ("java", "-Djava.awt.headless=true", "-jar", jar)


def _require_renderer(directive_rst: str) -> None:
    """Fail the test when a diagram directive's renderer is not available.

    The graphviz/uml cases must exercise the full mounts chain *including*
    the real renderer — tolerating a missing one would silently skip the
    render step, which is the whole point of those tests. So this asserts; it
    never skips.
    """
    if "graphviz" in directive_rst:
        assert shutil.which("dot"), (
            "graphviz (the `dot` binary) is required to run this test — "
            "install it (e.g. `apt install graphviz`)"
        )
    elif "uml" in directive_rst:
        assert _plantuml_jar_command() or shutil.which("plantuml"), (
            "PlantUML is required to run this test. Either set PLANTUML_JAR to "
            "a plantuml jar and have `java` on PATH (this repository vendors "
            "one at packages/sphinx-needs/tests/doc_test/utils/plantuml.jar, "
            "which is what CI points the variable at), or install a `plantuml` "
            "executable (e.g. `apt install plantuml`, `brew install plantuml`, "
            "`choco install plantuml`)"
        )


def _plantuml_extra_conf() -> tuple[str, ...]:
    """Extra conf.py lines for the uml tests.

    ``PLANTUML_JAR`` wins when it is set: it is an explicit choice, and it is
    the one CI makes on every runner including Windows.

    Otherwise sphinxcontrib.plantuml invokes the ``plantuml`` command
    synchronously; on Windows the chocolatey package's ``plantuml`` shim is
    non-blocking (javaw), so its ``plantumlc`` (java) shim must be used there.
    """
    jar_command = _plantuml_jar_command()
    if jar_command is not None:
        # `repr` of the tuple, so both a Windows path's backslashes and any
        # space in it survive into the conf.py as one argument
        return (f"plantuml = {jar_command!r}",)
    if os.name == "nt":
        return ("plantuml = 'plantumlc'",)
    return ()


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
    _require_renderer(directive_rst)

    bundle = tmp_path / "bundle"
    bundle.mkdir()
    _write_payload(bundle / target_name, old_content)
    (bundle / "index.rst").write_text(
        f"Bundle\n======\n\n{directive_rst}", encoding="utf-8"
    )

    host = make_host_project()
    if extensions:
        _add_extensions(host, *extensions)
    for line in conf_lines + _plantuml_extra_conf():
        _append_conf(host, line)
    write_ubproject_toml(host, [{"dir": str(bundle), "mount_at": "_generated/m"}])
    _replace_index_toctree(host, "_generated/m/index")

    app = make_app(srcdir=host, freshenv=True)
    app.build()
    assert count_warnings(app) == 0, app._warning.getvalue()

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
    assert count_warnings(app) == 0, app._warning.getvalue()
    read = _docs_read_in_log(app._status.getvalue()[offset:])

    assert "_generated/m/index" in read, (
        f"mounted doc not re-read after its {target_name} dependency changed; "
        f"read={read}"
    )
