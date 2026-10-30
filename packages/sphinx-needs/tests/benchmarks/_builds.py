"""What every timed build in this directory shares.

A timed build measures sphinx-needs, so three things the rest of the suite does to a
build are left out of it:

* **PlantUML renders nothing.** Every diagram is one JVM start, about two seconds, and
  the official documentation draws some 85 of them: measured, a full build takes 66-73 s
  with rendering and 18.5 s without, so three quarters of the old number was Java -- and
  JVM start-up is what varies most between CI runners. The directives still parse, so
  sphinx-needs' own half of every diagram (the filtering, the generated PlantUML source)
  is still timed.
* **No suite fence runs.** ``tests/conftest.py`` wraps ``analyse_need_locations`` for the
  whole session and connects a parent-child walk of every resolved doctree to each
  ``test_app``: both are assertions about the product, not the product.
* **Every round is a fresh application** with a fresh environment, so each round reads and
  writes every document. A second ``build_all`` on the same application would find
  nothing outdated and time the writing alone.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from sphinx.testing.util import SphinxTestApp

import sphinx_needs.needs
from sphinx_needs.directives.need import analyse_need_locations
from sphinx_needs_testkit import make_plantuml_inert


@contextmanager
def unfenced() -> Iterator[None]:
    """Applications set up inside this block run sphinx-needs' own doctree walk.

    ``setup()`` looks ``analyse_need_locations`` up by name on :mod:`sphinx_needs.needs`
    when each application is set up, which is where the session's fence replaces it.
    """
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(
            sphinx_needs.needs, "analyse_need_locations", analyse_need_locations
        )
        yield


def time_html_builds(
    benchmark: Any,
    make_app: Callable[..., SphinxTestApp],
    srcdir: Path,
    *,
    rounds: int,
    prepare: Callable[[SphinxTestApp], None] | None = None,
) -> SphinxTestApp:
    """Time ``rounds`` full html builds of ``srcdir``, each on a fresh application.

    :param benchmark: The ``benchmark`` fixture of pytest-benchmark.
    :param make_app: The suite's ``make_app`` fixture.
    :param srcdir: A project already copied out of the tree, built in place.
    :param rounds: How many builds to time; the workflow reports the fastest.
    :param prepare: Called on each application after it is made and before it is timed.
    :return: The application of the last round, built.
    """
    apps: list[SphinxTestApp] = []

    def setup() -> tuple[tuple[SphinxTestApp], dict[str, Any]]:
        with unfenced():
            app = make_app(buildername="html", srcdir=srcdir, freshenv=True)
        make_plantuml_inert(app)
        if prepare is not None:
            prepare(app)
        apps.append(app)
        return (app,), {}

    benchmark.pedantic(
        lambda app: app.builder.build_all(), setup=setup, rounds=rounds, iterations=1
    )
    return apps[-1]
