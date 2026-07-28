"""Regression guard: the libclang engine is an OPTIONAL dependency.

A project that only wants tree-sitter extraction must be able to import and run
sphinx-codelinks without the ``libclang`` wheel installed. Selecting the
libclang engine without it must fail with a clear ``pip install`` hint, not an
obscure ``ImportError``.

CI installs the ``libclang`` extra, so we cannot test the absent case simply by
not installing it. Instead each test spawns a fresh interpreter with
``clang``/``clang.*`` blocked at import time (a tree-sitter-only install, by
construction) and -- before anything else -- proves the block is effective, so
the test can never pass vacuously when the wheel happens to be present.

If someone adds an eager top-level ``import clang`` anywhere in the import
chain, ``test_treesitter_path_imports_and_runs_without_libclang`` breaks here
instead of silently making libclang mandatory for every user.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import textwrap

FIXTURE = Path(__file__).parent / "data" / "preproc" / "variants_branching.cpp"

# Block ``clang`` so the child interpreter behaves like a tree-sitter-only
# install, then assert the block actually took effect -- otherwise every check
# below would be meaningless on a machine that has the libclang wheel.
_BLOCK_CLANG = """
import importlib.abc
import sys


class _BlockClang(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path, target=None):
        if name == "clang" or name.startswith("clang."):
            raise ImportError("simulated tree-sitter-only install: " + name)
        return None  # defer all other imports to the real finders


for _mod in [k for k in sys.modules if k == "clang" or k.startswith("clang.")]:
    del sys.modules[_mod]
sys.meta_path.insert(0, _BlockClang())

try:
    import clang.cindex
except ImportError:
    pass
else:
    raise SystemExit("clang.cindex was NOT blocked; this test would be vacuous")
"""


def _run_probe(body: str) -> None:
    """Run ``_BLOCK_CLANG + body`` in a fresh interpreter.

    The fixture path is passed as ``sys.argv[1]``. On non-zero exit the child's
    stdout/stderr are surfaced in the assertion message.
    """
    code = _BLOCK_CLANG + textwrap.dedent(body)
    proc = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code, str(FIXTURE)],
        capture_output=True,
        text=True,
        check=False,  # returncode is asserted explicitly below
    )
    assert proc.returncode == 0, (
        f"probe exited {proc.returncode}\n"
        f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
    )


def test_treesitter_path_imports_and_runs_without_libclang() -> None:
    """Default (tree-sitter) extraction needs no libclang -- import and run."""
    _run_probe(
        """
        import sys
        from pathlib import Path

        # Importing these must not pull in clang (parent __init__ files run too).
        from sphinx_codelinks.analyse.analyse import SourceAnalyse
        from sphinx_codelinks.config import SourceAnalyseConfig

        fixture = Path(sys.argv[1])
        cfg = SourceAnalyseConfig(
            src_files=[fixture],
            src_dir=fixture.parent,
            get_oneline_needs=True,
        )
        analyse = SourceAnalyse(cfg)
        analyse.git_remote_url = None
        analyse.git_commit_rev = None
        analyse.run()  # no preprocessor configured -> tree-sitter engine

        ids = {n.need["id"] for n in analyse.oneline_needs}
        # tree-sitter ignores #ifdef, so markers on every branch are extracted.
        missing = {"IMPL_ALWAYS", "IMPL_VAR_A", "IMPL_VAR_B"} - ids
        assert not missing, f"tree-sitter missed markers without libclang: {missing}"
        """
    )


def test_libclang_engine_errors_with_install_hint_when_extra_missing() -> None:
    """Selecting the libclang engine without the extra raises the install hint."""
    _run_probe(
        """
        import sys
        from pathlib import Path

        from sphinx_codelinks.analyse.analyse import SourceAnalyse
        from sphinx_codelinks.config import PreprocessorConfig, SourceAnalyseConfig

        fixture = Path(sys.argv[1])
        cfg = SourceAnalyseConfig(
            src_files=[fixture],
            src_dir=fixture.parent,
            get_oneline_needs=True,
            preprocessor=PreprocessorConfig(defines=[]),  # selects libclang engine
        )
        analyse = SourceAnalyse(cfg)
        analyse.git_remote_url = None
        analyse.git_commit_rev = None
        try:
            analyse.run()
        except ImportError as exc:
            assert "sphinx-codelinks[libclang]" in str(exc), (
                f"install hint did not name the extra: {str(exc)!r}"
            )
        else:
            raise SystemExit("libclang engine ran without the extra; expected ImportError")
        """
    )
