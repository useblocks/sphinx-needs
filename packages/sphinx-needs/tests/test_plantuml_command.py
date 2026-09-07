"""The order in which the suite decides how to render PlantUML.

Every test project's ``plantuml`` configuration comes from the ``plantuml_command``
fixture, which is :func:`sphinx_needs_testkit.resolve_plantuml_command` applied to
:func:`sphinx_needs_testkit.workspace_plantuml_jar` -- the jar this repository commits at
``vendor/plantuml/`` at the version ``vendor/plantuml/pin.toml`` names. The
order that function applies is load-bearing rather than incidental, so it is asserted here
instead of being left to the several hundred rendering tests that would merely go a strange
colour if it changed:

* ``PLANTUML_JAR`` beats everything, because naming a jar is an explicit choice;
* the workspace's committed jar beats a ``plantuml`` on ``PATH``, because this suite
  renders for real and a developer machine carrying a homebrew ``plantuml`` must not
  silently swap the renderer version out from under it;
* the executable is reached only when that jar is gone -- a checkout somebody deleted it
  from, or a package directory copied out of the repository, which has no ``vendor/``
  above it because ``vendor/`` sits at the repository root and flit's ``include`` patterns
  cannot escape the package directory. That used to describe the sdist as well; from 9.0.0
  the tarball ships neither this suite nor the testkit it imports, so nobody reaches this
  chain from one -- but ``docs/conf.py``, which the sdist does ship, resolves a renderer
  the same way, and its copy of the message says the same two things in the same order.

The command it returns is a *string*, which sphinxcontrib-plantuml splits for itself, so
two of the cases below assert through that real split rather than on the string -- what has
to survive is the argv, not the spelling. :func:`sphinx_needs_testkit.copy_test_utils` is pinned
here too: it no longer copies a jar, but it is still what stands between a session fixture
and a ``FileNotFoundError`` on a directory nothing guarantees.
"""

from __future__ import annotations

import os
import re
import shutil
import tomllib
from pathlib import Path

import pytest
from sphinxcontrib.plantuml import _split_cmdargs

from sphinx_needs_testkit import (
    copy_test_utils,
    plantuml_conf,
    require_plantuml_extension,
    resolve_plantuml_command,
    workspace_plantuml_jar,
)


@pytest.fixture
def workspace_jar(tmp_path: Path) -> Path:
    """A stand-in for the committed jar under ``vendor/plantuml/``."""
    jar = tmp_path / "vendor" / "plantuml" / "plantuml-1.2026.8.jar"
    jar.parent.mkdir(parents=True)
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
    tmp_path: Path, workspace_jar: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``PLANTUML_JAR`` is chosen over both the workspace jar and an executable."""
    named = tmp_path / "somewhere-else.jar"
    named.write_bytes(b"not really a jar either")
    monkeypatch.setenv("PLANTUML_JAR", str(named))
    monkeypatch.setattr(shutil, "which", lambda _name: "/usr/local/bin/plantuml")

    assert (
        resolve_plantuml_command(workspace_jar)
        == f'java -Djava.awt.headless=true -jar "{named}"'
    )


def test_the_workspace_jar_is_the_default(
    workspace_jar: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no ``PLANTUML_JAR``, the workspace's own jar is used even when ``plantuml``
    is on ``PATH`` -- the developer-machine guard."""
    monkeypatch.setattr(shutil, "which", lambda _name: "/usr/local/bin/plantuml")

    assert (
        resolve_plantuml_command(workspace_jar)
        == f'java -Djava.awt.headless=true -jar "{workspace_jar}"'
    )


def test_an_executable_is_the_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With the jar gone -- a checkout somebody deleted it from, or a package directory
    copied out of the repository -- ``plantuml`` on ``PATH`` is used."""
    monkeypatch.setattr(shutil, "which", lambda _name: "/usr/local/bin/plantuml")

    assert (
        resolve_plantuml_command(tmp_path / "vendor" / "plantuml.jar")
        == "/usr/local/bin/plantuml"
    )


def test_a_named_jar_that_is_not_there_is_an_error(
    tmp_path: Path, workspace_jar: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A ``PLANTUML_JAR`` naming no file fails loudly, and never falls through.

    Falling back to the workspace jar here would render with a renderer the caller did not
    ask for and report nothing about it.
    """
    missing = tmp_path / "gone.jar"
    monkeypatch.setenv("PLANTUML_JAR", str(missing))
    monkeypatch.setattr(shutil, "which", lambda _name: "/usr/local/bin/plantuml")

    with pytest.raises(RuntimeError, match=_expected(missing)) as caught:
        resolve_plantuml_command(workspace_jar)

    # and the alternative it offers is the true one. The jar is COMMITTED at
    # ``vendor/plantuml/``: a checkout has it, and ``fetch_plantuml.py --verify`` -- which
    # `poe lint` and CI's Lint job run -- downloads nothing at all, so a message saying
    # ``poe fetch-plantuml`` "puts" it there named an action that path never takes. The same
    # clause is in ``docs/conf.py``, ``performance/performance_test.py`` and
    # ``tools/src/sn_tools/fetch_plantuml.py``, word for word, and this is the assertion that
    # holds this copy of it to that wording
    assert "unset it to render with the jar committed at vendor/plantuml/." in str(
        caught.value
    )


