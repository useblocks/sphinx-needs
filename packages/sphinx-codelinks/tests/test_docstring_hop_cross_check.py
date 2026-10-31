"""Autodoc's docstring hop and sphinx-codelinks' code hop name the same entity.

sphinx-needs records a need in a docstring autodoc reads as a ``code`` hop of the
Python file the docstring is defined in, with the in-file qualified name in this
package's Python kinds -- a rule it restates, since it cannot import this package. Here
both producers read the same files: each docstring holds a need of sphinx-needs (``R_*``)
and a one-line marker of this package (``CL_*``), side by side. For every function and
class, the two code hops have the same file, the same language, the same entity by
:func:`~sphinx_codelinks.analyse.entity.name_chain`, the same qualified name (the
``qualified_name`` extra of the entity: this package's analysis renders it, sphinx-needs
restates the Python rendering), and the same parts, kinds included (``name_chain``
leaves the kinds out, and does not tell a ``method`` from a ``function``), so the two
rules cannot drift apart.

An attribute is where they differ by design: sphinx-needs names the attribute autodoc
documents (a leaf ``attribute``), this package attaches the ``#:`` comment to the
enclosing class, or to the file.
"""

from __future__ import annotations

import io
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from sphinx.testing.util import SphinxTestApp

from sphinx_codelinks.analyse.entity import name_chain
from sphinx_needs.api import NeedSourceHop
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs_testkit import assert_no_warnings

_MakeApp = Callable[..., SphinxTestApp]

BASE = '''\
class Base:
    def describe(self):
        """A method a class in another module inherits.

        .. req:: Inherited method
           :id: R_INHERITED

        @Inherited marker, CL_INHERITED, impl
        """
'''

SHAPES = '''\
"""The module docstring.

.. req:: Module docstring
   :id: R_MODULE

@Module marker, CL_MODULE, impl
"""

from hopcheck.base import Base


def area_of(shape):
    """A module function.

    .. req:: Module function
       :id: R_FUNC

    @Function marker, CL_FUNC, impl
    """


#: A module attribute.
#:
#: .. req:: Module attribute
#:    :id: R_DATA
#:
#: @Module attribute marker, CL_DATA, impl
LIMIT = 3


class Shape(Base):
    """A class.

    .. req:: Class
       :id: R_CLASS

    @Class marker, CL_CLASS, impl
    """

    #: A class attribute.
    #:
    #: .. req:: Class attribute
    #:    :id: R_ATTR
    #:
    #: @Class attribute marker, CL_ATTR, impl
    sides = 0

    def area(self):
        """A method.

        .. req:: Method
           :id: R_METHOD

        @Method marker, CL_METHOD, impl
        """

    @staticmethod
    def make():
        """A staticmethod.

        .. req:: Staticmethod
           :id: R_STATIC

        @Static marker, CL_STATIC, impl
        """

    @classmethod
    def build(cls):
        """A classmethod.

        .. req:: Classmethod
           :id: R_CLASSMETHOD

        @Classmethod marker, CL_CLASSMETHOD, impl
        """

    @property
    def size(self):
        """A property.

        .. req:: Property
           :id: R_PROPERTY

        @Property marker, CL_PROPERTY, impl
        """
        return 1

    class Inner:
        """A nested class.

        .. req:: Nested class
           :id: R_NESTED

        @Nested marker, CL_NESTED, impl
        """

        def deep(self):
            """A method of the nested class.

            .. req:: Nested method
               :id: R_NESTED_METHOD

            @Nested method marker, CL_NESTED_METHOD, impl
            """


class Oops(Exception):
    """An exception.

    .. req:: Exception
       :id: R_EXCEPTION

    @Exception marker, CL_EXCEPTION, impl
    """
'''

FACTORY = '''\
def make():
    class Made:
        """A class made in a function.

        .. req:: Made class
           :id: R_MADE

        @Made marker, CL_MADE, impl
        """

        def go(self):
            """Its method.

            .. req:: Made method
               :id: R_MADE_METHOD

            @Made method marker, CL_MADE_METHOD, impl
            """

    return Made


Made = make()
'''

CONF = """\
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "src"))
for _name in [name for name in sys.modules if name.partition(".")[0] == "hopcheck"]:
    del sys.modules[_name]

extensions = ["sphinx_needs", "sphinx_codelinks", "sphinx.ext.autodoc"]
exclude_patterns = ["_build"]
# the project is in no git repository, so it has no blob links
suppress_warnings = ["codelinks.git_root"]
"""

TOML = """\
[codelinks.projects.py.source_discover]
src_dir = "../src/hopcheck"
comment_type = "python"

[codelinks.projects.py.analyse]
get_oneline_needs = true
"""

INDEX = """\
Cross-check
===========

.. automodule:: hopcheck.shapes
   :members:
   :inherited-members:

.. automodule:: hopcheck.factory
   :members:

.. src-trace::
   :project: py
"""

