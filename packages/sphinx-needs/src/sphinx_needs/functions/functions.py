"""
Sphinx-needs functions module
=============================

Cares about the correct registration and execution of sphinx-needs functions to support dynamic values
in need configurations.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Callable, Container, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Protocol, TypeAlias, TypeVar

from docutils import nodes
from sphinx.application import Sphinx
from sphinx.environment import BuildEnvironment
from sphinx.util.logging import suppress_logging

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import NeedsMutable, SphinxNeedsData
from sphinx_needs.debug import measure_time_func
from sphinx_needs.exceptions import FunctionParsingException
from sphinx_needs.filter_common import filter_needs_and_parts, filter_single_need
from sphinx_needs.logging import get_logger, log_warning
from sphinx_needs.need_item import NeedItem, NeedLink, NeedPartItem
from sphinx_needs.needs_schema import FieldsSchema
from sphinx_needs.nodes import Need
from sphinx_needs.roles.need_func import NeedFunc
from sphinx_needs.utils import counted_ids
from sphinx_needs.variant_data import (
    VariantDataError,
    VariantDataParsed,
    lookup_variant_data,
)
from sphinx_needs.variants import VariantFunctionParsed
from sphinx_needs.views import NeedsView

if TYPE_CHECKING:
    from sphinx_needs.functions.order import (
        Column,
        Node,
        OutOfScope,
        Project,
        Stratum,
    )

logger = get_logger(__name__)
unicode = str


class DynamicFunction(Protocol):
    """A protocol for a sphinx-needs dynamic function."""

    __name__: str

    def __call__(
        self,
        app: Sphinx,
        need: NeedItem | NeedPartItem | None,
        needs: NeedsView | NeedsMutable,
        *args: Any,
        **kwargs: Any,
    ) -> (
        str | int | float | list[str] | list[int] | list[float] | list[NeedLink] | None
    ): ...


def _execute_dynamic_func(
    app: Sphinx,
    need: NeedItem | NeedPartItem | None,
    needs: NeedsView | NeedsMutable,
    df: DynamicFunctionParsed,
    *,
    reads: UnresolvedReads | None = None,
) -> str | int | float | list[str] | list[int] | list[float] | list[NeedLink] | None:
    """Execute a parsed dynamic function call.

    :param app: Sphinx application
    :param need: The need the call belongs to, if any
    :param needs: All needs
    :param df: The parsed call
    :param reads: The record of the call ``resolve_functions`` is running, handed to a
        function marked :func:`records_reads` as its ``reads`` keyword; any other
        function is called without it.
    :return: return value of executed function
    :raises RuntimeError: If the call cannot be applied to the need, names no
        registered function, or fails.
    """
    needs_config = NeedsSphinxConfig(app.config)

    if need is not None:
        # it imports this module
        from sphinx_needs.functions.order import BUILTINS, unset_selector

        if (
            df.name in needs_config.functions
            and needs_config.functions[df.name]["function"] is BUILTINS.get(df.name)
            and (attr := unset_selector(df, need)) is not None
        ):
            raise RuntimeError(
                f"Error while applying need to function {df.name!r}: need.{attr} "
                "selects what the call reads, and is not set"
            )
        try:
            df = df.apply_need(need)
        except Exception as err:
            raise RuntimeError(
                f"Error while applying need to function {df.name!r}: {err}"
            ) from err

    if df.name not in needs_config.functions:
        raise RuntimeError(f"Unknown function {df.name!r}")

    registered = needs_config.functions[df.name]["function"]
    func = measure_time_func(registered, category="dyn_func", source="user")

    try:
        if getattr(registered, "records_reads", None) is registered:
            func_return = func(
                app,
                need,
                needs,
                *df.args,
                reads=reads,
                **df.kwargs_dict(),
            )
        else:
            func_return = func(
                app,
                need,
                needs,
                *df.args,
                **df.kwargs_dict(),
            )
    except Exception as e:
        raise RuntimeError(f"Error while executing function {df.name!r}: {e}") from e

    return func_return


def execute_func(
    app: Sphinx,
    need: NeedItem | NeedPartItem | None,
    needs: NeedsView | NeedsMutable,
    df: str | DynamicFunctionParsed,
    location: str | tuple[str | None, int | None] | nodes.Node | None,
) -> str | int | float | list[str] | list[int] | list[float] | list[NeedLink] | None:
    """Executes a given function string.

    :param env: Sphinx environment
    :param need: Actual need, which contains the found function string
    :param func_string: string of the found function. Without ``[[ ]]``
    :param location: source location of the function call
    :return: return value of executed function
    """
    if isinstance(df, str):
        try:
            df = DynamicFunctionParsed.from_string(df, allow_need=need is not None)
        except FunctionParsingException as err:
            log_warning(
                logger,
                str(err),
                "dynamic_function",
                location=location,
            )
            return "??"

    if need is not None:
        try:
            df = df.apply_need(need)
        except Exception as err:
            log_warning(
                logger,
                f"Error while applying need to function {df.name!r}: {err}",
                "dynamic_function",
                location=location,
            )
            return "??"

    needs_config = NeedsSphinxConfig(app.config)

    if df.name not in needs_config.functions:
        log_warning(
            logger,
            f"Unknown function {df.name!r}",
            "dynamic_function",
            location=location,
        )
        return "??"

    func = measure_time_func(
        needs_config.functions[df.name]["function"],
        category="dyn_func",
        source="user",
    )

    try:
        func_return = func(
            app,
            need,
            needs,
            *df.args,
            **df.kwargs_dict(),
        )
    except Exception as e:
        log_warning(
            logger,
            f"Error while executing function {df.name!r}: {e}",
            "dynamic_function",
            location=location,
        )
        return "??"

    if func_return is not None and not isinstance(
        func_return, str | int | float | list
    ):
        log_warning(
            logger,
            f"Return value of function {df.name!r} is of type {type(func_return)}. Allowed are str, int, float, list",
            "dynamic_function",
            location=location,
        )
        return "??"
    if isinstance(func_return, list):
        for i, element in enumerate(func_return):
            if not isinstance(element, str | int | float | NeedLink):
                log_warning(
                    logger,
                    f"Return value item {i} of function {df.name!r} is of type {type(element)}. Allowed are str, int, float, NeedLink",
                    "dynamic_function",
                    location=location,
                )
                return "??"
    return func_return


FUNC_RE = re.compile(r"\[\[(.*?)\]\]")  # RegEx to detect function strings


def find_and_replace_node_content(
    node: nodes.Node, env: BuildEnvironment, need: NeedItem
) -> nodes.Node:
    """
    Search inside a given node and its children for ``NeedFunc`` nodes,
    created by the ``ndf`` role, and replace each with the text its function returns.

    A nested need is not descended into, because it runs this pass itself, for its own
    need data -- that skip is observable. Literal blocks and inline literals are skipped
    to state the intent: RST cannot put a role inside either, so no ``NeedFunc`` can be
    there to find.

    :param node: Node to analyse
    :param env: Sphinx environment
    :param need: Need data
    """
    if isinstance(node, NeedFunc):
        return node.get_text(env, need)

    if not node.children:
        return node

    new_children = []
    for child in node.children:
        if isinstance(child, nodes.literal_block | nodes.literal | Need):
            # Do not parse literal blocks or nested needs
            new_children.append(child)
            continue
        new_children.append(find_and_replace_node_content(child, env, need))

    node.children = new_children
    for subchild in node.children:
        node.setup_child(subchild)
    return node


# -- the order of the pass, and the reads it cannot order ----------------------------
#
# ``resolve_functions`` computes the link fields first, then builds the back links,
# then every other field, each after every value it reads, as the call texts say
# (:mod:`sphinx_needs.functions.order`). The record of the reads a call actually makes
# checks that order: the pass opens an ``UnresolvedReads`` for each call and each
# ``<<…>>`` variant, a built-in marked ``records_reads`` receives it as its ``reads``
# keyword and notes what it reads, ``_get_variant`` notes the names the variant's
# evaluated conditions read, and a read of a value the pass has not computed yet is
# reported once the call is over, as ``needs.derive_scope``. With the order right,
# that is only a read of a value your own function computes, after the built-in
# functions. Nothing else is handed a record: an ``ndf`` role or a ``:style_row:``
# runs after the pass, and a user's own function, which the pass calls without one,
# has none to give a built-in it calls; such a built-in gets ``reads=None`` and notes
# nothing.


class UnresolvedReads:
    """The reads of values not computed yet, made by ONE call or ``<<…>>`` variant.

    ``resolve_functions`` creates one for each call and each ``<<…>>`` variant (shared
    by all the conditions it evaluates), hands it to the dynamic function as its
    ``reads`` keyword when the function is marked :func:`records_reads`, and reports
    what it holds as ``needs.derive_scope`` once the call is over. No other caller
    creates one: after the pass every value read is final, and a user's function is
    opaque (its reads, through a built-in or otherwise, are not reported).

    Kept by the name read, in the order first read, each need named once per name.

    :param pending: The ``(need id, name)`` values of the pass not computed yet.
    """

    __slots__ = ("_pending", "_reads")

    def __init__(self, pending: Container[tuple[str, str]]) -> None:
        self._pending = pending
        self._reads: dict[str, dict[str, None]] = {}

    def note(self, name: str, need_id: str) -> None:
        """Record that ``name`` was read on the need ``need_id``, unconditionally.

        :meth:`note_read` is the form that checks the value is not computed yet.
        """
        self._reads.setdefault(name, {})[need_id] = None

    def note_read(self, need: NeedItem | NeedPartItem, name: str) -> None:
        """Note that the field or link ``name`` of ``need`` was read.

        It is recorded only when the value is computed in the pass and not computed
        yet: the order of the pass did not put the call after it.

        :param need: The need read: the call's own need or another one.
        :param name: The field or link read.
        """
        # the pass hands its functions whole needs, so only a need is noted; a need
        # part is admitted by the types (a ``filter``'s result is typed so), not noted
        # a built-in reads every candidate of a sum through here: kept to one lookup
        if isinstance(need, NeedItem) and (need.id, name) in self._pending:
            self.note(name, need.id)

    def reads(self) -> list[tuple[str, list[str]]]:
        """Return each name read, with the ids of the needs it was read on."""
        return [(name, list(ids)) for name, ids in self._reads.items()]


_DynamicFunctionT = TypeVar("_DynamicFunctionT", bound=Callable[..., Any])


def records_reads(func: _DynamicFunctionT) -> _DynamicFunctionT:
    """Mark a dynamic function as one that takes the record of the reads of its call.

    ``resolve_functions`` calls a marked function with the keyword argument ``reads``,
    the :class:`UnresolvedReads` of the call being resolved, into which the function
    notes each field it reads (:meth:`UnresolvedReads.note_read`). Every other caller
    (the ``ndf`` role, a ``:style_row:``, a direct call) passes no ``reads``, so the
    parameter must be keyword-only and default to ``None``. A function that is not
    marked is called exactly as before, never with ``reads``.

    The mark names the function it is set on, and is checked on the function as
    registered: a wrapper that copies the function's ``__dict__`` (``functools.wraps``,
    so also a user's function made with it) carries a mark naming another function,
    and is not marked.

    :param func: The dynamic function to mark.
    :return: The same function, marked.
    """
    # through ``vars``: the type checker refuses an attribute assignment on a callable
    vars(func)["records_reads"] = func
    return func


def _joined(parts: Sequence[str]) -> str:
    """``a``, ``a and b``, ``a, b and c``."""
    return parts[0] if len(parts) == 1 else f"{', '.join(parts[:-1])} and {parts[-1]}"


def _reads_phrase(reads: Sequence[tuple[str, Sequence[str]]]) -> str:
    """Each name once, with the one need it was read on, or a count and the first three."""
    return _joined(
        [
            f"'{name}' on need '{ids[0]}'"
            if len(ids) == 1
            else f"'{name}' on {counted_ids(ids, ' needs')}"
            for name, ids in reads
        ]
    )


def _one(reads: Sequence[tuple[str, Sequence[str]]]) -> bool:
    """Whether the reads are one name read on one need."""
    return len(reads) == 1 and len(reads[0][1]) == 1


def _derive_scope_message(
    what: str, option: str, reads: Sequence[tuple[str, Sequence[str]]], cause: str
) -> str:
    """Return the ``needs.derive_scope`` message for the reads of one call.

    ubCode's words up to the reads, then that they were read before they were
    computed, and why. Each name is said once, with the one need it was read on, or
    with how many and the first three, in need-id order; several names are joined
    ``a, b and c``.

    :param what: The reader: ``dynamic function 'copy'``, or ``variant condition``.
    :param option: The field the reader computes.
    :param reads: Each name read, with the ids of the needs it was read on, in order.
    :param cause: Why the values were not computed yet.
    :raises ValueError: If there is no read.
    """
    if not reads:
        raise ValueError("no read to report")
    when = "it was" if _one(reads) else "they were"
    return (
        f"{what} for option '{option}' read {_reads_phrase(reads)} "
        f"before {when} computed: {cause}"
    )


def _kept(value: Any) -> str:
    """What a field that is not computed holds, from its placeholder value."""
    return (
        "the field keeps only its written items" if value else "the field is left empty"
    )


def _through_clause(through: tuple[Column, str | None] | None) -> str:
    """What a cycle member reads its cycle through, as its message says it.

    :param through: The column on the cycle the member reads, with the filter that
        made every need a candidate; ``None`` for no column.
    """
    if through is None:
        return ""
    column, reason = through
    if reason is not None:
        return (
            f", through the filter {reason!r}, which names a computed field, "
            "so every need is a candidate"
        )
    if column.candidates is not None:
        return f", through the filter {column.candidates!r}, which keeps a need on the cycle"
    return ", through a sum over every need"


def _derive_cycle_message(
    what: str,
    option: str,
    members: Sequence[tuple[str, str]],
    clause: str,
    value: Any,
) -> str:
    """Return the ``needs.derive_cycle`` message for one member of a cycle.

    :param what: The member's first call or variant.
    :param option: The member's field.
    :param members: Every member, ``(need id, field)``, in that order.
    :param clause: What else to say: the column or the variant the cycle runs through.
    :param value: The value the member holds instead (its placeholder).
    """
    fields: dict[str, list[str]] = {}
    for need_id, name in members:
        fields.setdefault(name, []).append(need_id)
    return (
        f"{what} for option '{option}' is on a cycle: "
        f"{_reads_phrase(list(fields.items()))}{clause}; {_kept(value)}"
    )


def _out_of_scope_message(option: str, out_of_scope: OutOfScope, value: Any) -> str:
    """Return the ``needs.derive_scope`` message for a call or variant not computed.

    :param option: The field it computes.
    :param out_of_scope: The call or variant, and why it cannot be computed in its
        stratum.
    :param value: The value the field holds instead (its placeholder).
    """
    what = out_of_scope.what
    not_run = (
        "the condition is not evaluated"
        if what == "variant condition"
        else "the call is not run"
    )
    if selectors := out_of_scope.selectors:
        return (
            f"{what} for option '{option}' names its target by "
            f"{_joined([repr(s) for s in selectors])}, which "
            f"{'is' if len(selectors) == 1 else 'are'} computed in the same step: "
            f"{not_run} and {_kept(value)}"
        )
    names: dict[str, list[str]] = {}
    for name, read_id in out_of_scope.reads:
        names.setdefault(name, []).append(read_id)
    reads = list(names.items())
    return (
        f"{what} for option '{option}' reads {_reads_phrase(reads)}, which "
        f"{'is' if _one(reads) else 'are'} final only after the link fields are "
        f"computed: {not_run} and {_kept(value)}"
    )


class _Pass:
    """One ``resolve_functions`` pass: the values not computed yet, and why.

    :param project: The nodes of the pass.
    """

    def __init__(self, project: Project) -> None:
        self.project = project
        self.stratum: Stratum | None = None
        #: the ``(need id, name)`` values not computed yet, a name being the field's,
        #: or ``parent_need`` for a computed ``parent_needs``
        self.pending: set[tuple[str, str]] = set(project.nodes)
        self.pending.update(
            (need_id, "parent_need")
            for need_id, name in project.nodes
            if project.field_of("parent_need") == name
        )

    def finish(self, node: Node) -> None:
        """``node`` holds its final value."""
        self.pending.discard(node)
        if self.project.field_of("parent_need") == node[1]:
            self.pending.discard((node[0], "parent_need"))

    def causes(
        self, reads: Sequence[tuple[str, Sequence[str]]]
    ) -> list[tuple[str, list[tuple[str, list[str]]]]]:
        """The reads of a call, grouped by why they were read before being computed.

        Such a value is computed after the built-in functions: by your own function,
        or by a call whose filter cannot be read. Any other is a read the order did
        not account for.
        """
        groups: dict[str, list[tuple[str, list[str]]]] = {}
        functions: dict[str, None] = {}
        for name, ids in reads:
            for need_id in ids:
                node_reads = (
                    self.stratum.reads.get((need_id, self.project.field_of(name)))
                    if self.stratum is not None
                    else None
                )
                if node_reads is not None and node_reads.user_functions:
                    kind = "user"
                    functions.update(dict.fromkeys(node_reads.user_functions))
                elif node_reads is not None and node_reads.opaque:
                    kind = "opaque"
                else:
                    kind = "other"
                group = groups.setdefault(kind, [])
                if not group or group[-1][0] != name:
                    group.append((name, []))
                group[-1][1].append(need_id)
        result = []
        for kind, group in groups.items():
            subject = "it is" if _one(group) else "they are"
            if kind == "user":
                names = _joined([f"'{f}'" for f in functions])
                plural = len(functions) > 1
                cause = (
                    f"{subject} computed by your own function{'s' if plural else ''} "
                    f"{names}, which run{'' if plural else 's'} after the built-in functions"
                )
            elif kind == "opaque":
                cause = (
                    f"{subject} computed by a call whose filter cannot be read, "
                    "which runs after the other built-in functions"
                )
            else:
                cause = "the order of the pass did not account for this read"
            result.append((cause, group))
        return result


@dataclass(frozen=True, slots=True)
class _ReadsContext:
    """What the record of one node's calls needs from the pass.

    :ivar pass_: The pass.
    """

    pass_: _Pass

    def record(self) -> UnresolvedReads:
        """A new record, for one call or ``<<…>>`` variant."""
        return UnresolvedReads(self.pass_.pending)

    def report(
        self,
        what: str,
        option: str,
        need: NeedItem,
        noted: Sequence[tuple[str, Sequence[str]]],
    ) -> None:
        """Report the reads of a value not computed yet, by cause."""
        for cause, group in self.pass_.causes(noted):
            log_warning(
                logger,
                _derive_scope_message(what, option, group, cause),
                "derive_scope",
                location=_location(need),
            )


def _location(need: NeedItem) -> tuple[str, int | None] | None:
    return (need["docname"], need["lineno"]) if need["docname"] else None


@contextmanager
def _reads_reported(
    what: str, option: str, need: NeedItem, reads_ctx: _ReadsContext
) -> Iterator[UnresolvedReads]:
    """Open the record of one call or ``<<…>>`` variant, and report its reads after it.

    They are reported whatever the outcome, so a call that fails because of a value it
    read still says what it read. The warning is located at the reading need.

    :param what: The reader, as the message names it.
    :param option: The field the reader computes.
    :param need: The need the reader belongs to.
    :param reads_ctx: The pass the call is made in.
    """
    reads = reads_ctx.record()
    try:
        yield reads
    finally:
        if noted := reads.reads():
            reads_ctx.report(what, option, need, noted)


def resolve_functions(
    app: Sphinx,
    needs: NeedsMutable,
    needs_config: NeedsSphinxConfig,
) -> None:
    """Resolve all dynamic/variant functions in all needs, in dependency order.

    The link fields first (stratum 1), then the back links are built, then every other
    field (stratum 2), each after every value it reads; your own functions last in each
    stratum. A cycle's members are not computed, hold their placeholder (a list its
    written items, any other field its empty value) and are reported as
    ``needs.derive_cycle``; a call that reads what its stratum cannot wait for is not
    run either, holds its placeholder and is reported as ``needs.derive_scope``.
    Warnings come in the order the values are computed.
    """
    # imported here, as these modules import this one
    from sphinx_needs.directives.need import build_backlinks
    from sphinx_needs.functions.common import _find_need_refs
    from sphinx_needs.functions.order import FAILED, Project

    needs_schema = SphinxNeedsData(app.env).get_schema()

    def copy_match(filter_string: str, current: NeedItem) -> str | object | None:
        # the lowest-id match of ``copy``'s filter, as the call computes it, quietly:
        # the call reports a filter's problems itself
        with suppress_logging():
            try:
                found = filter_needs_and_parts(
                    needs.values(), needs_config, filter_string, current
                )
            except Exception:
                return FAILED
        return min(n["id"] for n in found) if found else None

    def sum_candidates(filter_string: str) -> list[str]:
        # ``calc_sum``'s candidates, in need-id order; a need its filter fails on is
        # summed, as the call sums it
        candidates = []
        with suppress_logging():
            for need_id in sorted(needs):
                try:
                    keep = filter_single_need(
                        needs[need_id], needs_config, filter_string
                    )
                except Exception:
                    keep = True
                if keep:
                    candidates.append(need_id)
        return candidates

    def content_refs(need_id: str) -> list[str]:
        node = SphinxNeedsData(app.env).get_need_node(need_id)
        return (
            []
            if node is None
            else [ref["need_link"].id for ref in _find_need_refs(node)]
        )

    project = Project(
        needs,
        link_fields=list(needs_schema.iter_link_field_names()),
        variants=needs_config.variants,
        not_fields={*needs_config.filter_data, "build_tags", "var"},
        builtins={name: f["function"] for name, f in needs_config.functions.items()},
        copy_match=copy_match,
        sum_candidates=sum_candidates,
        content_refs=content_refs,
    )
    pass_ = _Pass(project)
    # a link field's call reads no back link of an earlier build
    for need in needs.values():
        need.reset_backlinks()
    _resolve_stratum(app, needs, pass_, 1, needs_schema, needs_config)
    build_backlinks(needs, needs_schema)
    _resolve_stratum(app, needs, pass_, 2, needs_schema, needs_config)


def _resolve_stratum(
    app: Sphinx,
    needs: NeedsMutable,
    pass_: _Pass,
    number: int,
    schema: FieldsSchema,
    config: NeedsSphinxConfig,
) -> None:
    """Compute every value of one stratum, in order, and report what cannot be."""
    # it imports this module
    from sphinx_needs.functions.order import build_stratum, placeholder

    stratum = pass_.stratum = build_stratum(pass_.project, number)
    for step in stratum.steps:
        if step.cycle:
            for need_id, field in step.nodes:
                needs[need_id][field] = placeholder(needs[need_id], field, schema)
                pass_.finish((need_id, field))
            for (need_id, field), through in zip(step.nodes, step.through, strict=True):
                node_reads = stratum.reads[(need_id, field)]
                own = (
                    "; its condition reads the field it sets"
                    if node_reads.reads_itself_by_variant
                    else ""
                )
                log_warning(
                    logger,
                    _derive_cycle_message(
                        node_reads.what,
                        field,
                        step.nodes,
                        _through_clause(through) + own,
                        needs[need_id][field],
                    ),
                    "derive_cycle",
                    location=_location(needs[need_id]),
                )
            continue
        ((need_id, field),) = step.nodes
        need = needs[need_id]
        node_reads = stratum.reads[(need_id, field)]
        if node_reads.sink:
            need[field] = value = placeholder(need, field, schema)
            for out_of_scope in node_reads.scope:
                log_warning(
                    logger,
                    _out_of_scope_message(field, out_of_scope, value),
                    "derive_scope",
                    location=_location(need),
                )
        else:
            _resolve_field(
                app, needs, need, field, schema, config, _ReadsContext(pass_)
            )
        pass_.finish((need_id, field))


def _resolve_field(
    app: Sphinx,
    needs: NeedsMutable,
    need: NeedItem,
    field: str,
    schema: FieldsSchema,
    config: NeedsSphinxConfig,
    reads_ctx: _ReadsContext,
) -> None:
    """Compute the value of one field of one need, and write it into the need.

    The items of the field (calls, variants, variant data, literals) are resolved in
    the order written and joined by the field's type; a failure is one
    ``needs.dynamic_function`` warning, and the field keeps the value it held.
    """
    needs_schema = schema
    needs_config = config
    var_proxy = needs_config.variant_data_proxy
    try:
        if (field_schema := needs_schema.get_any_field(field)) is None:
            raise RuntimeError("does not exist in schema")
        resolved: list[Any] = []
        for item in need._dynamic_fields[field].value:
            if isinstance(item, DynamicFunctionParsed):
                with _reads_reported(
                    f"dynamic function '{item.name}'", field, need, reads_ctx
                ) as reads:
                    func_return = _execute_dynamic_func(
                        app, need, needs, item, reads=reads
                    )
                    if not (
                        field_schema.type_check(func_return)
                        or (
                            field_schema.type == "array"
                            and field_schema.type_check_item(func_return)
                        )
                    ):
                        raise ValueError(
                            f"dynamic function value {type(func_return)} is not of type {field_schema.type!r}"
                            + (
                                ""
                                if field_schema.type != "array"
                                else f" or item type {field_schema.item_type!r}"
                            )
                        )
                    if isinstance(func_return, list | tuple):
                        resolved.extend(func_return)
                    else:
                        resolved.append(func_return)
            elif isinstance(item, VariantFunctionParsed):
                # what a condition reads other than the need's own fields;
                # these names win over a field of the same name
                not_fields: dict[str, Any] = {
                    **needs_config.filter_data,
                    "build_tags": set(app.builder.tags),
                }
                if var_proxy is not None:
                    not_fields["var"] = var_proxy
                var_context: dict[str, Any] = {**need, **not_fields}
                with _reads_reported(
                    "variant condition", field, need, reads_ctx
                ) as reads:
                    if (
                        var_return := _get_variant(
                            item,
                            needs_config.variants,
                            var_context,
                            reader=need,
                            not_fields=not_fields,
                            reads=reads,
                        )
                    ) is not None:
                        if not (
                            field_schema.type_check(var_return)
                            or (
                                field_schema.type == "array"
                                and field_schema.type_check_item(var_return)
                            )
                        ):
                            raise ValueError(
                                f"variant value {type(var_return)} is not of type {field_schema.type!r}"
                                + (
                                    ""
                                    if field_schema.type != "array"
                                    else f" or item type {field_schema.item_type!r}"
                                )
                            )
                        if isinstance(var_return, list | tuple):
                            resolved.extend(var_return)
                        else:
                            resolved.append(var_return)
            elif isinstance(item, VariantDataParsed):
                vd_return = _get_variant_data(item, needs_config.variant_data)
                if not (
                    field_schema.type_check(vd_return)
                    or (
                        field_schema.type == "array"
                        and field_schema.type_check_item(vd_return)
                    )
                ):
                    raise ValueError(
                        f"variant data value {type(vd_return)} is not of type {field_schema.type!r}"
                        + (
                            ""
                            if field_schema.type != "array"
                            else f" or item type {field_schema.item_type!r}"
                        )
                    )
                if isinstance(vd_return, list | tuple):
                    resolved.extend(vd_return)
                else:
                    resolved.append(vd_return)
            else:
                resolved.append(item)

        # a ``None`` result (a ``copy`` of an unset field, a failed check) adds nothing,
        # and a nullable field it leaves with nothing is unset
        values = [el for el in resolved if el is not None]
        if field_schema.type == "string":
            need[field] = (
                None
                if not values and field_schema.nullable
                else " ".join(str(el) for el in values)
            )
        elif field_schema.type in {"integer", "number", "boolean"}:
            # TODO(mh) unboxing the list for non-joinable types
            if len(resolved) > 1:
                raise ValueError(
                    f"Field {field!r} of type {field_schema.type!r} cannot have multiple values"
                )
            need[field] = resolved[0]
        else:
            need[field] = (
                None if resolved and not values and field_schema.nullable else values
            )
    except Exception as err:
        log_warning(
            logger,
            f"Error while resolving dynamic values for field {field!r}, of need {need['id']!r}: {err}",
            "dynamic_function",
            location=(need["docname"], need["lineno"]) if need["docname"] else None,
        )


def _get_variant(
    variant: VariantFunctionParsed,
    variants: dict[str, str],
    context: dict[str, Any],
    *,
    reader: NeedItem,
    not_fields: Container[str],
    reads: UnresolvedReads | None,
) -> str | int | float | bool | None:
    """Return the value of the first variant whose condition holds.

    Each condition evaluated notes the fields of ``reader`` it names into ``reads``
    (:meth:`UnresolvedReads.note_read`), one record for the whole variant; the
    conditions after the first that holds are not evaluated.

    :param variant: The parsed ``<<…>>``.
    :param variants: ``needs_variants``, mapping a name to the condition it stands for.
    :param context: The names a condition is evaluated with.
    :param reader: The need whose field the variant is.
    :param not_fields: The names in ``context`` that are not ``reader``'s fields.
    :param reads: The record of this variant's reads, or ``None`` to note nothing.
    """
    for expr, _, value in variant.expressions:
        expr = variants.get(expr, expr)
        if reads is not None:
            for name in _condition_names(expr):
                if name not in not_fields:
                    reads.note_read(reader, name)
        if bool(eval(expr, context.copy())):
            return value
    return variant.final_value


@lru_cache(maxsize=256)
def _condition_names(expression: str) -> tuple[str, ...]:
    """Return the names a variant condition reads, in the order written, each once.

    A condition that does not parse names nothing here; evaluating it reports the error.

    :param expression: The condition.
    """
    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except (SyntaxError, ValueError):
        return ()
    names = sorted(
        (node for node in ast.walk(tree) if isinstance(node, ast.Name)),
        key=lambda node: (node.lineno, node.col_offset),
    )
    return tuple(dict.fromkeys(node.id for node in names))


def _get_variant_data(
    variant_data: VariantDataParsed,
    variant_data_context: dict[str, Any],
) -> Any:
    """Resolve a variant data reference against the ``var`` namespace.

    The reference is a constrained dotted ``var.*`` path (no arbitrary
    expression evaluation); it is resolved by walking the variant data mapping.

    :param variant_data: The parsed variant data reference.
    :param variant_data_context: The resolved variant data mapping.
    :returns: The resolved value.
    :raises ValueError: if the reference is invalid or cannot be resolved.
    """
    try:
        return lookup_variant_data(variant_data_context, variant_data.expression)
    except VariantDataError as exc:
        raise ValueError(str(exc)) from exc


def check_and_get_content(
    content: str,
    need: NeedItem | NeedPartItem | None,
    env: BuildEnvironment,
    location: nodes.Node,
) -> str:
    """
    Checks if the given content is a function call.
    If not, content is returned.
    If it is, the functions gets executed and its returns value replaces the related part in content.

    This is the ``[[...]]`` syntax as written in a directive option
    (``:style:``, ``needtable``'s ``:style_row:``); it is not applied to a need's content,
    where the ``ndf`` role is the way to call a dynamic function.

    :param content: option content string
    :param need: need
    :param env: Sphinx environment object
    :param location: source location of the function call
    :return: string
    """
    func_match = FUNC_RE.search(content)
    if func_match is None:
        return content

    func_call = func_match.group(1)  # Extract function call
    func_return = execute_func(
        env.app, need, SphinxNeedsData(env).get_needs_view(), func_call, location
    )  # Execute function call and get return value

    if isinstance(func_return, list):
        func_return = ", ".join(str(el) for el in func_return)

    # Replace the function_call with the calculated value
    content = content.replace(
        f"[[{func_call}]]", "" if func_return is None else str(func_return)
    )
    return content


@dataclass(frozen=True, slots=True)
class NeedAttribute:
    """A reference to a need field."""

    name: str


DFuncArg: TypeAlias = (
    str | int | float | bool | list[str | int | float | bool] | NeedAttribute
)


@dataclass(frozen=True, slots=True)
class DynamicFunctionParsed:
    """A dynamic function call."""

    name: str
    args: tuple[DFuncArg, ...]
    kwargs: tuple[tuple[str, DFuncArg], ...]

    def kwargs_dict(self) -> Mapping[str, DFuncArg]:
        """Return kwargs as dictionary."""
        return dict(self.kwargs)

    def apply_need(self, need: NeedItem | NeedPartItem) -> DynamicFunctionParsed:
        """Replace NeedAttribute args and kwargs with actual values from given need.

        :raises FunctionParsingException: if need does not have the required attribute
        """
        new_args: list[DFuncArg] = []
        for arg in self.args:
            if isinstance(arg, NeedAttribute):
                if arg.name not in need:
                    raise FunctionParsingException(
                        f"need has no attribute {arg.name!r}", self.name
                    )
                new_args.append(need[arg.name])
            else:
                new_args.append(arg)
        new_kwargs: list[tuple[str, DFuncArg]] = []
        for key, value in self.kwargs:
            if isinstance(value, NeedAttribute):
                if value.name not in need:
                    raise FunctionParsingException(
                        f"need has no attribute {value.name!r}", self.name
                    )
                new_kwargs.append((key, need[value.name]))
            else:
                new_kwargs.append((key, value))
        return DynamicFunctionParsed(self.name, tuple(new_args), tuple(new_kwargs))

    @classmethod
    def from_string(
        cls, func_string: str, *, allow_need: bool = False
    ) -> DynamicFunctionParsed:
        """Create a DynamicFunction from a string.

        :param func_string: The function string.
        :param allow_need: Whether to allow `need.<field>` as argument.
        :raises FunctionParsingException: if the function string is not valid.
        """
        try:
            func = ast.parse(func_string.strip())
            func_call = func.body[0].value  # ty: ignore[unresolved-attribute]
            assert isinstance(func_call, ast.Call)
            func_name = func_call.func.id
            assert isinstance(func_name, str)
        except Exception as e:
            raise FunctionParsingException("Not a function call", None) from e

        func_args: list[DFuncArg] = []
        for i, arg in enumerate(func_call.args):
            if isinstance(arg, ast.Constant) and isinstance(
                arg.value, str | int | float | bool
            ):
                func_args.append(arg.value)
            elif isinstance(arg, ast.List):
                el_list: list[str | int | float | bool] = []
                for j, element in enumerate(arg.elts):
                    if isinstance(element, ast.Constant) and isinstance(
                        element.value, str | int | float | bool
                    ):
                        el_list.append(element.value)
                    else:
                        raise FunctionParsingException(
                            f"Unsupported arg {i} item {j} value type", func_name
                        )
                func_args.append(el_list)
            elif (
                allow_need
                and isinstance(arg, ast.Attribute)
                and isinstance(arg.value, ast.Name)
                and arg.value.id == "need"
            ):
                func_args.append(NeedAttribute(arg.attr))
            else:
                raise FunctionParsingException(
                    f"Unsupported arg {i} value type", func_name
                )
        func_kwargs: list[tuple[str, DFuncArg]] = []
        for keyword in func_call.keywords:
            kvalue = keyword.value
            kkey = keyword.arg
            if not isinstance(kkey, str):
                raise FunctionParsingException(
                    "Keyword argument must have a string key", func_name
                )
            if isinstance(kvalue, ast.Constant) and isinstance(
                kvalue.value, str | int | float | bool
            ):
                func_kwargs.append((kkey, kvalue.value))
            elif isinstance(kvalue, ast.List):
                el_list = []
                for j, element in enumerate(kvalue.elts):
                    if isinstance(element, ast.Constant) and isinstance(
                        element.value, str | int | float | bool
                    ):
                        el_list.append(element.value)
                    else:
                        raise FunctionParsingException(
                            f"Unsupported kwarg {kkey!r} item {j} value type", func_name
                        )
                func_kwargs.append((kkey, el_list))
            elif (
                allow_need
                and isinstance(kvalue, ast.Attribute)
                and isinstance(kvalue.value, ast.Name)
                and kvalue.value.id == "need"
            ):
                func_kwargs.append((kkey, NeedAttribute(kvalue.attr)))
            else:
                raise FunctionParsingException(
                    f"Unsupported kwarg {kkey!r} value type", func_name
                )

        return cls(func_name, tuple(func_args), tuple(func_kwargs))