def test_no_renderer_at_all_is_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No variable, no jar and no executable names all three routes in the message.

    The first of them is a command -- ``uv run poe fetch-plantuml`` -- and it is asserted
    literally: a fresh clone renders nothing until someone runs it, so a message that said
    only "no PlantUML" would send the reader hunting for a file that was never there.
    """
    monkeypatch.setattr(shutil, "which", lambda _name: None)

    with pytest.raises(RuntimeError, match="no PlantUML to render with") as caught:
        resolve_plantuml_command(tmp_path / "vendor" / "plantuml.jar")

    message = str(caught.value)
    assert "uv run poe fetch-plantuml" in message
    assert "PLANTUML_JAR" in message
    assert "install a plantuml executable" in message


def test_an_empty_variable_is_treated_as_unset(
    workspace_jar: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An empty ``PLANTUML_JAR`` falls through to the workspace jar.

    Not a curiosity: it is how the variable arrives from a developer shell with
    ``PLANTUML_JAR=`` exported, and from a workflow that computes the value with an
    expression rather than deciding whether to set it. Read as "set but names no file"
    it would instead raise, which is a red run for every cell that does not want a jar.
    sphinx-mounts' `_plantuml_jar_command` agrees, and its own suite pins it too.
    """
    monkeypatch.setenv("PLANTUML_JAR", "")

    assert (
        resolve_plantuml_command(workspace_jar)
        == f'java -Djava.awt.headless=true -jar "{workspace_jar}"'
    )


def test_a_named_jar_that_is_a_directory_is_an_error(
    tmp_path: Path, workspace_jar: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A ``PLANTUML_JAR`` naming a directory is as wrong as one naming nothing.

    ``java -jar <a directory>`` fails at render time, far from the mistake, so this is
    the same fail-loud case as a missing file and is rejected by the same branch.
    """
    monkeypatch.setenv("PLANTUML_JAR", str(tmp_path))

    with pytest.raises(RuntimeError, match=_expected(tmp_path)):
        resolve_plantuml_command(workspace_jar)


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
    workspace_jar: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Quoting the path changes the string and not the argv."""
    monkeypatch.setattr(shutil, "which", lambda _name: None)

    argv = _split_cmdargs(resolve_plantuml_command(workspace_jar))

    assert argv == ["java", "-Djava.awt.headless=true", "-jar", str(workspace_jar)]


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
        resolve_plantuml_command(tmp_path / "vendor" / "plantuml.jar")
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
        resolve_plantuml_command(tmp_path / "vendor" / "plantuml.jar")
        == "/usr/local/bin/plantuml"
    )
    assert asked == ["plantuml"]


def test_a_missing_utils_directory_is_not_an_error(tmp_path: Path) -> None:
    """`copy_test_utils` declines quietly when there is nothing to copy.

    Which is now the ordinary case rather than the exotic one: ``doc_test/utils`` held
    exactly one file, a plantuml jar for this package alone, and the workspace's one
    shared jar is committed at ``vendor/plantuml/`` instead -- so the directory is not in the tree at all. Unguarded,
    the session fixture would raise ``FileNotFoundError`` before the precedence chain
    above was consulted, and every rendering test would fail for a reason that has nothing
    to do with rendering.
    """
    destination = tmp_path / "tempdir" / "utils"
    destination.parent.mkdir()

    copy_test_utils(tmp_path / "not-there", destination)

    assert not destination.exists()


def test_no_pin_at_all_falls_through_to_the_executable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``None`` -- a tree with no ``vendor/`` above it -- skips route (2) instead of
    crashing on it.

    ``vendor/`` is at the repository root and flit's ``include`` patterns cannot escape the
    package directory, so nothing this repository builds carries the jar or the pin that
    names it: the sdist (whose ``docs/conf.py`` resolves a renderer this way), the wheel,
    and a package directory somebody copied out of the tree.
    :func:`sphinx_needs_testkit.workspace_plantuml_jar` returns ``None`` in all of them, and
    the chain has to read that as "no workspace jar" rather than looking up a path on it.
    """
    monkeypatch.setattr(shutil, "which", lambda _name: "/usr/local/bin/plantuml")

    assert resolve_plantuml_command(None) == "/usr/local/bin/plantuml"


def test_no_pin_and_no_executable_says_which_tree_this_is(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A pinless tree with no renderer at all gets a message about a pinless tree.

    ``None does not exist`` would be the obvious way to write this and the wrong one: the
    reader is in a tree where ``poe fetch-plantuml`` does not exist either -- an sdist
    building its shipped ``docs/`` ships no ``vendor/``, no root ``pyproject.toml`` and no
    poe, and neither does a copied-out package directory -- so the message has to say that
    no pin was found rather than name a path that never was one, and it must not LEAD with
    a command that cannot be run there. The two routes that do work come first; the task is
    mentioned last and only for "a checkout of the repository".
    """
    monkeypatch.setattr(shutil, "which", lambda _name: None)

    with pytest.raises(
        RuntimeError, match=re.escape("no vendor/plantuml/pin.toml")
    ) as caught:
        resolve_plantuml_command(None)

    message = str(caught.value)
    assert message.index("Set PLANTUML_JAR") < message.index(
        "uv run poe fetch-plantuml"
    )
    assert "in a checkout of the repository" in message


