"""The order in which the suite decides how to render PlantUML.

Every test project's ``plantuml`` configuration comes from the ``plantuml_command``
fixture, which is :func:`tests.conftest.resolve_plantuml_command` applied to the copy of
the vendored jar that ``sphinx_test_tempdir`` made. The order that function applies is
load-bearing rather than incidental, so it is asserted here instead of being left to the
several hundred rendering tests that would merely go a strange colour if it changed:

* ``PLANTUML_JAR`` beats everything, because naming a jar is an explicit choice;
* the vendored jar beats a ``plantuml`` on ``PATH``, because this suite renders for real
  and a developer machine carrying a homebrew ``plantuml`` must not silently swap the
  renderer version out from under it;
* the executable is reached only when the vendored jar is gone, which is what a checkout
  or an sdist without the jar looks like.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from tests.conftest import resolve_plantuml_command


@pytest.fixture
def vendored_jar(tmp_path: Path) -> Path:
    """A stand-in for the copy of the vendored jar in the test tempdir."""
    jar = tmp_path / "utils" / "plantuml.jar"
    jar.parent.mkdir()
    jar.write_bytes(b"not really a jar")
    return jar


@pytest.fixture(autouse=True)
def _no_inherited_jar(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start every case from an unset ``PLANTUML_JAR``.

    CI sets it for the sphinx-mounts cells and the release workflow's build job, and a
    developer may well have it exported, so a case that means "unset" has to say so.
    """
    monkeypatch.delenv("PLANTUML_JAR", raising=False)


def test_the_environment_variable_wins(
    tmp_path: Path, vendored_jar: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``PLANTUML_JAR`` is chosen over both the vendored jar and an executable."""
    named = tmp_path / "somewhere-else.jar"
    named.write_bytes(b"not really a jar either")
    monkeypatch.setenv("PLANTUML_JAR", str(named))
    monkeypatch.setattr(shutil, "which", lambda _name: "/usr/local/bin/plantuml")

    assert (
        resolve_plantuml_command(vendored_jar)
        == f"java -Djava.awt.headless=true -jar {named}"
    )


def test_the_vendored_jar_is_the_default(
    vendored_jar: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no ``PLANTUML_JAR``, the vendored jar is used even when ``plantuml`` is on
    ``PATH`` -- the developer-machine guard."""
    monkeypatch.setattr(shutil, "which", lambda _name: "/usr/local/bin/plantuml")

    assert (
        resolve_plantuml_command(vendored_jar)
        == f"java -Djava.awt.headless=true -jar {vendored_jar}"
    )


def test_an_executable_is_the_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With the jar gone -- a checkout or sdist without it -- ``plantuml`` on ``PATH``
    is used."""
    monkeypatch.setattr(shutil, "which", lambda _name: "/usr/local/bin/plantuml")

    assert (
        resolve_plantuml_command(tmp_path / "utils" / "plantuml.jar")
        == "/usr/local/bin/plantuml"
    )


def test_a_named_jar_that_is_not_there_is_an_error(
    tmp_path: Path, vendored_jar: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A ``PLANTUML_JAR`` naming no file fails loudly, and never falls through.

    Falling back to the vendored jar here would render with a renderer the caller did not
    ask for and report nothing about it.
    """
    missing = tmp_path / "gone.jar"
    monkeypatch.setenv("PLANTUML_JAR", str(missing))
    monkeypatch.setattr(shutil, "which", lambda _name: "/usr/local/bin/plantuml")

    with pytest.raises(RuntimeError, match=str(missing)):
        resolve_plantuml_command(vendored_jar)


def test_no_renderer_at_all_is_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No variable, no jar and no executable names all three routes in the message."""
    monkeypatch.setattr(shutil, "which", lambda _name: None)

    with pytest.raises(RuntimeError, match="no PlantUML to render with"):
        resolve_plantuml_command(tmp_path / "utils" / "plantuml.jar")
