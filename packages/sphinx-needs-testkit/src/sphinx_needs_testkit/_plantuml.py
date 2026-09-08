"""How this workspace's suites render PlantUML -- and how they refuse to.

Two halves, and both are the workspace's rather than any one package's:

* :func:`workspace_plantuml_jar` and :func:`resolve_plantuml_command` answer "what should
  ``plantuml`` be set to", from the jar this repository commits under ``vendor/plantuml/``
  or from an explicit ``PLANTUML_JAR``. ``tools/src/sn_tools/fetch_plantuml.py`` still owns
  the pin and its hash; this only reads the version out of it.
* :func:`make_plantuml_inert` makes a build that did NOT ask to render incapable of doing
  so, rather than merely unconfigured -- because sphinxcontrib-plantuml's own default is
  the bare word ``plantuml``, which renders for real with whatever unpinned renderer the
  developer's machine happens to carry, silently.
"""

from __future__ import annotations

import os
import shutil
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING

from docutils import nodes
from sphinx.testing.util import SphinxTestApp

if TYPE_CHECKING:
    import pytest

# The jar path is DOUBLE-QUOTED. sphinxcontrib-plantuml passes a list or tuple through
# untouched and `shlex`-splits anything else -- `posix=True` off Windows, `posix=False`
# plus its own `_ntunquote` on it -- so an unquoted path containing a space arrives as
# two argv elements and the render dies. Both split paths strip these quotes again, so
# the argv is unchanged for a path without one. sphinx-mounts solves the same problem by
# returning a tuple; a string is what this function's callers already pass around.
_PLANTUML_JAVA = 'java -Djava.awt.headless=true -jar "{}"'

#: Where the workspace keeps its one renderer, relative to the repository root.
_PIN = Path("vendor") / "plantuml" / "pin.toml"


def workspace_plantuml_jar() -> Path | None:
    """The workspace's one PlantUML jar, committed under ``vendor/plantuml/``.

    Computed from the pin rather than hard-coded, because the version is IN the filename
    (``plantuml-<version>.jar``) and ``vendor/plantuml/pin.toml`` is the one place this
    repository writes it -- the jar this replaced was called ``plantuml.jar`` and was four
    years old without anyone noticing.

    The repository root is found by walking UP from this file until a
    ``vendor/plantuml/pin.toml`` appears, rather than by counting directories: this module
    is installed from a member two levels below the root in a checkout, from
    ``site-packages`` in the release workflow's import check, and from neither in an sdist,
    and a fixed index would silently name a different directory in each.

    Returns ``None`` when there is no pin to find, which is what everything but a checkout
    looks like: ``vendor/`` sits at the repository root and is in no distribution, so
    neither the pin nor the jar is in any wheel or tarball. That is the case route (3) of
    :func:`resolve_plantuml_command` exists for.

    This reads the TOML itself instead of importing ``tools/src/sn_tools/fetch_plantuml.py``
    (which computes the same path) on purpose: the tooling is a virtual member run by path
    and installed into nothing, so a test suite that imported it would only work from a
    checkout -- exactly the tree that does not need this fallback reasoning.

    :return: The pinned jar's path, or ``None`` if no pin was found above this file.
    """
    for directory in Path(__file__).resolve().parents:
        pin = directory / _PIN
        if pin.is_file():
            version = tomllib.loads(pin.read_text(encoding="utf-8"))["version"]
            return pin.parent / f"plantuml-{version}.jar"
    return None


