"""The ``source.*`` facets of a filter: where a need comes from, by named position.

A need's hops (:class:`~sphinx_needs.need_item.NeedItemSource`, innermost first) are
provisional; the facets are the stable view a filter reads of them. Each facet names a
position in the hop list, never a producer, so a longer chain needs no new rule:

- ``kind``: the producer, read from the whole chain (:func:`kind_of`);
- ``path``, ``line``, ``symbol``: ``hops[0]``, the innermost hop;
- ``paths``: every hop;
- ``document``, ``sections``: the placement, read for now from the legacy ``docname``
  and ``sections`` they are aliases of.

A facet that is not yet knowable is ``None`` (``()`` for ``paths``), and later data
only fills it: an imported or external need has no ``path`` until the upstream file is
recorded, a test case none until its code root is known. A path is POSIX and relative
to the Sphinx source directory (a hop whose ``root`` is ``"srcdir"``), with ``..`` for a
file outside it; a hop under another root, or with a URL alone, has none.

One function per facet, each costing its own work only, over a source and the need it
belongs to. No Sphinx import of its own and no environment: the facets are computed
from what a need holds, which the legacy projections of the hops will reuse.

``paths`` is the one facet that may gain an entry rather than fill a ``None``, as more
of a chain is recorded (a test case's test file once its root is known; MyST include
chains; a file included through a ``:parser:`` include on docutils 0.22 and later);
filters test membership of it.

The rule for the legacy projections (slice 4): ``document`` and ``sections`` are derived
from the placement hop where there is one, else from an ``external`` hop's own section
chain, else they stay the legacy read. Derived from the placement alone, five kinds of
need would move: a hop-less ``NeedItemSource()`` and ``NeedItemSource((),
is_import=True)`` placed by a directive (their walked ``sections`` would become ``()``,
G15), and third-party protocol sources, plain, imported and external (their
``docname`` from ``dict_repr`` would become ``None``, their walked ``sections`` ``()``).
"""

from __future__ import annotations

import ast
import difflib
from collections.abc import Callable, Mapping
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Final

from sphinx_needs._need_source import SRCDIR_ROOT

if TYPE_CHECKING:
    from sphinx_needs._need_source import NeedSourceHop

SOURCE_NAME: Final = "source"
"""The name a filter reads the facets by, ``source.<facet>``."""

SOURCE_FACETS: Final = (
    "document",
    "kind",
    "line",
    "path",
    "paths",
    "sections",
    "symbol",
)
"""The facets a filter reads as ``source.<facet>``, sorted."""

_PATHLESS: Final = frozenset({"import", "external", "generated"})
"""The kinds whose ``path`` is ``None``: the file their text comes from is not one this
build records (an upstream project's, a service's)."""


def _hops(source: object) -> tuple[NeedSourceHop, ...]:
    """The hops of a source; none for one that has no ``hops`` (a third party's, which
    obeys only ``NeedItemSourceProtocol``)."""
    return getattr(source, "hops", ())


def _srcdir_path(hop: NeedSourceHop) -> str | None:
    """The hop's path, where its root is the Sphinx source directory."""
    physical = hop.physical
    if physical is None or physical.root != SRCDIR_ROOT or hop.origin is not None:
        return None
    return physical.path


def kind_of(source: Any) -> str | None:
    """``source.kind``: the producer of the need, the first rule that applies.

    ``"external"`` (``hops[0]`` is ``external``, or the need is external),
    ``"import"`` (``needimport`` read it: its stored flag, as an imported needs.json
    and an included file are both ``file`` hops), ``"report"`` (any hop is a test
    report's), ``"code"`` (``hops[0]`` is ``code``), ``"generated"`` (``hops[0]`` is
    ``generated``: a service), ``"page"`` (any ``page`` or ``file`` hop), else ``None``.
    The vocabulary is open: a later producer adds a value.
    """
    hops = _hops(source)
    keys = source.dict_repr
    first = hops[0].kind if hops else None
    if keys.get("is_import"):
        return "import"
    if first == "external" or keys.get("is_external"):
        return "external"
    if any(hop.kind == "report" for hop in hops):
        return "report"
    if first in ("code", "generated"):
        return first
    if any(hop.kind in ("page", "file") for hop in hops):
        return "page"
    return None


def path_of(source: Any) -> str | None:
    """``source.path``: ``hops[0]``'s path under the source directory.

    ``None`` for an ``import``, ``external`` or ``generated`` need, where ``hops[0]`` has
    no path under the source directory (a test case's code file, whose root is the test
    run's; a needs.json downloaded from a URL), and without hops.
    """
    hops = _hops(source)
    if not hops or kind_of(source) in _PATHLESS:
        return None
    return _srcdir_path(hops[0])


def line_of(source: Any) -> int | None:
    """``source.line``: ``hops[0]``'s start line, where ``source.path`` is not ``None``
    (the two are one hop's, so they are a coherent pair); 1-based, recorded only where
    it is a true line of the file."""
    if path_of(source) is None:
        return None
    physical = _hops(source)[0].physical
    return None if physical is None else physical.start_line


