"""Diagnostics about mounted docs carry an ABSOLUTE filesystem path that points
into the mount's source tree — never a srcdir-relative path or a bare docname.

Why this matters: a tool that consumes the build log (an editor's problem
matcher, a terminal's Ctrl+click, CI annotations) can only open the offending
file if the location is absolute. A path relative to the Sphinx ``srcdir``
is useless to anything that does not already know ``srcdir``.

The behaviour is not implemented by this extension directly. sphinx-mounts
stores each mounted doc's *absolute* external path in
``Project._docname_to_path`` (see ``mounter._register``); Sphinx then derives
every diagnostic location from that — ``os.path.abspath(node.source)`` for
docutils/RST messages and ``env.doc2path(docname)`` for reference messages
(``sphinx/util/logging.py``). Because the stored path is absolute, the
location is absolute too — and any directive/extension that reports through
docutils or attaches ``location=node`` inherits it for free.

Coverage:

* core RST/ref warnings with no file reference — title-underline and a
  broken cross-reference;
* every file-referencing integration showcased in
  ``tests/example/showcase`` — csv-table, figure, graphviz, image, include,
  literalinclude, mermaid, raw, uml — each made to reference a *missing*
  file. This spans docutils-native directives, Sphinx core (asset collector,
  literalinclude), Sphinx-bundled extensions (graphviz), and third-party
  extensions (sphinxcontrib.plantuml / .mermaid). The missing-file path is
  detected at read time, so no dot/java/mmdc renderer binary is required.
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import TYPE_CHECKING

import pytest

from tests.conftest import write_ubproject_toml

if TYPE_CHECKING:
    from sphinx.testing.util import SphinxTestApp

_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


def _build(make_app, host: Path) -> SphinxTestApp:
    """Build the host project and return the app (for outdir/warnings)."""
    app = make_app(srcdir=host, freshenv=True)
    app.build()
    return app


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


def _lines_mentioning(warnings: str, fragment: str) -> list[str]:
    """Return the ANSI-stripped diagnostic lines that contain ``fragment``."""
    plain = _ANSI_ESCAPE_RE.sub("", warnings)
    return [line for line in plain.splitlines() if fragment in line]


def _assert_located_at(lines: list[str], source_file: Path, host_srcdir: Path) -> None:
    """Assert every line is prefixed ``<abs source_file>:<lineno>:`` — i.e. an
    absolute path into the mount, with a line number — and never a path under
    the host srcdir. Severity-agnostic: matches WARNING and CRITICAL alike."""
    abs_src = str(source_file.resolve())
    assert source_file.resolve().is_absolute()  # sanity: the expectation is absolute
    loc_re = re.compile(re.escape(abs_src) + r":\d+:")
    for line in lines:
        assert loc_re.match(line), (
            f"diagnostic location is not the absolute mounted path "
            f"{abs_src!r} with a line number:\n  {line}"
        )
        # The location must not be a path under the host srcdir.
        assert not line.startswith(str(host_srcdir.resolve())), (
            f"diagnostic location points into the host srcdir, not the mount:\n  {line}"
        )


# ---------- core RST / ref warnings (no file reference) ----------

CORE_CASES = [
    pytest.param(
        # title (11 chars) over a 4-char underline -> docutils RST warning
        "Broken page\n====\n\nBody text.\n",
        "Title underline too short",
        id="docutils-title-underline",
    ),
    pytest.param(
        # cross-reference to a doc that does not exist -> Sphinx ref warning
        "Broken page\n===========\n\nSee :doc:`does-not-exist`.\n",
        "unknown document",
        id="ref-doc-missing",
    ),
]


@pytest.mark.parametrize("doc_rst, fragment", CORE_CASES)
def test_core_warning_location_is_absolute_mount_path(
    make_app, make_host_project, tmp_path, doc_rst, fragment
):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "index.rst").write_text(doc_rst, encoding="utf-8")

    host = make_host_project()
    write_ubproject_toml(host, [{"dir": str(bundle), "mount_at": "_g/api"}])
    _replace_index_toctree(host, "_g/api/index")

    app = _build(make_app, host)

    lines = _lines_mentioning(app._warning.getvalue(), fragment)
    assert lines, f"expected a {fragment!r} warning; got:\n{app._warning.getvalue()}"
    _assert_located_at(lines, bundle / "index.rst", Path(app.srcdir))


# ---------- every file-referencing integration in tests/example/showcase ----------
#
# Each references a MISSING file so the directive emits a read-time diagnostic.
# ``fragment`` is a substring that lands on the *located* line (the one carrying
# ``<path>:<line>:``); for the docutils :file: directives that is the
# ``Problems with "<name>" directive`` headline, with the missing-path detail on
# the following (un-located) line.
#
# Columns: directive_rst, extensions, conf_lines, fragment, importorskip_module
SHOWCASE_CASES = [
    pytest.param(
        ".. csv-table:: Limits\n   :file: missing.csv\n   :header-rows: 1\n",
        (),
        (),
        'Problems with "csv-table" directive',
        None,
        id="csv-table",
    ),
    pytest.param(
        ".. figure:: missing.png\n\n   A bundled figure with a caption.\n",
        (),
        (),
        "image file not readable",
        None,
        id="figure",
    ),
    pytest.param(
        ".. graphviz:: missing.dot\n",
        ("sphinx.ext.graphviz",),
        (),
        "External Graphviz file",
        None,
        id="graphviz",
    ),
    pytest.param(
        ".. image:: missing.png\n   :alt: A bundled image\n",
        (),
        (),
        "image file not readable",
        None,
        id="image",
    ),
    pytest.param(
        ".. include:: missing.txt\n",
        (),
        (),
        'Problems with "include" directive',
        None,
        id="include",
    ),
    pytest.param(
        ".. literalinclude:: missing.py\n   :language: python\n",
        (),
        (),
        "Include file",
        None,
        id="literalinclude",
    ),
    pytest.param(
        ".. mermaid:: missing.mmd\n",
        ("sphinxcontrib.mermaid",),
        ("mermaid_output_format = 'raw'",),
        "External Mermaid file",
        "sphinxcontrib.mermaid",
        id="mermaid",
    ),
    pytest.param(
        ".. raw:: html\n   :file: missing.html\n",
        (),
        (),
        'Problems with "raw" directive',
        None,
        id="raw",
    ),
    pytest.param(
        ".. uml:: missing.puml\n",
        ("sphinxcontrib.plantuml",),
        (),
        "PlantUML file",
        "sphinxcontrib.plantuml",
        id="uml",
    ),
]


@pytest.mark.parametrize(
    "directive_rst, extensions, conf_lines, fragment, skip_module", SHOWCASE_CASES
)
def test_showcase_integration_warning_location_is_absolute_mount_path(
    make_app,
    make_host_project,
    tmp_path,
    directive_rst,
    extensions,
    conf_lines,
    fragment,
    skip_module,
):
    """Every showcase directive that references a missing file reports the
    failure at the mounted doc's ABSOLUTE path. The missing reference resolves
    *inside* the bundle root, so path_check does not interfere."""
    if skip_module:
        pytest.importorskip(skip_module)

    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "index.rst").write_text(
        f"Bundle\n======\n\n{directive_rst}", encoding="utf-8"
    )

    host = make_host_project()
    if extensions:
        _add_extensions(host, *extensions)
    for line in conf_lines:
        _append_conf(host, line)
    write_ubproject_toml(host, [{"dir": str(bundle), "mount_at": "_g/api"}])
    _replace_index_toctree(host, "_g/api/index")

    app = _build(make_app, host)

    lines = _lines_mentioning(app._warning.getvalue(), fragment)
    assert lines, f"expected a {fragment!r} diagnostic; got:\n{app._warning.getvalue()}"
    _assert_located_at(lines, bundle / "index.rst", Path(app.srcdir))
