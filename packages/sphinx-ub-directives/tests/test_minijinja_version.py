"""The engine version is part of the template corpus (contract §9.4)."""

from __future__ import annotations

import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "tools" / "check_minijinja_version.py"


def test_the_lock_resolves_the_version_the_corpus_records() -> None:
    """The CI-runnable script, run as CI would run it."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


def test_the_installed_engine_is_the_recorded_one() -> None:
    """The environment this suite runs in renders with the recorded version."""
    from .test_templates_conformance import header_minijinja

    assert version("minijinja") == header_minijinja()
