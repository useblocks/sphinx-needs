"""The order the ``[[…]]``, ``<<…>>`` and ``<{…}>`` of the needs are computed in.

Every field that carries one after the ``needextend`` directives are applied is a
*node*, ``(need id, field)``. The link fields are computed first (stratum 1), then
the back links are built, then every other field (stratum 2). Inside a stratum a node
is computed after every node it reads, as the call text says what it reads: a
:func:`~sphinx_needs.functions.common.copy` reads one field of one need, a
:func:`~sphinx_needs.functions.common.calc_sum` the field of each of its candidates
(through one *column* node per field, rather than one edge per need), a
:func:`~sphinx_needs.functions.common.check_linked_values` the fields of every linked
need, a variant the fields of its own need that any of its conditions names.

A strongly connected group of nodes is a cycle: its members are not computed, and
take their field's empty value. Your own functions read what they like, so they are
computed after every built-in node of their stratum, in ``(need id, field)`` order;
so is a built-in call whose filter cannot be read (it names ``needs``, or reads
``current_need`` by a key that is not written out).

Nothing here touches Sphinx: the module only reads the needs and the call texts,
and returns the order to compute them in, which ``resolve_functions`` follows.
"""

from __future__ import annotations

import ast
import heapq
import inspect
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Final, Literal, TypeVar

from sphinx_needs.functions.common import (
    calc_sum,
    check_linked_values,
    copy,
    echo,
    links_from_content,
    test,
)
from sphinx_needs.functions.functions import (
    DynamicFunctionParsed,
    NeedAttribute,
    _condition_names,
)
from sphinx_needs.need_item import NeedItem
from sphinx_needs.needs_schema import FieldSchema, FieldsSchema, LinkSchema
from sphinx_needs.variant_data import VariantDataParsed
from sphinx_needs.variants import VariantFunctionParsed

Node = tuple[str, str]
"""A computed value: ``(need id, field)`` of a field that carries a ``[[…]]``,
``<<…>>`` or ``<{…}>`` once every ``needextend`` is applied."""


@dataclass(frozen=True, slots=True)
class Column:
    """The values of ``field`` on the candidates of a sum or a filter, as one node.

    ``candidates`` is the filter whose candidates were computed before the stratum,
    or ``None`` when every need is a candidate.
    """

    field: str
    candidates: str | None = None


_Vertex = Node | Column

#: the built-in functions, which the order knows the reads of, by their name
BUILTINS: Final[Mapping[str, Callable[..., Any]]] = {
    func.__name__: func
    for func in (test, echo, copy, check_linked_values, calc_sum, links_from_content)
}


def _parameters(func: Callable[..., Any]) -> tuple[str, ...]:
    """The parameters a call of a built-in gives, positionally or by name, in order."""
    return tuple(
        name
        for name, parameter in list(inspect.signature(func).parameters.items())[3:]
        if parameter.kind is parameter.POSITIONAL_OR_KEYWORD
    )


#: the arguments that name what a call reads, by built-in; the others are values
_SELECTORS: Final[Mapping[str, frozenset[str]]] = {
    "copy": frozenset({"option", "need_id", "filter"}),
    "check_linked_values": frozenset({"search_option", "filter_string"}),
    "calc_sum": frozenset({"option", "filter", "links_only"}),
    "links_from_content": frozenset({"need_id", "filter"}),
}
_PARAMETERS: Final[Mapping[str, tuple[str, ...]]] = {
    name: _parameters(func) for name, func in BUILTINS.items()
}
_VARARGS: Final = frozenset({"test", "echo"})


def typed_empty(field_schema: FieldSchema | LinkSchema) -> Any:
    """The value a field takes when its call is not computed: a cycle, a read out of scope.

    ``None`` for a nullable field, else the empty value of its type; ``[]`` for a link.
    """
    if field_schema.nullable:
        return None
    match field_schema.type:
        case "string":
            return ""
        case "boolean":
            return False
        case "integer":
            return 0
        case "number":
            return 0.0
        case _:
            return []