def test_the_workspace_jar_is_read_from_the_pin() -> None:
    """The path the fixture actually uses, in the tree this test is running in.

    Two facts at once: the version comes out of ``vendor/plantuml/pin.toml`` rather than a
    literal, and the filename carries it -- which is exactly what the four-year-old
    ``plantuml.jar`` this replaced could not say for itself. Skipped rather than failed
    when there is no pin, which is the pinless tree the two cases above describe -- no
    longer an sdist, which stopped shipping this suite in 9.0.0, but still a package
    directory copied out of the repository. The guard stays because what it protects is the
    assertion below, which is about the pin and not about how the tree was obtained.
    """
    jar = workspace_plantuml_jar()
    if jar is None:
        pytest.skip(
            "no vendor/plantuml/pin.toml: this tree is not a repository checkout"
        )

    version = tomllib.loads((jar.parent / "pin.toml").read_text(encoding="utf-8"))[
        "version"
    ]
    assert jar.name == f"plantuml-{version}.jar"
    assert jar.parent.name == "plantuml"


def test_a_present_utils_directory_is_copied(tmp_path: Path) -> None:
    """The ordinary case: the directory and its contents arrive in the tempdir."""
    source = tmp_path / "doc_test" / "utils"
    source.mkdir(parents=True)
    (source / "plantuml.jar").write_bytes(b"not really a jar")
    destination = tmp_path / "tempdir" / "utils"
    destination.parent.mkdir()

    copy_test_utils(source, destination)

    assert (destination / "plantuml.jar").read_bytes() == b"not really a jar"


class _StubApp:
    """Just enough application for :func:`require_plantuml_extension` to read."""

    def __init__(self, *extensions: str) -> None:
        self.extensions = dict.fromkeys(extensions)


def test_an_opt_in_without_the_extension_is_refused_by_name() -> None:
    """Setting ``plantuml`` on a project that never loads the extension is a mistake.

    Nothing is rendered and no diagram is drawn; what the build gets instead is ``unknown
    config value 'plantuml' in override, ignoring`` -- twice -- which is exactly the
    warning the opt-in design removed from every project that does NOT render. The only
    signal is in a warning stream the test may never read, so the harness refuses instead,
    and the message has to carry what the reader needs to fix it: which build, and both
    ways out.
    """
    with pytest.raises(RuntimeError) as caught:
        require_plantuml_extension(_StubApp("sphinx_needs"), "tests/test_x.py::test_y")

    message = str(caught.value)
    assert "tests/test_x.py::test_y" in message
    assert "does not load `sphinxcontrib.plantuml`" in message
    assert "unknown config value 'plantuml' in override, ignoring" in message
    assert "drop the opt-in" in message


def test_a_build_that_draws_nothing_never_asks_for_a_renderer() -> None:
    """The property the whole opt-in design rests on, asserted without a renderer.

    A fixture named in a test's SIGNATURE is resolved whether the body uses it or not, and
    resolving this one raises on a machine with no jar -- which is why 57 cases that have
    never drawn a PlantUML diagram used to error there, the graphviz half of a conformance
    corpus among them. :func:`sphinx_needs_testkit.plantuml_conf` is the lazy spelling, and
    "lazy" has to mean *the fixture is not even asked for*: a request whose
    ``getfixturevalue`` explodes proves that, where a green run on this machine (which has
    a jar) would prove nothing at all.
    """

    class _ExplodingRequest:
        def getfixturevalue(self, name: str) -> str:
            raise AssertionError(f"resolved {name!r} for a build that draws nothing")

    assert plantuml_conf(_ExplodingRequest(), False) == {}  # type: ignore[arg-type]

    # No converse case here, and deliberately: a `plantuml_conf` that always returned `{}`
    # would take every rendering test in this suite with it, and a guard that always raised
    # would take all twelve opt-ins. Only the one-sided halves above need a test of their
    # own -- they are the ones that regress to a green suite.