def paths_of(source: Any) -> tuple[str, ...]:
    """``source.paths``: every hop's path under the source directory, innermost first,
    each once.

    ``()`` for an external need, keyed on ``hops[0]`` being ``external``: a page hop
    after it can carry a local path, which is not where the need comes from.
    """
    hops = _hops(source)
    if hops and hops[0].kind == "external" and not source.dict_repr.get("is_import"):
        return ()
    return tuple(
        dict.fromkeys(path for hop in hops if (path := _srcdir_path(hop)) is not None)
    )


def symbol_of(source: Any) -> str | None:
    """``source.symbol``: where ``hops[0]`` is ``code``, the ``qualified_name`` extra of
    its innermost semantic entry, the entity as its producer renders it
    (``ns::Widget::draw``, ``Shape.area.<locals>.inner``); otherwise ``None``."""
    hops = _hops(source)
    if not hops or hops[0].kind != "code" or not hops[0].semantic:
        return None
    return dict(hops[0].semantic[-1].extras).get("qualified_name")


def document_of(need: Any) -> str | None:
    """``source.document``: the need's ``docname``, the document it is placed on."""
    return need["docname"]


def sections_of(need: Any) -> Any:
    """``source.sections``: the need's ``sections``, innermost first."""
    return need["sections"]


def _read_kind(need: Any) -> str | None:
    return kind_of(need.source)


def _read_path(need: Any) -> str | None:
    return path_of(need.source)


def _read_line(need: Any) -> int | None:
    return line_of(need.source)


def _read_paths(need: Any) -> tuple[str, ...]:
    return paths_of(need.source)


def _read_symbol(need: Any) -> str | None:
    return symbol_of(need.source)


READERS: Final[Mapping[str, Callable[[Any], Any]]] = {
    "document": document_of,
    "kind": _read_kind,
    "line": _read_line,
    "path": _read_path,
    "paths": _read_paths,
    "sections": sections_of,
    "symbol": _read_symbol,
}
"""Each facet's reader of a need (a part's need, for a part): one per name of
:data:`SOURCE_FACETS`."""


def unknown_facet(name: str) -> str:
    """The error of ``source.<name>`` naming no facet, with the closest facet."""
    close = difflib.get_close_matches(name, SOURCE_FACETS, 1, 0.8)
    if close:
        return f"source has no facet {name!r} (did you mean {close[0]!r}?)"
    return f"source has no facet {name!r} (its facets: {', '.join(SOURCE_FACETS)})"


class SourceFacets:
    """What ``source`` is in a filter ``eval`` evaluates: each facet computed when it is
    read, so a filter pays for the facets it names alone."""

    __slots__ = ("_need",)

    def __init__(self, need: Any) -> None:
        """:param need: The need (a part's need, for a part)."""
        self._need = need

    def __getattr__(self, name: str) -> Any:
        reader = READERS.get(name)
        if reader is None:
            raise AttributeError(unknown_facet(name))
        return reader(self._need)

    # one need's facets are equal however often they are read: the parsed tier reads
    # ``source`` once per operand, where ``eval`` binds it once
    def __eq__(self, other: object) -> bool:
        return isinstance(other, SourceFacets) and other._need is self._need

    def __hash__(self) -> int:
        return id(self._need)

    def __repr__(self) -> str:
        return f"<source of {self._need['id']!r}>"


@lru_cache(maxsize=256)
def reads_a_facet(expression: str) -> bool:
    """Whether an expression reads a facet, ``source.<facet>`` for a name of
    :data:`SOURCE_FACETS` -- not any attribute of ``source``: a method of a field named
    ``source`` (``source.startswith(...)``) is no facet read. False for an expression
    that does not parse. Cached per string."""
    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except (SyntaxError, ValueError):
        return False
    return any(
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == SOURCE_NAME
        and node.attr in READERS
        for node in ast.walk(tree)
    )


def source_undefined(error: BaseException) -> bool:
    """Whether *error* is ``source`` undefined, where an expression is evaluated with no
    facets."""
    return isinstance(error, NameError) and getattr(error, "name", None) == SOURCE_NAME


def unavailable(error: BaseException, expression: str) -> bool:
    """Whether an expression evaluated where there are no facets failed for want of
    them: ``source`` undefined there, or a facet read failing on what ``source`` is
    there (a field named ``source``, a record's key)."""
    return source_undefined(error) or reads_a_facet(expression)


def explained(error: BaseException, where: str, expression: str) -> str:
    """The text of an error of *expression*, evaluated where there are no facets
    (*where*: a field predicate, a needimport filter, a variant condition), with why,
    where it failed for want of them (:func:`unavailable`)."""
    if unavailable(error, expression):
        return f"{error}; the source.* facets are not available in {where}"
    return str(error)