def resolve_plantuml_command(workspace_jar: Path | None) -> str:
    """Work out how a suite renders PlantUML, from three sources in this order.

    The point of the chain is that the jar's *location* is an implementation detail of
    the workspace rather than a fact its callers have to know.

    1. ``PLANTUML_JAR``, run through ``java``. Naming a jar is an explicit choice, so it
       wins: it is how sphinx-mounts' suite is already pointed at a renderer, and it is
       the only route open to someone running a suite from a tree with no ``vendor/`` above
       it -- a package directory copied out of the repository, or the ``site-packages`` the
       release workflow's compat cell installs this member into. No sdist this workspace
       builds ships a suite at all. A variable that is set but names no
       file is a mistake worth a red run rather than a silent fall-through: falling through
       would render with a renderer the caller did not ask for and say nothing.
    2. The workspace's committed jar, ``vendor/plantuml/plantuml-<pinned version>.jar``.
       The default in a checkout, which carries it; every rendering poe task additionally
       declares ``deps = ["fetch-plantuml"]``, which hashes it against the pin.
    3. A ``plantuml`` executable on ``PATH`` -- and only once (2) is gone. These suites
       render for real and assert on the output, so a developer machine that happens to
       carry a homebrew ``plantuml`` must not quietly swap the renderer version out from
       under them. The executable is the fallback for a tree with no jar, not a preference.

    An EMPTY ``PLANTUML_JAR`` is treated as unset rather than as a mistake, because that
    is how it arrives: a developer shell with ``PLANTUML_JAR=`` exported, and a workflow
    that computes the value with an expression. sphinx-mounts reads it the same way.

    :param workspace_jar: The pinned jar's path, or ``None`` if this tree carries no pin.
    :return: The value for the ``plantuml`` configuration.
    """
    env_jar = os.environ.get("PLANTUML_JAR")
    if env_jar:
        if not Path(env_jar).is_file():
            raise RuntimeError(
                f"PLANTUML_JAR names {env_jar!r}, which is not a file. "
                "Point it at a plantuml jar, or unset it to render with the "
                "jar committed at vendor/plantuml/."
            )
        return _PLANTUML_JAVA.format(env_jar)
    if workspace_jar is not None and workspace_jar.is_file():
        return _PLANTUML_JAVA.format(workspace_jar)
    # sphinxcontrib.plantuml invokes the command synchronously; on Windows the
    # chocolatey package's `plantuml` shim is non-blocking (javaw), so its `plantumlc`
    # (java) shim is the one to use there -- a lesson sphinx-mounts has already paid for
    # (see `_plantuml_extra_conf` in its tests/test_path_directives.py)
    for name in ("plantumlc", "plantuml") if os.name == "nt" else ("plantuml",):
        if executable := shutil.which(name):
            return executable
    # Two messages, because two trees. In a CHECKOUT the fix is the task, so it leads. In a
    # tree with no pin -- an sdist -- there is no `vendor/`, no root `pyproject.toml` and no
    # poe to run it with, so leading with `poe fetch-plantuml` would be an instruction the
    # reader cannot follow; the two routes that do work lead instead. `docs/conf.py` and
    # `performance/performance_test.py` say the same two things in the same order.
    if workspace_jar is None:
        raise RuntimeError(
            "no PlantUML to render with: no `plantuml` (nor, on Windows, `plantumlc`) is "
            "on PATH and PLANTUML_JAR is unset, and this tree has no "
            "vendor/plantuml/pin.toml naming one -- which is what an sdist looks like. "
            "Set PLANTUML_JAR to a plantuml jar (with java on PATH), or install a "
            "plantuml executable; in a checkout of the repository, "
            "`uv run poe fetch-plantuml` downloads the pinned one."
        )
    raise RuntimeError(
        f"no PlantUML to render with: {workspace_jar} does not exist, no `plantuml` "
        "(nor, on Windows, `plantumlc`) is on PATH, and PLANTUML_JAR is unset. Run "
        "`uv run poe fetch-plantuml` to download the pinned jar, or set PLANTUML_JAR "
        "to a plantuml jar of your own (with java on PATH), or install a plantuml "
        "executable."
    )


# The ``plantuml`` command for a build that did NOT opt in: one that cannot be run. Not
# merely a placeholder -- sphinxcontrib-plantuml's own default is the bare word
# ``plantuml``, so a build left on the default renders for real, silently, with whatever
# unpinned renderer the developer's machine happens to carry. One token, no spaces, so
# that whatever splits it (``shlex`` off Windows, sphinxcontrib's own unquoting on it)
# still names it in the ``plantuml command %r cannot be run`` error it raises.
_INERT_PLANTUML_COMMAND = (
    "sphinx-needs-tests-this-build-did-not-opt-into-plantuml"
    "--add-plantuml-True-to-its-test_app-parameters"
)


def _skip_plantuml_node(self, node: nodes.Element) -> None:
    """Visit a ``plantuml`` node by dropping it: no subprocess, no warning, no markup."""
    raise nodes.SkipNode


def _refuse_to_render(*args: object, **kwargs: object) -> None:
    """Stand in for sphinxcontrib-plantuml's renderer on a build that did not opt in."""
    raise AssertionError(
        "PlantUML rendering was reached by a build that did not opt into it. "
        "Add '\"plantuml\": True' to that test's test_app parameter dict if it means "
        "to render -- or, for a bare `make_app` caller, set `plantuml` in its "
        "confoverrides; otherwise find out what got past the inert node visitors."
    )


