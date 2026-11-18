"""The ``c.source`` facets of a filter: where a need comes from, by named position.

A need's hops (:class:`~sphinx_needs.need_item.NeedItemSource`, innermost first) are
provisional; the facets are the stable view a filter reads of them, as
``c.source.<facet>``: ``c`` is the need's check context, which the filter context sets
over every field, beside ``c.this_doc()`` and ``c.is_a()``, so no field a project
declares can shadow them. Each facet names a position in the hop list, never a
producer, so a longer chain needs no new rule:

- ``kind``: the producer, read from the whole chain and the need's import and external
  flags (:func:`kind_of`);
- ``path``, ``line``, ``symbol``: ``hops[0]``, the innermost hop;
- ``paths``: every hop;
- ``document``, ``sections``: the placement, read for now from the legacy ``docname``
  and ``sections`` they are aliases of.

A facet that is not yet knowable is ``None`` (``()`` for ``paths``), and later data
only fills it: an imported or external need has no ``path`` until the upstream file is
recorded, a test case none until its code root is known (the innermost place of a test
case is its test code: a test case whose report gives no test file has the report as
``hops[0]``, which is not where the case is written, so its path is ``None``; a case's
code hop answers once its root is known). A path is POSIX
and relative to the Sphinx source directory (a hop whose ``root`` is ``"srcdir"``), with
``..`` for a file outside it; a hop under another root, or with a URL alone, has none.

One function per facet, each costing its own work only, over a source and the need it
belongs to. No Sphinx import of its own and no environment: the facets are computed
from what a need holds.

``paths`` is the one facet that may gain an entry rather than fill a ``None``, as more
of a chain is recorded (a test case's test file once its root is known; MyST include
chains; a file included through a ``:parser:`` include on docutils 0.22 and later);
filters test membership of it.

The legacy projections (slice 4a): ``document`` and ``sections`` stay reads of the
need's ``docname`` and ``sections``, which ARE the placement hop's where a need has one.
``docname`` is a ``NeedItemSource``'s placement ``document``; ``sections`` (with
``signature``) is written once, as the projection of the semantic location the
doctree-read walk puts on the placement hop (``project_legacy(placement_semantic(node))``),
so there is no second walk to agree with. They stay stored fields rather than reads of
the hops, because the hops cannot answer for every need: the same walk writes the
``sections`` of a need with no placement hop (a hop-less ``NeedItemSource()``,
``NeedItemSource.on_page(None)`` or ``NeedItemSource((), is_import=True)`` placed by a
directive, G15; a third-party protocol source, whose ``docname`` is its ``dict_repr``'s),
and a need no walk visits keeps the value it was given (an external need's record, an
``add_need(sections=...)`` whose nodes are discarded). Read from the hops, the order
would be an ``external`` ``hops[0]`` first (its section chain, ``None`` giving ``()``),
then the placement's semantic location, with a stored fallback all the same; an external
need's ``signature`` is on no hop.
"""

from __future__ import annotations

import ast
import difflib
from collections.abc import Callable, Iterable, Iterator, Mapping
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Final

from sphinx_needs import _id_facets
from sphinx_needs._need_source import SRCDIR_ROOT

if TYPE_CHECKING:
    from sphinx_needs._need_source import NeedSourceHop

CHECKS_NAME: Final = "c"
"""The name of a filter's check context, which holds the facets."""

SOURCE_NAME: Final = "source"
"""The attribute of the check context a filter reads the facets by,
``c.source.<facet>``."""

SOURCE_FACETS: Final = (
    "document",
    "kind",
    "line",
    "path",
    "paths",
    "sections",
    "symbol",
)
"""The facets a filter reads as ``c.source.<facet>``, sorted."""

_PATHLESS: Final = frozenset({"import", "external", "generated"})
"""The kinds whose ``path`` is ``None``: the file their text comes from is not one this
build records (an upstream project's, a service's)."""


def _hops(source: object) -> tuple[NeedSourceHop, ...]:
    """The hops of a source; none for one that has no ``hops`` (a third party's, which
    obeys only ``NeedItemSourceProtocol``)."""
    return getattr(source, "hops", ())


