"""The ``code`` hop of a need in a docstring autodoc reads.

Autodoc gives a docstring's text the source ``<file>:docstring of <name>``, where
``<name>`` is the object's ``__module__`` and ``__qualname__`` (its definition, not the
path it is documented under). The hop records the file of the module that name resolves
to, the language ``python``, and the name's part in that file as sphinx-codelinks'
Python rule reads it from the file's syntax: ``class``; ``method`` for a ``def`` directly
in a class; ``function`` for any other ``def``; ``<locals>`` implied after a ``def``, not
an entry. An attribute (a ``#:`` comment) is a leaf ``attribute``. A module docstring,
and a name the file's syntax does not define, have no semantic location: nothing finer
than the file is known.

The project, ``doc_test/doc_need_source_autodoc``, documents one docstring of each case;
the file each row names is under its ``src`` directory, outside the Sphinx source
directory.
"""

from __future__ import annotations

import io
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from sphinx.testing.util import SphinxTestApp

from sphinx_needs._need_source import NeedSourceHop
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs_testkit import assert_no_warnings
from tests.test_need_source import _compact

PROJECT = Path(__file__).parent / "doc_test" / "doc_need_source_autodoc"

_SHAPES = "code srcdir:../src/docstring_hops/shapes.py (python)"
_FACTORY = "code srcdir:../src/docstring_hops/factory.py (python)"

#: every need's code hop, its first; the second is its page
EXPECTED: dict[str, str] = {
    # the module docstring: the file
    "R_MODULE": _SHAPES,
    "R_FUNC": f"{_SHAPES} :: function 'area_of'",
    "R_CLASS": f"{_SHAPES} :: class 'Shape'",
    "R_METHOD": f"{_SHAPES} :: class 'Shape' > method 'area'",
    # the syntax' kinds, not autodoc's objtypes (which the page hop keeps)
    "R_STATIC": f"{_SHAPES} :: class 'Shape' > method 'make'",
    "R_CLASSMETHOD": f"{_SHAPES} :: class 'Shape' > method 'build'",
    "R_PROPERTY": f"{_SHAPES} :: class 'Shape' > method 'size'",
    "R_NESTED": f"{_SHAPES} :: class 'Shape' > class 'Inner'",
    "R_NESTED_METHOD": f"{_SHAPES} :: class 'Shape' > class 'Inner' > method 'deep'",
    "R_EXCEPTION": f"{_SHAPES} :: class 'Oops'",
    # documented under ``Shape`` in shapes.py, defined in base.py: the file it is in
    "R_INHERITED": (
        "code srcdir:../src/docstring_hops/base.py (python)"
        " :: class 'Base' > method 'describe'"
    ),
    # ``make.<locals>.Made``: the ``<locals>`` is implied by the function before it
    "R_MADE": f"{_FACTORY} :: function 'make' > class 'Made'",
    "R_MADE_METHOD": f"{_FACTORY} :: function 'make' > class 'Made' > method 'go'",
    # attributes (``#:``): a leaf ``attribute``, under its class or at the file
    "R_ATTR": f"{_SHAPES} :: class 'Shape' > attribute 'sides'",
    "R_DATA": f"{_SHAPES} :: attribute 'LIMIT'",
    # an alias of a function of the same file: autodoc names the docstring by the
    # function, so the hop does (a KNOWN GAP: the text is the alias' comment)
    "R_ALIAS_HERE": f"{_FACTORY} :: function 'make'",
    # an alias of a function with no Python source (``builtins.len``): the file autodoc
    # gives, nothing finer
    "R_ALIAS_BUILTIN": _FACTORY,
    # a function made by ``exec``: its name is no definition of the file's syntax
    "R_GENERATED": _FACTORY,
}


@pytest.fixture(scope="module")
def hops(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[dict[str, tuple[NeedSourceHop, ...]]]:
    """The project, built once from its own copy: every need's hops."""
    root = tmp_path_factory.mktemp("autodoc") / "project"
    shutil.copytree(PROJECT, root)
    app = SphinxTestApp(
        "html",
        srcdir=root / "docs",
        freshenv=True,
        status=io.StringIO(),
        warning=io.StringIO(),
    )
    try:
        app.build()
        assert_no_warnings(app)
        yield {
            need_id: need.source.hops
            for need_id, need in SphinxNeedsData(app.env).get_needs_view().items()
        }
    finally:
        app.cleanup()


def test_the_project_holds_exactly_the_pinned_needs(
    hops: dict[str, tuple[NeedSourceHop, ...]],
) -> None:
    assert sorted(hops) == sorted(EXPECTED)


@pytest.mark.xfail(
    strict=True, reason="the docstring hop is not in codelinks' Python vocabulary yet"
)
@pytest.mark.parametrize("need_id", sorted(EXPECTED))
def test_a_docstring_s_code_hop(
    hops: dict[str, tuple[NeedSourceHop, ...]], need_id: str
) -> None:
    code, page = hops[need_id]
    assert _compact(code) == EXPECTED[need_id]
    assert (page.kind, page.document) == ("page", "index")