def make_plantuml_inert(app: SphinxTestApp) -> None:
    """Neutralise PlantUML rendering for one app, for a test that did not opt in.

    Three layers, and each covers what the one before it cannot:

    * every node visitor sphinxcontrib-plantuml registers is replaced with one that raises
      ``SkipNode``. That is where the time goes: the directive still parses and the node
      still reaches the doctree -- so the tests that inspect ``plantuml`` nodes, or the
      ``.puml`` files sphinx-needs writes itself, keep passing untouched -- but no JVM
      starts, and a JVM start is 2.04 s of every 2.13 s render, measured.
    * THIS APP'S OWN ``PlantumlBuilder`` has its two render entry points replaced with one
      that raises. That is the assertion that nothing renders, and it is made on the app
      rather than on the output directory because a rendered file found in a directory
      cannot be attributed to any particular application, while a call reaching this
      object can only have come from this one.
    * the ``plantuml`` configuration is pointed at :data:`_INERT_PLANTUML_COMMAND`. This one
      is a SENTINEL rather than a fence, and the difference is worth stating: its whole
      protection is that the token cannot be ``exec``-ed, and when sphinxcontrib does try it
      the resulting ``PlantUmlError`` is caught by its own ``_prepare_html_render``, logged as
      a warning and turned into a ``SkipNode`` -- so a build that got past both layers above
      would warn and drop the diagram rather than fail. It also does not reach the batch
      renderer: ``PlantumlBuilder.__init__`` freezes ``_base_cmdargs`` at ``builder-inited``,
      before this function runs, and only ``render()`` and ``render_plantuml_inline()`` read
      the live config (layer two is what covers that path). What it does buy is that "not
      opted in" never means "run sphinxcontrib's default", which is the bare word
      ``plantuml`` -- i.e. render with an unpinned renderer, and say nothing.

    Layer one could also be spelled with a PUBLIC config value: ``plantuml_output_format =
    "none"`` makes ``_prepare_html_render`` raise ``SkipNode`` and zeroes the batch path's
    ``image_formats``, in every sphinxcontrib-plantuml back to 0.18.1. It is not used here
    because it covers only the html and latex builders, where ``_NODE_VISITORS`` covers all
    seven; and the private name is safe to depend on precisely because layer two is loud --
    if a future release dropped it, the import below raises ``ImportError`` at fixture setup
    rather than quietly restoring rendering.

    **What this does NOT cover**: anything that is not this app object. A build spawned as
    a subprocess is a process with its own config, which no patch made here can reach --
    which is one reason no test in the sphinx-needs suite spawns one.

    All of it happens after the app exists rather than through ``confoverrides``, because a
    project that does not load ``sphinxcontrib.plantuml`` -- 88 of the sphinx-needs suite's
    138 test projects -- would otherwise collect an "unknown config value 'plantuml' in
    override, ignoring" warning that it never used to have.

    :param app: The application to neutralise, already constructed and not yet built.
    """
    if "sphinxcontrib.plantuml" not in app.extensions:
        return

    from sphinxcontrib.plantuml import _NODE_VISITORS, plantuml

    app.config.plantuml = _INERT_PLANTUML_COMMAND
    app.add_node(
        plantuml,
        override=True,
        **dict.fromkeys(_NODE_VISITORS, (_skip_plantuml_node, None)),
    )
    plantuml_builder = getattr(app.builder, "plantuml_builder", None)
    if plantuml_builder is not None:
        plantuml_builder.render = _refuse_to_render
        plantuml_builder.render_batches = _refuse_to_render


def require_plantuml_extension(app: SphinxTestApp, where: str) -> None:
    """Refuse a build that asked to render but cannot: it never loaded the extension.

    Setting ``plantuml`` on a project without ``sphinxcontrib.plantuml`` in its
    ``extensions`` does not render anything -- it earns the build two warnings,
    ``unknown config value 'plantuml' in override, ignoring`` and the same for
    ``plantuml_batch_size``, which are precisely the warnings the opt-in design removed
    from the other 88 projects. Nothing rendered, no diagram was drawn, and the only
    signal is two warnings in a stream the test may not read.

    So it is refused, by name. The mistake is one line in a ``conf.py`` and the message
    says which line.

    :param app: The application that opted in, already constructed.
    :param where: What to name in the error -- the project, or the test.
    :raises RuntimeError: If the project does not load ``sphinxcontrib.plantuml``.
    """
    if "sphinxcontrib.plantuml" in app.extensions:
        return
    raise RuntimeError(
        f"{where} asked to render PlantUML, but its project does not load "
        "`sphinxcontrib.plantuml`, so nothing would be rendered and the build would "
        "collect an `unknown config value 'plantuml' in override, ignoring` warning "
        "instead. Add 'sphinxcontrib.plantuml' to that project's `extensions`, or drop "
        "the opt-in."
    )


def plantuml_conf(
    request: pytest.FixtureRequest, renders: bool = True
) -> dict[str, str]:
    """``confoverrides`` entries for a ``make_app`` caller, resolved only if it renders.

    The lazy half of :func:`plantuml_command`, for the tests that call ``make_app``
    directly. A test parametrised over more than one diagram engine renders for one
    parameter and not for the others, so naming ``plantuml_command`` in its signature
    would make every parameter need a renderer -- 61 cases in the sphinx-needs suite were
    in exactly that state, among them the whole graphviz half of a conformance corpus that
    has never drawn a PlantUML diagram in its life.

    :param request: The test's own request, used to resolve the session fixture on demand.
    :param renders: Whether this build will actually draw a PlantUML diagram.
    :return: ``{"plantuml": <command>}``, or an empty dict; splat it into ``confoverrides``.
    """
    if not renders:
        return {}
    return {"plantuml": request.getfixturevalue("plantuml_command")}
