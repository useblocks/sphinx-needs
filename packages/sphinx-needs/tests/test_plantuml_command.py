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

The command it returns is a *string*, which sphinxcontrib-plantuml splits for itself, so
two of the cases below assert through that real split rather than on the string -- what has
to survive is the argv, not the spelling. :func:`tests.conftest.copy_test_utils` is pinned
here too, since it decides whether route (2) is reachable at all.
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

import pytest
from sphinxcontrib.plantuml import _split_cmdargs

from tests.conftest import copy_test_utils, resolve_plantuml_command


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


def _expected(path: Path) -> str:
    """A ``pytest.raises`` pattern matching the message's rendering of ``path``.

    Two escapes, and both are load-bearing on Windows. ``match=`` is a REGULAR
    EXPRESSION, so a raw ``C:\\Users\\...`` is not a path there but a pattern beginning
    with the invalid escape ``\\U`` -- ``re`` rejects it before the assertion is reached,
    and the three Windows cells go red on every run. And the message renders the value
    with ``!r`` (deliberately: it is what makes a whitespace-only ``PLANTUML_JAR``
    visible), so what appears in it is ``repr`` of the path -- with the backslashes
    DOUBLED. Escaping the bare ``str`` fixes the crash and then fails to match.
    """
    return re.escape(repr(str(path)))


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
        == f'java -Djava.awt.headless=true -jar "{named}"'
    )


def test_the_vendored_jar_is_the_default(
    vendored_jar: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no ``PLANTUML_JAR``, the vendored jar is used even when ``plantuml`` is on
    ``PATH`` -- the developer-machine guard."""
    monkeypatch.setattr(shutil, "which", lambda _name: "/usr/local/bin/plantuml")

    assert (
        resolve_plantuml_command(vendored_jar)
        == f'java -Djava.awt.headless=true -jar "{vendored_jar}"'
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

    with pytest.raises(RuntimeError, match=_expected(missing)):
        resolve_plantuml_command(vendored_jar)


def test_no_renderer_at_all_is_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No variable, no jar and no executable names all three routes in the message."""
    monkeypatch.setattr(shutil, "which", lambda _name: None)

    with pytest.raises(RuntimeError, match="no PlantUML to render with"):
        resolve_plantuml_command(tmp_path / "utils" / "plantuml.jar")


def test_an_empty_variable_is_treated_as_unset(
    vendored_jar: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An empty ``PLANTUML_JAR`` falls through to the vendored jar.

    Not a curiosity: it is how the variable arrives from a developer shell with
    ``PLANTUML_JAR=`` exported, and from a workflow that computes the value with an
    expression rather than deciding whether to set it. Read as "set but names no file"
    it would instead raise, which is a red run for every cell that does not want a jar.
    sphinx-mounts' `_plantuml_jar_command` agrees, and its own suite pins it too.
    """
    monkeypatch.setenv("PLANTUML_JAR", "")

    assert (
        resolve_plantuml_command(vendored_jar)
        == f'java -Djava.awt.headless=true -jar "{vendored_jar}"'
    )


def test_a_named_jar_that_is_a_directory_is_an_error(
    tmp_path: Path, vendored_jar: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A ``PLANTUML_JAR`` naming a directory is as wrong as one naming nothing.

    ``java -jar <a directory>`` fails at render time, far from the mistake, so this is
    the same fail-loud case as a missing file and is rejected by the same branch.
    """
    monkeypatch.setenv("PLANTUML_JAR", str(tmp_path))

    with pytest.raises(RuntimeError, match=_expected(tmp_path)):
        resolve_plantuml_command(vendored_jar)


def test_a_jar_path_with_a_space_stays_one_argument(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The command survives sphinxcontrib-plantuml's own splitting.

    That module `shlex`-splits any command that is not already a list or tuple, so an
    unquoted path containing a space arrives as two argv elements and the render dies
    with an unhelpful message. Asserted through the real ``_split_cmdargs``, which takes
    both the posix and the Windows branch depending on where this runs.
    """
    jar = tmp_path / "My Jars" / "plantuml.jar"
    jar.parent.mkdir()
    jar.write_bytes(b"not really a jar")
    monkeypatch.setenv("PLANTUML_JAR", str(jar))

    argv = _split_cmdargs(resolve_plantuml_command(tmp_path / "unused.jar"))

    assert argv == ["java", "-Djava.awt.headless=true", "-jar", str(jar)]


def test_the_ordinary_jar_path_splits_to_the_same_argv(
    vendored_jar: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Quoting the path changes the string and not the argv."""
    monkeypatch.setattr(shutil, "which", lambda _name: None)

    argv = _split_cmdargs(resolve_plantuml_command(vendored_jar))

    assert argv == ["java", "-Djava.awt.headless=true", "-jar", str(vendored_jar)]


def test_windows_prefers_the_blocking_shim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """On Windows route (3) asks for ``plantumlc`` before ``plantuml``.

    sphinxcontrib.plantuml runs the command synchronously, and the chocolatey package's
    ``plantuml`` shim is a non-blocking ``javaw`` launcher -- so a build that used it
    would race its own renderer. ``plantumlc`` is the blocking ``java`` one.
    """
    monkeypatch.setattr(os, "name", "nt")
    monkeypatch.setattr(shutil, "which", lambda name: f"C:/bin/{name}.exe")

    assert (
        resolve_plantuml_command(tmp_path / "utils" / "plantuml.jar")
        == "C:/bin/plantumlc.exe"
    )


def test_elsewhere_the_plain_executable_is_used(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Off Windows ``plantumlc`` is not asked for at all -- it is a chocolatey artefact."""
    monkeypatch.setattr(os, "name", "posix")
    asked: list[str] = []

    def _which(name: str) -> str | None:
        asked.append(name)
        return f"/usr/local/bin/{name}"

    monkeypatch.setattr(shutil, "which", _which)

    assert (
        resolve_plantuml_command(tmp_path / "utils" / "plantuml.jar")
        == "/usr/local/bin/plantuml"
    )
    assert asked == ["plantuml"]


def test_a_missing_utils_directory_is_not_an_error(tmp_path: Path) -> None:
    """`copy_test_utils` declines quietly when there is nothing to copy.

    flit writes no directory entries into the sdist and ``doc_test/utils`` holds exactly
    one file, so a packager who strips ``*.jar`` from the tarball is left without the
    directory. Unguarded, the session fixture would raise ``FileNotFoundError`` before
    the precedence chain above was consulted at all -- and the sdist route this whole
    module exists for would be unreachable.
    """
    destination = tmp_path / "tempdir" / "utils"
    destination.parent.mkdir()

    copy_test_utils(tmp_path / "not-there", destination)

    assert not destination.exists()


def test_a_present_utils_directory_is_copied(tmp_path: Path) -> None:
    """The ordinary case: the directory and its contents arrive in the tempdir."""
    source = tmp_path / "doc_test" / "utils"
    source.mkdir(parents=True)
    (source / "plantuml.jar").write_bytes(b"not really a jar")
    destination = tmp_path / "tempdir" / "utils"
    destination.parent.mkdir()

    copy_test_utils(source, destination)

    assert (destination / "plantuml.jar").read_bytes() == b"not really a jar"