def placeholder(need: NeedItem, field: str, schema: FieldsSchema) -> Any:
    """The value of a field whose ``[[…]]``, ``<<…>>`` or ``<{…}>`` is not computed.

    A cycle member holds it, as does a field whose call cannot be ordered, and a field
    a ``needextend`` sets to a call, until the call is computed. A link or an array
    field keeps the items written in it (once every ``needextend`` is applied) that are
    not computed: ``LIT_1, [[copy("status")]]`` holds ``['LIT_1']``. Any other field,
    and a list with no such item, takes its typed empty value (:func:`typed_empty`).

    :param need: The need.
    :param field: The field, which carries a ``[[…]]``, ``<<…>>`` or ``<{…}>``.
    :param schema: The schema of the fields.
    """
    if (field_schema := schema.get_any_field(field)) is None:
        return need.get(field)
    if isinstance(field_schema, LinkSchema) or field_schema.type == "array":
        dynamic = need._dynamic_fields.get(field)
        written = [
            item
            for item in (dynamic.value if dynamic is not None else ())
            if not isinstance(
                item, DynamicFunctionParsed | VariantFunctionParsed | VariantDataParsed
            )
        ]
        if written:
            return written
    return typed_empty(field_schema)


@dataclass(frozen=True, slots=True)
class FilterNames:
    """What a filter string reads, from its text.

    :ivar names: The free names it reads, one field of the need it is evaluated on each.
    :ivar current: The keys it reads as ``current_need["key"]``.
    :ivar opaque: It names ``needs``, or reads ``current_need`` other than by a
        constant key: what it reads cannot be told from the text.
    """

    names: frozenset[str]
    current: frozenset[str]
    opaque: bool


#: names the filter context sets over a need's fields; a builtin's name is not one of
#: them, as a field of the same name shadows the builtin
_FILTER_GLOBALS: Final = frozenset({"search", "c", "var"})


@lru_cache(maxsize=512)
def filter_names(
    filter_string: str, not_fields: frozenset[str] = frozenset()
) -> FilterNames:
    """Return what ``filter_string`` reads, from its text.

    A name bound inside the filter (a comprehension's or a lambda's) is not a field;
    nor are the names the filter context supplies over the need's fields (``search``,
    ``c``, ``var``, and ``not_fields``, the keys of ``needs_filter_data``). A builtin's
    name is kept: a field of that name shadows it, and no other is computed.
    ``c.this_doc()`` reads ``docname``, which nothing computes. A filter that does not
    parse reads nothing here; evaluating it reports the error.

    :param filter_string: The filter.
    :param not_fields: The names supplied by ``needs_filter_data``.
    """
    try:
        tree = ast.parse(filter_string.strip(), mode="eval")
    except (SyntaxError, ValueError):
        return FilterNames(frozenset(), frozenset(), False)
    bound: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.comprehension):
            bound.update(
                target.id
                for target in ast.walk(node.target)
                if isinstance(target, ast.Name)
            )
        elif isinstance(node, ast.Lambda):
            bound.update(arg.arg for arg in node.args.args)
        elif isinstance(node, ast.NamedExpr):
            bound.add(node.target.id)
    current: set[str] = set()
    constant_current: set[int] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name)
            and node.value.id == "current_need"
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, str)
        ):
            current.add(node.slice.value)
            constant_current.add(id(node.value))
    names: set[str] = set()
    opaque = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Name) or not isinstance(node.ctx, ast.Load):
            continue
        if node.id in bound:
            continue
        if node.id == "needs":
            opaque = True
        elif node.id == "current_need":
            opaque = opaque or id(node) not in constant_current
        elif node.id not in _FILTER_GLOBALS and node.id not in not_fields:
            names.add(node.id)
        elif node.id == "c":
            names.add("docname")
    return FilterNames(frozenset(names), frozenset(current), opaque)


_T = TypeVar("_T")


def _appended(items: Sequence[_T], item: _T) -> list[_T]:
    """``items`` with ``item`` appended: the list itself, or a new one for ``()``.

    The fields of :class:`NodeReads` start as ``()``, so a node that reads nothing
    allocates nothing: the pass keeps one per node while it runs.
    """
    if isinstance(items, list):
        items.append(item)
        return items
    return [*items, item]