FILES = {
    "docs/conf.py": CONF,
    "docs/ubproject.toml": TOML,
    "docs/index.rst": INDEX,
    "src/hopcheck/__init__.py": "",
    "src/hopcheck/base.py": BASE,
    "src/hopcheck/shapes.py": SHAPES,
    "src/hopcheck/factory.py": FACTORY,
}

#: every function and class case, and the module docstring (the file, on both sides)
ENTITIES = [
    "MODULE",
    "FUNC",
    "CLASS",
    "METHOD",
    "STATIC",
    "CLASSMETHOD",
    "PROPERTY",
    "NESTED",
    "NESTED_METHOD",
    "EXCEPTION",
    "INHERITED",
    "MADE",
    "MADE_METHOD",
]


@pytest.fixture
def code_hops(make_app: _MakeApp, tmp_path: Path) -> dict[str, NeedSourceHop]:
    """Build the project; every need's first hop, its code hop."""
    for name, content in FILES.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    app = make_app(
        "html", srcdir=tmp_path / "docs", freshenv=True, warning=io.StringIO()
    )
    app.build()
    assert_no_warnings(app)
    return {
        need_id: need.source.hops[0]
        for need_id, need in SphinxNeedsData(app.env).get_needs_view().items()
    }


def _qualified_name(hop: NeedSourceHop) -> str | None:
    """The entity's qualified name, the ``qualified_name`` extra of the hop's innermost
    entry; ``None`` for a hop with no semantic location."""
    if not hop.semantic:
        return None
    return dict(hop.semantic[-1].extras).get("qualified_name")


def _identity(hop: NeedSourceHop) -> tuple[Any, ...]:
    """What names a code hop's entity -- its file, its language, its name chain over the
    analysis' components (the hop's own ``qualified_name`` extra left out), and the
    qualified name -- and its parts as values, kinds and extras included."""
    parts: list[Any] = [
        {
            "kind": p.kind,
            "name": p.name,
            **{key: value for key, value in p.extras if key != "qualified_name"},
        }
        for p in hop.semantic or ()
    ]
    physical = hop.physical
    return (
        hop.kind,
        None if physical is None else (physical.root, physical.path),
        hop.language,
        name_chain(parts if hop.semantic is not None else None, hop.language or ""),
        _qualified_name(hop),
        None
        if hop.semantic is None
        else [(p.kind, p.name, p.extras) for p in hop.semantic],
    )


def test_the_project_holds_both_producers_needs(
    code_hops: dict[str, NeedSourceHop],
) -> None:
    assert sorted(code_hops) == sorted(
        f"{side}_{case}" for side in ("R", "CL") for case in [*ENTITIES, "DATA", "ATTR"]
    )


def test_both_producers_name_the_same_entity(
    code_hops: dict[str, NeedSourceHop],
) -> None:
    """For every function and class, and the module docstring: one file, ``python``, one
    name chain, the same kinds."""
    assert {case: _identity(code_hops[f"R_{case}"]) for case in ENTITIES} == {
        case: _identity(code_hops[f"CL_{case}"]) for case in ENTITIES
    }
    assert {code_hops[f"R_{case}"].language for case in ENTITIES} == {"python"}


def test_an_attribute_differs_by_design(code_hops: dict[str, NeedSourceHop]) -> None:
    """sphinx-needs names the attribute autodoc documents; this package attaches its
    ``#:`` comment to the enclosing class, or to the file: the same file and language,
    and the class' name chain a prefix of the attribute's."""

    def parts(need_id: str) -> list[tuple[str, str]] | None:
        semantic = code_hops[need_id].semantic
        return None if semantic is None else [(p.kind, p.name) for p in semantic]

    assert parts("R_ATTR") == [("class", "Shape"), ("attribute", "sides")]
    assert parts("CL_ATTR") == [("class", "Shape")]
    assert parts("R_DATA") == [("attribute", "LIMIT")]
    assert parts("CL_DATA") is None
    for case in ("ATTR", "DATA"):
        ours, theirs = (
            _identity(code_hops[f"R_{case}"]),
            _identity(code_hops[f"CL_{case}"]),
        )
        assert ours[:3] == theirs[:3]
        ours_chain, theirs_chain = ours[3], theirs[3] or ()
        assert ours_chain[: len(theirs_chain)] == theirs_chain


def test_both_producers_render_the_same_qualified_name(
    code_hops: dict[str, NeedSourceHop],
) -> None:
    """The entity's ``qualified_name`` extra: this package's rendering of the analysis,
    and sphinx-needs' of the parts it reads from the syntax, are one string for every
    function and class (``make.<locals>.Made.go``); the module docstring has none."""
    ours = {case: _qualified_name(code_hops[f"R_{case}"]) for case in ENTITIES}
    assert ours == {case: _qualified_name(code_hops[f"CL_{case}"]) for case in ENTITIES}
    assert ours["MADE_METHOD"] == "make.<locals>.Made.go"
    assert [case for case, name in ours.items() if name is None] == ["MODULE"]
