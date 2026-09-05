"""Bazel integration test.

Builds a small Bazel workspace whose ``genrule`` outputs end up under
``bazel-bin/docs/``, then runs ``sphinx-build`` against a Sphinx project
that mounts that directory. Confirms the genrule content reaches the
HTML output via sphinx-mounts.

The test is marked ``bazel`` and skipped when no bazel/bazelisk binary is
on ``PATH``. Run it with ``tox -e bazel`` or
``pytest -m bazel tests/test_bazel.py``.
"""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    pass

TESTS_DIR = Path(__file__).parent
BAZEL_FIXTURE = TESTS_DIR / "fixtures" / "bazel"


def _find_bazel() -> str | None:
    return shutil.which("bazel") or shutil.which("bazelisk")


@pytest.mark.bazel
def test_bazel_genrule_output_is_mounted(tmp_path: Path) -> None:
    bazel = _find_bazel()
    if bazel is None:
        pytest.skip("bazel/bazelisk not on PATH")

    workspace = tmp_path / "ws"
    shutil.copytree(BAZEL_FIXTURE, workspace)

    # Each test run gets its own output base so the test is hermetic and
    # cannot collide with the user's other Bazel state.
    output_base = tmp_path / "bazel-out-base"
    output_base.mkdir()

    bazel_build = subprocess.run(
        [
            bazel,
            f"--output_base={output_base}",
            "build",
            "//:generated_docs",
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

    bazel_bin_docs = workspace / "bazel-bin" / "docs"
    assert (bazel_bin_docs / "index.rst").exists(), (
        f"bazel did not produce {bazel_bin_docs / 'index.rst'}"
    )
    assert (bazel_bin_docs / "tutorial.rst").exists()

    # Run sphinx-build against the project. -W turns warnings into errors so
    # any mounting glitch (missing docname, unresolved ref) fails the test.
    sphinx_project = workspace / "sphinx_project"
    html_out = tmp_path / "html"
    sphinx_build = subprocess.run(
        [
            sys.executable,
            "-m",
            "sphinx",
            "-b",
            "html",
            "-W",
            "--keep-going",
            "-c",
            str(sphinx_project),
            str(sphinx_project),
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

    tutorial_html = (html_out / "_bazel" / "tutorial.html").read_text(encoding="utf-8")
    assert "BAZEL_GENRULE_MARKER" in tutorial_html

    # The mounted files were never copied into the Sphinx srcdir.
    assert not (sphinx_project / "_bazel").exists()