@dataclass(slots=True)
class NodeReads:
    """What one node reads, as the stratum it is computed in sees it.

    :ivar first: The node's first call or variant (``None`` for variant data only).
    :ivar deps: The nodes of the same stratum it is computed after.
    :ivar columns: The columns it reads, each with the filter that made every need a
        candidate, or ``None`` for a sum over every need.
    :ivar scope: Per call, the ``(name, need id)`` reads of a value that is computed
        only after the node's stratum (``needs.derive_scope``).
    :ivar blocked: The call whose ``need.<field>`` argument selects what it reads
        while the field is computed in the same stratum, and those fields.
    :ivar user_functions: The user functions the node calls: it is computed last.
    :ivar opaque: A built-in call of the node has a filter that cannot be read: it is
        computed last.
    :ivar reads_itself_by_variant: A variant condition of the node names its field.
    """

    first: DynamicFunctionParsed | VariantFunctionParsed | None
    deps: Sequence[Node] = ()
    columns: Sequence[tuple[Column, str | None]] = ()
    scope: Sequence[tuple[str, list[tuple[str, str]]]] = ()
    blocked: tuple[str, list[str]] | None = None
    user_functions: Sequence[str] = ()
    opaque: bool = False
    reads_itself_by_variant: bool = False

    @property
    def what(self) -> str:
        """The node's first call or variant, as messages name it."""
        return _what(self.first)

    @property
    def last(self) -> bool:
        """Whether the node is computed after every built-in node of its stratum."""
        return bool(self.user_functions) or self.opaque

    def expected(self) -> frozenset[tuple[str, str]]:
        """The ``(need id, name)`` reads already reported as out of scope."""
        if not self.scope:
            return _NOTHING
        return frozenset(
            (need_id, name) for _, reads in self.scope for name, need_id in reads
        )


_NOTHING: Final[frozenset[tuple[str, str]]] = frozenset()


def _what(item: DynamicFunctionParsed | VariantFunctionParsed | None) -> str:
    """A call or a variant, as messages name it."""
    if isinstance(item, DynamicFunctionParsed):
        return f"dynamic function '{item.name}'"
    return "variant condition" if item is not None else "variant data"


FAILED: Final = object()
"""A precomputed filter that cannot be evaluated: the call reads nothing."""


