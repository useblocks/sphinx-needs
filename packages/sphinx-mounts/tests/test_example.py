"""End-to-end test of the full example under ``tests/example/``.

The example is a complete, checked-in reference setup: a host Sphinx
project, two Bazel-generated bundles (one RST, one Markdown), and nine
checked-in "showcase" bundles — one folder per file-referencing
directive (literalinclude, include, csv-table, raw, image, figure,
graphviz, uml, mermaid) — all wired into the host's toctree via
``attach_to``. This test runs the pipeline the example's README
documents:

1. Copy the example to a tmp workspace (so the developer's real
   ``bazel-bin/`` is untouched).
2. ``bazel build //:all_bundles`` to materialise the bundles under
   ``bazel-bin/bundles/...``.
3. ``sphinx-build`` against the host project. ``sphinx-mounts`` reads
   ``ubproject.toml``, mounts both bundles in place, and ``attach_to``
   injects each bundle's entry doc into the host's ``index.rst``
   toctree at doctree-read time.
4. Assert that all three layers (host, RST bundle, MD bundle) appear
   in the rendered HTML, plus the attach_to wiring did its work.

Marked ``bazel``; skipped when no ``bazel``/``bazelisk`` is on PATH.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

TESTS_DIR = Path(__file__).parent
EXAMPLE_DIR = TESTS_DIR / "example"


def _find_bazel() -> str | None:
    return shutil.which("bazel") or shutil.which("bazelisk")


@pytest.mark.bazel
def test_example_pipeline_end_to_end(tmp_path: Path) -> None:
    bazel = _find_bazel()
    if bazel is None:
        pytest.skip("bazel/bazelisk not on PATH")
    if shutil.which("sphinx-build") is None and not _have_sphinx_module():
        pytest.skip("sphinx-build not available")
    pytest.importorskip("myst_parser")
    # The showcase bundles render graphviz and plantuml diagrams at build
    # time under ``-nW``; skip (don't fail) when their extensions or
    # binaries are unavailable. Mermaid runs in ``raw`` mode, so no
    # ``mmdc`` binary is required.
    pytest.importorskip("sphinxcontrib.plantuml")
    pytest.importorskip("sphinxcontrib.mermaid")
    for tool in ("dot", "java", "plantuml"):
        if shutil.which(tool) is None:
            pytest.skip(
                f"{tool!r} not on PATH — required to render the showcase "
                "graphviz/plantuml bundles under -nW"
            )

    workspace = tmp_path / "ws"
    shutil.copytree(EXAMPLE_DIR, workspace)

    # Per-test --output_base so this never touches the developer's real
    # Bazel state.
    output_base = tmp_path / "bazel-out-base"
    output_base.mkdir()

    bazel_build = subprocess.run(
        [
            bazel,
            f"--output_base={output_base}",
            "build",
            "//:all_bundles",
        ],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
    )
    if bazel_build.returncode != 0:
        pytest.fail(
            "bazel build failed:\n"
            f"stdout:\n{bazel_build.stdout}\n"
            f"stderr:\n{bazel_build.stderr}\n"
        )

    # Both bundles should now exist on disk where ubproject.toml expects
    # them.
    bazel_bin = workspace / "bazel-bin" / "bundles"
    assert (bazel_bin / "api-foo" / "index.rst").exists()
    assert (bazel_bin / "api-foo" / "reference.rst").exists()
    assert (bazel_bin / "api-foo" / "coverage.rst").exists()
    assert (bazel_bin / "api-bar" / "index.md").exists()
    # The pre-built HTML report (consumed by html_extra_path) is
    # materialised too, alongside the bundles.
    assert (
        workspace
        / "bazel-bin"
        / "coverage_report"
        / "extra"
        / "coverage"
        / "index.html"
    ).exists()

    # The directive "showcase" bundles are plain checked-in files (NOT
    # Bazel-generated): they live under ``showcase/<directive>/`` and are
    # copied into the workspace as-is, then mounted directly from there.
    assert (workspace / "showcase" / "literalinclude" / "greeter.py").exists()
    assert (workspace / "showcase" / "uml" / "sequence.puml").exists()
    assert (workspace / "showcase" / "csv-table" / "data.csv").exists()

    # Run sphinx-build against the host project. -W turns any unresolved
    # reference into a failure, so a broken mount surfaces here.
    docs = workspace / "docs"
    html_out = tmp_path / "html"
    sphinx_build = subprocess.run(
        [
            sys.executable,
            "-m",
            "sphinx",
            "-b",
            "html",
            "-nW",
            "--keep-going",
            "-c",
            str(docs),
            str(docs),
            str(html_out),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if sphinx_build.returncode != 0:
        pytest.fail(
            "sphinx-build failed:\n"
            f"stdout:\n{sphinx_build.stdout}\n"
            f"stderr:\n{sphinx_build.stderr}\n"
        )

    # 1) Host's own RST page rendered.
    index_html = (html_out / "index.html").read_text(encoding="utf-8")
    install_html = (html_out / "installation.html").read_text(encoding="utf-8")
    assert "INDEX_PAGE_MARKER" in index_html
    assert "INSTALL_PAGE_MARKER" in install_html

    # 2) RST bundle rendered (entry + reference).
    foo_index = (html_out / "_generated" / "api-foo" / "index.html").read_text(
        encoding="utf-8"
    )
    foo_ref = (html_out / "_generated" / "api-foo" / "reference.html").read_text(
        encoding="utf-8"
    )
    assert "API_FOO_INDEX_MARKER" in foo_index
    assert "API_FOO_REFERENCE_MARKER" in foo_ref

    # 2b) Each checked-in "showcase" bundle renders one file-referencing
    #     directive at _generated/showcase/<directive>/index.html. The
    #     build succeeding under -nW already proves every directive
    #     resolved its path *inside* its bundle (and passed path_check);
    #     these spot-checks confirm the referenced content actually landed.
    def _showcase(name: str) -> str:
        return (html_out / "_generated" / "showcase" / name / "index.html").read_text(
            encoding="utf-8"
        )

    # Text directives embed the referenced file's content verbatim.
    assert "SHOWCASE_GREETER" in _showcase("literalinclude")
    assert "SHOWCASE_INCLUDE_BODY" in _showcase("include")
    assert "SHOWCASE_CSV_ROW" in _showcase("csv-table")
    assert "SHOWCASE_RAW_BODY" in _showcase("raw")
    assert "SHOWCASE_MERMAID_NODE" in _showcase("mermaid")  # mermaid (raw mode)
    # image / figure / graphviz / uml render to files in the shared _images/.
    assert "SHOWCASE_IMAGE" in _showcase("image")
    assert "SHOWCASE_FIGURE" in _showcase("figure")
    assert "SHOWCASE_GRAPHVIZ" in _showcase("graphviz")
    assert "SHOWCASE_UML" in _showcase("uml")
    assert (html_out / "_images").is_dir()

    # 2c) The pre-built HTML coverage report is shipped into the site by
    #     html_extra_path — so the built output is self-contained and
    #     copyable to any server — and the api-foo bundle's coverage page
    #     links to + embeds it via a bundle-relative URL. The report is
    #     read in place; it is never staged into the docs source tree.
    assert (html_out / "coverage" / "index.html").exists()
    assert (html_out / "coverage" / "greeter.py.html").exists()
    report_html = (html_out / "coverage" / "index.html").read_text(encoding="utf-8")
    assert "API_FOO_COVERAGE_REPORT_MARKER" in report_html
    foo_cov = (html_out / "_generated" / "api-foo" / "coverage.html").read_text(
        encoding="utf-8"
    )
    assert "API_FOO_COVERAGE_MARKER" in foo_cov
    assert 'href="../../coverage/index.html"' in foo_cov
    assert 'src="../../coverage/index.html"' in foo_cov

    # 3) Markdown bundle rendered.
    bar_index = (html_out / "_generated" / "api-bar" / "index.html").read_text(
        encoding="utf-8"
    )
    assert "API_BAR_INDEX_MARKER" in bar_index

    # 4) Both wiring styles produce toctree links in the rendered
    #    host index.html — api-foo via ``attach_to`` (doctree-level
    #    injection; the host source RST never references its mount
    #    path), api-bar via a hand-written toctree entry in the
    #    host's ``index.rst``.
    source_index_rst = (docs / "index.rst").read_text(encoding="utf-8")
    assert "_generated/api-foo" not in source_index_rst, (
        "api-foo is wired via attach_to; the host source RST must not "
        "reference its mount path"
    )
    assert "_generated/api-bar/index" in source_index_rst, (
        "api-bar has no attach_to in this example; the host references "
        "its entry doc by hand"
    )
    assert "_generated/api-foo/index.html" in index_html
    assert "_generated/api-bar/index.html" in index_html
    # The showcase bundles are wired via attach_to too, so their entry
    # docs appear in the host index toctree (and never in its source RST).
    assert "_generated/showcase" not in source_index_rst
    assert "_generated/showcase/literalinclude/index.html" in index_html
    assert "_generated/showcase/uml/index.html" in index_html

    # 5) Nothing was copied into the host srcdir — neither the mounted
    #    bundles (_generated) nor the html_extra_path report (coverage).
    assert not (docs / "_generated").exists()
    assert not (docs / "coverage").exists()


def _have_sphinx_module() -> bool:
    """``python -m sphinx`` only works if Sphinx is importable from the
    current interpreter — which it is when running the project's tests
    via tox."""
    return importlib.util.find_spec("sphinx") is not None
