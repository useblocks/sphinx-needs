"""End-to-end test of the full example under ``tests/example/``.

The example is a complete, checked-in reference setup: a host Sphinx
project + two Bazel-generated bundles (one RST, one Markdown) wired
into the host's toctree via ``attach_to``. This test runs the
pipeline the example's README documents:

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
    assert (bazel_bin / "api-bar" / "index.md").exists()

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

    # 5) Nothing was copied into the host srcdir.
    assert not (docs / "_generated").exists()


def _have_sphinx_module() -> bool:
    """``python -m sphinx`` only works if Sphinx is importable from the
    current interpreter — which it is when running the project's tests
    via tox."""
    return importlib.util.find_spec("sphinx") is not None