class Project:
    """The nodes of all needs, and what the order needs to know about the project.

    :param needs: The needs, after every ``needextend`` is applied.
    :param link_fields: The names of the link fields.
    :param variants: ``needs_variants``.
    :param not_fields: The names a variant condition or filter reads from
        ``needs_filter_data``, ``build_tags`` or ``var``, not from the need.
    :param builtins: The registered function of each built-in name; a name whose
        registered function is not the built-in is a user function.
    :param copy_match: The id of the lowest-id need ``copy``'s filter matches on behalf
        of a need, ``None`` for no match, or ``FAILED``; evaluated before the stratum.
    :param sum_candidates: The ids of the needs ``calc_sum``'s filter keeps, in need-id
        order; evaluated before the stratum.
    :param content_refs: The ids a need's content references (``links_from_content``).
    """

    def __init__(
        self,
        needs: Mapping[str, NeedItem],
        *,
        link_fields: Collection[str],
        variants: Mapping[str, str],
        not_fields: Collection[str],
        builtins: Mapping[str, Callable[..., Any]],
        copy_match: Callable[[str, NeedItem], str | object | None],
        sum_candidates: Callable[[str], Sequence[str]],
        content_refs: Callable[[str], Sequence[str]],
    ) -> None:
        self.needs = needs
        self.link_fields = frozenset(link_fields)
        self.variants = variants
        self.not_fields = frozenset(not_fields)
        self.builtins = {
            name: func for name, func in builtins.items() if BUILTINS.get(name) is func
        }
        self._copy_match = copy_match
        self._sum_candidates = sum_candidates
        self._sum_memo: dict[str, Sequence[str]] = {}
        self.content_refs = content_refs
        #: every node, by stratum (1 for a link field, 2 for any other)
        self.nodes: dict[Node, int] = {}
        #: the fields computed on at least one need, with their stratum
        self.computed_fields: dict[str, int] = {}
        for need_id, need in needs.items():
            for name in need._dynamic_fields:
                stratum = 1 if name in self.link_fields else 2
                self.nodes[(need_id, name)] = stratum
                self.computed_fields[name] = stratum

    def stratum_nodes(self, stratum: int) -> list[Node]:
        """The nodes of ``stratum``, in ``(need id, field)`` order."""
        return sorted(node for node, s in self.nodes.items() if s == stratum)

    def field_of(self, name: str) -> str:
        """The field a name reads: ``parent_need`` is computed from ``parent_needs``."""
        if name == "parent_need" and "parent_needs" in self.link_fields:
            return "parent_needs"
        return name

    def is_backlink(self, name: str) -> bool:
        """Whether ``name`` is a back link field (``<link>_back``)."""
        return name.endswith("_back") and name[:-5] in self.link_fields

    def final(self, name: str, stratum: int) -> bool:
        """Whether every need's ``name`` is final before ``stratum`` is computed."""
        if self.is_backlink(name):
            return stratum == 2
        computed = self.computed_fields.get(self.field_of(name))
        return computed is None or computed < stratum

    def final_on(self, need_id: str, name: str, stratum: int) -> bool:
        """Whether ``name`` of one need is final before ``stratum`` is computed."""
        if self.is_backlink(name):
            return stratum == 2
        computed = self.nodes.get((need_id, self.field_of(name)))
        return computed is None or computed < stratum

    def sum_candidates(self, filter_string: str) -> Sequence[str]:
        """``calc_sum``'s candidates for a filter on final values, memoised per filter."""
        if filter_string not in self._sum_memo:
            self._sum_memo[filter_string] = self._sum_candidates(filter_string)
        return self._sum_memo[filter_string]

    def node_reads(self, node: Node, stratum: int) -> NodeReads:
        """What ``node`` reads, computed in ``stratum``.

        A ``need.<field>`` that selects what a call reads (an id, a field name, a
        filter, ``links_only``) is read at this point, so it must be final already:
        otherwise the node is blocked.
        """
        need_id, name = node
        need = self.needs[need_id]
        items = need._dynamic_fields[name].value
        reads = NodeReads(
            next(
                (
                    item
                    for item in items
                    if isinstance(item, DynamicFunctionParsed | VariantFunctionParsed)
                ),
                None,
            )
        )
        for item in items:
            if isinstance(item, DynamicFunctionParsed):
                if item.name not in self.builtins:
                    reads.user_functions = _appended(reads.user_functions, item.name)
                    continue
                _CallReads(self, reads, need, stratum, item).read()
            elif isinstance(item, VariantFunctionParsed):
                scope: list[tuple[str, str]] = []
                for expression, _, _ in item.expressions:
                    expression = self.variants.get(expression, expression)
                    for read in _condition_names(expression):
                        if read in self.not_fields:
                            continue
                        if read == name:
                            reads.reads_itself_by_variant = True
                        _classify(self, reads, scope, stratum, need_id, read)
                if scope:
                    reads.scope = _appended(reads.scope, ("variant condition", scope))
        return reads


def _classify(
    project: Project,
    reads: NodeReads,
    scope: list[tuple[str, str]],
    stratum: int,
    need_id: str,
    name: str,
) -> None:
    """File the read of ``name`` on ``need_id`` by a node of ``stratum``.

    A node of the same stratum is a dependency; one of a later stratum, or a back
    link read in stratum 1, is out of scope; anything else is final already.
    """
    if project.is_backlink(name):
        if stratum == 1 and (name, need_id) not in scope:
            scope.append((name, need_id))
        return
    computed = project.nodes.get((need_id, project.field_of(name)))
    if computed is None or computed < stratum:
        return
    if computed == stratum:
        reads.deps = _appended(reads.deps, (need_id, project.field_of(name)))
    elif (name, need_id) not in scope:
        scope.append((name, need_id))