def _srcdir_path(hop: NeedSourceHop) -> str | None:
    """The hop's path, where its root is the Sphinx source directory of this project
    (a hop with an ``origin``, another project's, has none here)."""
    physical = hop.physical
    if physical is None or physical.root != SRCDIR_ROOT or hop.origin is not None:
        return None
    return physical.path


def kind_of(source: Any) -> str | None:
    """``c.source.kind``: the producer of the need, the first rule that applies.

    ``"import"`` (``needimport`` read it: its stored flag, as an imported needs.json
    and an included file are both ``file`` hops; first, so that an imported need stays
    one when its upstream hops arrive, an external need upstream included),
    ``"external"`` (``hops[0]`` is ``external``, or the need is external),
    ``"report"`` (any hop is a test
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


def _is_test_case(hop: NeedSourceHop) -> bool:
    """Whether a hop is a test report's place of a test case: a ``case`` entry in its
    semantic location, as sphinx-test-reports records one."""
    return hop.kind == "report" and any(
        entry.kind == "case" for entry in hop.semantic or ()
    )


def path_of(source: Any) -> str | None:
    """``c.source.path``: ``hops[0]``'s path under the source directory.

    ``None`` for an ``import``, ``external`` or ``generated`` need, where ``hops[0]`` has
    no path under the source directory (a test case's code file, whose root is the test
    run's; a needs.json downloaded from a URL), and without hops. ``None`` for a test
    case whose report gives no test file: its report is ``hops[0]``, which is not where
    the case is written (its test code is); a case's code hop answers once its root is
    known. A test file and a test suite are the report's, and keep its path.
    """
    hops = _hops(source)
    if not hops or kind_of(source) in _PATHLESS or _is_test_case(hops[0]):
        return None
    return _srcdir_path(hops[0])


def line_of(source: Any) -> int | None:
    """``c.source.line``: ``hops[0]``'s start line, where ``c.source.path`` is not ``None``
    (the two are one hop's, so they are a coherent pair); 1-based, recorded only where
    it is a true line of the file."""
    if path_of(source) is None:
        return None
    physical = _hops(source)[0].physical
    return None if physical is None else physical.start_line


def paths_of(source: Any) -> tuple[str, ...]:
    """``c.source.paths``: every hop's path under the source directory, innermost first,
    each once.

    ``()`` for an external need that is not imported, keyed on ``hops[0]`` being
    ``external``: a page hop after it can carry a local path, which is not where the
    need comes from. A hop with an ``origin`` (another project's) counts toward none.
    """
    hops = _hops(source)
    if hops and hops[0].kind == "external" and not source.dict_repr.get("is_import"):
        return ()
    return tuple(
        dict.fromkeys(path for hop in hops if (path := _srcdir_path(hop)) is not None)
    )


def symbol_of(source: Any) -> str | None:
    """``c.source.symbol``: where ``hops[0]`` is ``code``, the ``qualified_name`` extra of
    its innermost semantic entry, the entity as its producer renders it
    (``ns::Widget::draw``, ``Shape.area.<locals>.inner``); otherwise ``None``."""
    hops = _hops(source)
    if not hops or hops[0].kind != "code" or not hops[0].semantic:
        return None
    return dict(hops[0].semantic[-1].extras).get("qualified_name")


def document_of(need: Any) -> str | None:
    """``c.source.document``: the need's ``docname``, the document it is placed on."""
    return need["docname"]


def sections_of(need: Any) -> Any:
    """``c.source.sections``: the need's ``sections``, innermost first."""
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


CHECK_FACETS: Final[Mapping[str, Mapping[str, Callable[[Any], Any]]]] = {
    SOURCE_NAME: READERS,
    _id_facets.ID_NAME: _id_facets.READERS,
}
"""The facets of the check context, by the attribute of ``c`` that holds them
(``c.source.<facet>``, ``c.id.<facet>``): the one table the portable tier's 3-name chain,
the explanation where there is no check context and a derived field's whitelist read."""


def unknown_facet(name: str) -> str:
    """The error of ``c.source.<name>`` naming no facet, with the closest facet."""
    close = difflib.get_close_matches(name, SOURCE_FACETS, 1, 0.8)
    if close:
        return f"c.source has no facet {name!r} (did you mean {close[0]!r}?)"
    return f"c.source has no facet {name!r} (its facets: {', '.join(SOURCE_FACETS)})"


class SourceFacets:
    """What ``c.source`` is in a filter ``eval`` evaluates (``NeedCheckContext.source``):
    each facet computed when it is read, so a filter pays for the facets it names
    alone."""

    __slots__ = ("_need",)

    def __init__(self, need: Any) -> None:
        """:param need: The need (a part's need, for a part)."""
        self._need = need

    def __getattr__(self, name: str) -> Any:
        reader = READERS.get(name)
        if reader is None:
            raise AttributeError(unknown_facet(name))
        return reader(self._need)

    # one need's facets are equal however often they are read: each read of
    # ``c.source`` builds them anew
    def __eq__(self, other: object) -> bool:
        return isinstance(other, SourceFacets) and other._need is self._need

    def __hash__(self) -> int:
        return id(self._need)

    def __repr__(self) -> str:
        return f"<c.source of {self._need['id']!r}>"


def facet_read(node: ast.AST) -> str | None:
    """The attribute of ``c`` holding the facet *node* reads, ``c.<group>.<facet>``
    (``"source"``, ``"id"``), or ``None`` where *node* is no facet of
    :data:`CHECK_FACETS`."""
    if (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Attribute)
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == CHECKS_NAME
        and node.attr in CHECK_FACETS.get(node.value.attr, ())
    ):
        return node.value.attr
    return None


def _is_in_namespace(node: ast.AST) -> bool:
    """Whether *node* is a call of ``c.in_namespace``, whatever its arguments."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == _id_facets.IN_NAMESPACE
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == CHECKS_NAME
    )


#: what each read of the check context is called where there is none, in this order
_UNAVAILABLE: Final = (
    (SOURCE_NAME, "the c.source facets"),
    (_id_facets.ID_NAME, "the c.id facets"),
    (_id_facets.IN_NAMESPACE, "c.in_namespace()"),
)


@lru_cache(maxsize=256)
def _check_reads(expression: str) -> frozenset[str]:
    """What an expression reads of the check context: the attributes of ``c`` holding
    a facet it reads (``source``, ``id``), and ``in_namespace`` for a call of it. Empty
    for an expression that does not parse. Cached per string."""
    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except (SyntaxError, ValueError):
        return frozenset()
    reads: set[str] = set()
    for node in ast.walk(tree):
        if (group := facet_read(node)) is not None:
            reads.add(group)
        elif _is_in_namespace(node):
            reads.add(_id_facets.IN_NAMESPACE)
    return frozenset(reads)


#: the namespace values a filter can read, each as the warning names it, in the order
#: it names them: ``c.id.<facet>`` by its facet, and the call
_NAMESPACE_READS: Final = (
    ("ns", "c.id.ns"),
    ("local", "c.id.local"),
    (_id_facets.IN_NAMESPACE, "c.in_namespace()"),
)


def _is_bare_id(node: ast.AST) -> bool:
    """Whether *node* is ``c.id`` itself, which holds the facets, not the id."""
    return (
        isinstance(node, ast.Attribute)
        and node.attr == _id_facets.ID_NAME
        and isinstance(node.value, ast.Name)
        and node.value.id == CHECKS_NAME
    )


def _reached(node: ast.AST) -> Iterator[ast.AST]:
    """*node* and the nodes evaluated whenever it is: not the operands of ``and`` /
    ``or`` after the first, not the branches of a conditional (its test is), not the
    body of a lambda or a comprehension (a comprehension's first iterable is), not the
    comparisons of a chain after the first.

    Walked with an explicit stack, as :func:`ast.walk` is, so a filter nested however
    deep cannot exceed the interpreter's recursion limit here; the order is none in
    particular."""
    stack = [node]
    while stack:
        node = stack.pop()
        yield node
        children: Iterable[ast.AST]
        if isinstance(node, ast.BoolOp):
            children = node.values[:1]
        elif isinstance(node, ast.IfExp):
            children = (node.test,)
        elif isinstance(node, ast.Lambda):
            children = ()
        elif isinstance(
            node, ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp
        ):
            children = (node.generators[0].iter,)
        elif isinstance(node, ast.Compare):
            children = (node.left, node.comparators[0])
        else:
            children = ast.iter_child_nodes(node)
        stack.extend(children)


def _refused(node: ast.AST) -> bool:
    """Whether *node* is, by its text, an error every evaluation reaching it gives
    today: a call of ``c.in_namespace`` that is not one positional argument, or whose
    literal argument names no namespace (:func:`._id_facets.namespace_argument`); a
    facet of ``c.source`` / ``c.id`` that is none; ``c.id`` itself compared (by the
    first comparison of a chain), hashed (a set member, a dict key) or searched
    (``"x" in c.id``)."""
    if _is_in_namespace(node):
        assert isinstance(node, ast.Call)
        if node.keywords or len(node.args) != 1:
            return True
        if isinstance(argument := node.args[0], ast.Constant):
            try:
                _id_facets.namespace_argument(argument.value)
            except (TypeError, ValueError):
                return True
        return False
    if (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Attribute)
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == CHECKS_NAME
        and node.value.attr in CHECK_FACETS
    ):
        return node.attr not in CHECK_FACETS[node.value.attr]
    if isinstance(node, ast.Compare):
        return not isinstance(node.ops[0], ast.Is | ast.IsNot) and (
            _is_bare_id(node.left) or _is_bare_id(node.comparators[0])
        )
    if isinstance(node, ast.Set):
        return any(map(_is_bare_id, node.elts))
    if isinstance(node, ast.Dict):
        return any(key is not None and _is_bare_id(key) for key in node.keys)
    return False


@lru_cache(maxsize=256)
def namespace_reads(expression: str) -> tuple[str, ...]:
    """The namespace values an expression reads, as a warning names them, in the order
    ``c.id.ns``, ``c.id.local``, ``c.in_namespace()``, each once.

    Read from its text as parsed, never from evaluating it, so a name inside a string
    literal is no read; read past the leading spaces and tabs ``eval`` reads past, as the
    string is evaluated. Empty for an expression that reads none, that does not parse,
    and for one the text shows refused (:func:`_refused`, judged only where evaluation
    reaches it unconditionally, :func:`_reached`): such a filter has its refusal, and
    nothing beside it. Where the text cannot settle whether the filter is refused, the
    reads are given. Cached per string.
    """
    reads = _check_reads(expression)
    if _id_facets.ID_NAME not in reads and _id_facets.IN_NAMESPACE not in reads:
        return ()
    try:
        # past the leading spaces and tabs ``eval`` reads past, and no further
        tree = ast.parse(expression.lstrip(" \t"), mode="eval")
    except (SyntaxError, ValueError):
        return ()
    if any(map(_refused, _reached(tree.body))):
        return ()
    found: set[str] = set()
    for node in ast.walk(tree):
        if facet_read(node) == _id_facets.ID_NAME:
            assert isinstance(node, ast.Attribute)
            found.add(node.attr)
        elif _is_in_namespace(node):
            found.add(_id_facets.IN_NAMESPACE)
    return tuple(said for name, said in _NAMESPACE_READS if name in found)


def reads_a_facet(expression: str) -> bool:
    """Whether an expression reads a facet (``c.source.<facet>``, ``c.id.<facet>``) or
    calls ``c.in_namespace``. False for an expression that does not parse."""
    return bool(_check_reads(expression))


def unavailable(error: BaseException, expression: str) -> bool:
    """Whether an expression evaluated where there are no facets (no check context)
    failed for want of them: it reads a facet, and fails with ``c`` undefined, or with
    an attribute error on what ``c`` is there (a field named ``c``: a predicate's and a
    variant condition's contexts are built from the need's fields)."""
    reads = _check_reads(expression)
    if not reads:
        return False
    if isinstance(error, NameError):
        return getattr(error, "name", None) == CHECKS_NAME
    # the read itself failing: what ``c`` is there (a field named ``c``) has no
    # ``source``, ``id`` or ``in_namespace``
    return isinstance(error, AttributeError) and getattr(error, "name", None) in reads


def explained(error: BaseException, where: str, expression: str) -> str:
    """The text of an error of *expression*, evaluated where there are no facets
    (*where*: a field predicate, a needimport filter, a variant condition), with why,
    where it failed for want of them (:func:`unavailable`)."""
    if unavailable(error, expression):
        reads = _check_reads(expression)
        names = [said for name, said in _UNAVAILABLE if name in reads]
        verb = "is" if names == ["c.in_namespace()"] else "are"
        return f"{error}; {' and '.join(names)} {verb} not available in {where}"
    return str(error)