class _CallReads:
    """The reads of one built-in call, added to its node's :class:`NodeReads`."""

    def __init__(
        self,
        project: Project,
        reads: NodeReads,
        need: NeedItem,
        stratum: int,
        call: DynamicFunctionParsed,
    ) -> None:
        self.project = project
        self.reads = reads
        self.need = need
        self.stratum = stratum
        self.call = call
        self.scope: list[tuple[str, str]] = []

    @property
    def what(self) -> str:
        return _what(self.call)

    def _read(self, need_id: str, name: Any) -> None:
        if isinstance(name, str) and need_id in self.project.needs:
            _classify(self.project, self.reads, self.scope, self.stratum, need_id, name)

    def _column(self, name: Any, candidates: str | None, reason: str | None) -> None:
        if not isinstance(name, str):
            return
        if self.project.is_backlink(name):
            self._read(self.need.id, name)
            return
        computed = self.project.computed_fields.get(self.project.field_of(name))
        if computed is None or computed < self.stratum:
            return
        if computed > self.stratum:
            ids = (
                self.project.sum_candidates(candidates)
                if candidates is not None
                else sorted(self.project.needs)
            )
            for need_id in ids:
                self._read(need_id, name)
            return
        self.reads.columns = _appended(
            self.reads.columns,
            (Column(self.project.field_of(name), candidates), reason),
        )

    def _filter(self, filter_string: str) -> FilterNames | None:
        names = filter_names(filter_string, self.project.not_fields)
        if names.opaque:
            self.reads.opaque = True
            return None
        return names

    def read(self) -> None:
        name = self.call.name
        args: dict[str, Any] = {}
        if name in _VARARGS:
            values = [*self.call.args, *(value for _, value in self.call.kwargs)]
        else:
            parameters = _PARAMETERS[name]
            if len(self.call.args) > len(parameters):
                return  # the call fails: it reads nothing
            args = dict(zip(parameters, self.call.args, strict=False))
            for key, value in self.call.kwargs:
                if key in args or key not in parameters:
                    return  # the call fails: it reads nothing
                args[key] = value
            values = [v for k, v in args.items() if k not in _SELECTORS[name]]
        # a ``need.<field>`` in a value position is read like the field itself
        for value in values:
            if isinstance(value, NeedAttribute):
                self._read(self.need.id, value.name)
        # one that selects what the call reads must be final before the call
        blocking: list[str] = []
        for key, value in list(args.items()):
            if not isinstance(value, NeedAttribute):
                continue
            attr = value.name
            if not self.project.final_on(self.need.id, attr, self.stratum):
                blocking.append(f"need.{attr}")
                self._read(self.need.id, attr)
                continue
            if attr not in self.need:
                return  # the call fails: need has no attribute
            args[key] = self.need[attr]
        if blocking:
            if self.reads.blocked is None:
                self.reads.blocked = (self.what, blocking)
            return
        if any(
            args.get(key) is not None and not isinstance(args[key], str)
            for key in _SELECTORS.get(name, frozenset()) - {"links_only"}
        ):
            return  # an id, a field or a filter that is no string: the call fails
        getattr(self, f"_{name}", lambda _: None)(args)
        if self.scope:
            self.reads.scope = _appended(self.reads.scope, (self.what, self.scope))

    def _copy(self, args: dict[str, Any]) -> None:
        option = args.get("option")
        need_id = args.get("need_id")
        filter_string = args.get("filter")
        if need_id and need_id not in self.project.needs:
            return  # the call fails: no such need
        source = need_id or self.need.id
        if not filter_string:
            self._read(source, option)
            return
        names = self._filter(filter_string)
        if names is None:
            return
        for key in sorted(names.current):  # current_need is the caller
            self._read(self.need.id, key)
        if all(self.project.final(n, self.stratum) for n in names.names) and all(
            self.project.final_on(self.need.id, key, self.stratum)
            for key in names.current
        ):
            match = self.project._copy_match(filter_string, self.need)
            if match is FAILED:
                return
            self._read(match if isinstance(match, str) else source, option)
            return
        self._column(option, None, filter_string)
        for read in sorted(names.names):
            self._column(read, None, filter_string)
        self._read(source, option)  # no match copies from the need itself

    def _calc_sum(self, args: dict[str, Any]) -> None:
        option = args.get("option")
        filter_string = args.get("filter")
        names = FilterNames(frozenset(), frozenset(), False)
        if filter_string:
            filtered = self._filter(filter_string)
            if filtered is None:
                return
            names = filtered
        reads = sorted(names.names | names.current)  # current_need is the candidate
        if args.get("links_only"):
            self._read(self.need.id, "links")
            for target in self.need.get("links") or []:
                self._read(target, option)
                for read in reads:
                    self._read(target, read)
            return
        if not filter_string:
            self._column(option, None, None)
            return
        if all(self.project.final(read, self.stratum) for read in reads):
            self._column(option, filter_string, None)
            return
        self._column(option, None, filter_string)
        for read in reads:
            self._column(read, None, filter_string)

    def _check_linked_values(self, args: dict[str, Any]) -> None:
        reads: list[str] = []
        if filter_string := args.get("filter_string"):
            names = self._filter(filter_string)
            if names is None:
                return
            reads = sorted(names.names | names.current)
        self._read(self.need.id, "links")
        for target in self.need.get("links") or []:
            self._read(target, args.get("search_option"))
            for read in reads:
                self._read(target, read)

    def _links_from_content(self, args: dict[str, Any]) -> None:
        filter_string = args.get("filter")
        if not filter_string:
            return
        names = self._filter(filter_string)
        if names is None:
            return
        source = args.get("need_id") or self.need.id
        for target in self.project.content_refs(source):
            for read in sorted(names.names | names.current):
                self._read(target, read)


@dataclass(frozen=True, slots=True)
class Step:
    """One step of a stratum: compute a node, or settle a cycle.

    :ivar nodes: The node, or the members of the cycle in ``(need id, field)`` order.
    :ivar cycle: Whether the step is a cycle.
    :ivar through: For a cycle through a column: the filter that made every need a
        candidate, or ``None`` for a sum over every need; ``False`` otherwise.
    """

    nodes: tuple[Node, ...]
    cycle: bool = False
    through: str | Literal[False] | None = False


@dataclass(slots=True)
class Stratum:
    """The nodes of one stratum, what each reads, and the steps to compute them in."""

    stratum: int
    reads: dict[Node, NodeReads]
    steps: list[Step]


def build_stratum(project: Project, stratum: int) -> Stratum:
    """Read every node of ``stratum`` and order it.

    Called once the strata before it are computed, so the values a node's selectors
    and links name are final.
    """
    reads = {
        node: project.node_reads(node, stratum)
        for node in project.stratum_nodes(stratum)
    }
    built_in = [node for node, r in reads.items() if not r.last]
    last = [node for node, r in reads.items() if r.last]
    by_field: dict[str, list[Node]] = {}
    for node in built_in:
        by_field.setdefault(node[1], []).append(node)

    vertices: list[_Vertex] = list(built_in)
    index: dict[_Vertex, int] = {v: i for i, v in enumerate(vertices)}
    # a node that reads no other has no list of its own
    edges: list[list[int] | None] = [None] * len(vertices)

    def add_edge(source: int, target: int) -> None:
        if (targets := edges[source]) is None:
            edges[source] = [target]
        else:
            targets.append(target)

    #: per column vertex, why each reader reads it
    reasons: dict[tuple[int, int], str | None] = {}

    def column_vertex(column: Column) -> int | None:
        if column in index:
            return index[column]
        if column.candidates is None:
            members = by_field.get(column.field, [])
        else:
            members = [
                (need_id, column.field)
                for need_id in project.sum_candidates(column.candidates)
                if (need_id, column.field) in reads
                and not reads[(need_id, column.field)].last
            ]
        if not members:
            return None
        index[column] = len(vertices)
        vertices.append(column)
        edges.append([index[member] for member in members])
        return index[column]

    for node in built_in:
        source = index[node]
        node_reads = reads[node]
        for dep in node_reads.deps:
            if dep in index:  # a node computed last is not waited for
                add_edge(source, index[dep])
        for column, reason in node_reads.columns:
            target = column_vertex(column)
            if target is not None:
                add_edge(source, target)
                reasons.setdefault((source, target), reason)

    components = strongly_connected(edges)
    steps: list[Step] = []
    for component in schedule(edges, components, _keys(vertices, components)):
        members = sorted(
            v for v in (vertices[i] for i in component) if not isinstance(v, Column)
        )
        if not members:
            continue
        cyclic = len(component) > 1 or component[0] in (edges[component[0]] or ())
        if not cyclic:
            steps.append(Step((members[0],)))
            continue
        inside = set(component)
        through_columns = {
            reasons[(source, target)]
            for source in component
            for target in edges[source] or ()
            if target in inside and isinstance(vertices[target], Column)
        }
        filters = sorted(r for r in through_columns if r is not None)
        through: str | Literal[False] | None = (
            filters[0] if filters else None if through_columns else False
        )
        steps.append(Step(tuple(members), cycle=True, through=through))
    steps.extend(Step((node,)) for node in sorted(last))
    return Stratum(stratum, reads, steps)


def _keys(
    vertices: Sequence[_Vertex], components: Sequence[Sequence[int]]
) -> list[Node]:
    """Each component's key: its smallest node; a column alone sorts first."""
    keys: list[Node] = []
    for component in components:
        if len(component) == 1 and not isinstance(
            node := vertices[component[0]], Column
        ):
            keys.append(node)
            continue
        nodes = [
            v for v in (vertices[i] for i in component) if not isinstance(v, Column)
        ]
        keys.append(min(nodes) if nodes else ("", ""))
    return keys


def strongly_connected(edges: Sequence[Sequence[int] | None]) -> list[list[int]]:
    """The strongly connected components of a graph, by Tarjan's algorithm, iteratively.

    A recursion would end on a long chain (a valid project: each need copying the
    next), at Python's recursion limit. A component comes after every component it
    reaches, i.e. after everything its nodes read.

    :param edges: For each vertex, the vertices it reads (``None`` for none).
    """
    count = len(edges)
    order = [-1] * count
    low = [0] * count
    on_stack = [False] * count
    stack: list[int] = []
    components: list[list[int]] = []
    counter = 0
    for root in range(count):
        if order[root] != -1:
            continue
        work: list[tuple[int, int]] = [(root, 0)]
        while work:
            vertex, position = work[-1]
            if position == 0:
                order[vertex] = low[vertex] = counter
                counter += 1
                stack.append(vertex)
                on_stack[vertex] = True
            targets = edges[vertex] or ()
            while position < len(targets):
                target = targets[position]
                position += 1
                if order[target] == -1:
                    work[-1] = (vertex, position)
                    work.append((target, 0))
                    break
                if on_stack[target]:
                    low[vertex] = min(low[vertex], order[target])
            else:
                work.pop()
                if work:
                    parent = work[-1][0]
                    low[parent] = min(low[parent], low[vertex])
                if low[vertex] == order[vertex]:
                    component = []
                    while True:
                        member = stack.pop()
                        on_stack[member] = False
                        component.append(member)
                        if member == vertex:
                            break
                    components.append(component)
    return components


def schedule(
    edges: Sequence[Sequence[int] | None],
    components: Sequence[Sequence[int]],
    keys: Sequence[Node],
) -> Iterable[Sequence[int]]:
    """Yield the components so that each comes after every one it reads.

    Kahn's algorithm on the components, taking the ready one with the smallest key
    first, so the order of independent components (and of the warnings they give)
    is fixed by need id, then field.
    """
    component_of = [0] * len(edges)
    for number, component in enumerate(components):
        for vertex in component:
            component_of[vertex] = number
    readers: list[set[int] | None] = [None] * len(components)
    for source, targets in enumerate(edges):
        for target in targets or ():
            if component_of[source] != component_of[target]:
                if (found := readers[component_of[target]]) is None:
                    readers[component_of[target]] = {component_of[source]}
                else:
                    found.add(component_of[source])
    waiting = [0] * len(components)
    for found in readers:
        for reader in found or ():
            waiting[reader] += 1
    # each component by its rank in key order, so the heap holds plain integers
    by_key = sorted(range(len(components)), key=keys.__getitem__)
    rank = [0] * len(components)
    for position, number in enumerate(by_key):
        rank[number] = position
    ready = [rank[n] for n in range(len(components)) if waiting[n] == 0]
    heapq.heapify(ready)
    while ready:
        number = by_key[heapq.heappop(ready)]
        yield components[number]
        for reader in readers[number] or ():
            waiting[reader] -= 1
            if waiting[reader] == 0:
                heapq.heappush(ready, rank[reader])
