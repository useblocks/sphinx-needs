"""
Sphinx-needs functions module
=============================

Cares about the correct registration and execution of sphinx-needs functions to support dynamic values
in need configurations.
"""

from __future__ import annotations

import ast
import inspect
import re
from collections.abc import Callable, Container, Iterator, Mapping, Sequence
from contextlib import AbstractContextManager, contextmanager, nullcontext
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Final, Protocol, TypeAlias, TypeVar

from docutils import nodes
from sphinx.application import Sphinx
from sphinx.environment import BuildEnvironment
from sphinx.util.logging import suppress_logging

from sphinx_needs import _read_watch
from sphinx_needs._source_facets import explained, unavailable
from sphinx_needs._wording import joined
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import NeedsMutable, SphinxNeedsData
from sphinx_needs.debug import measure_time_func
from sphinx_needs.derive import DeriveCall, DeriveRule, fingerprint_names, is_union
from sphinx_needs.exceptions import FunctionParsingException
from sphinx_needs.filter_common import filter_needs_and_parts, filter_single_need
from sphinx_needs.logging import get_logger, log_warning
from sphinx_needs.need_item import NeedItem, NeedLink, NeedPartItem
from sphinx_needs.needs_schema import (
    FieldSchema,
    FieldShape,
    FieldsSchema,
    LinkSchema,
)
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
        Declaration,
        Node,
        NodeReads,
        OutOfScope,
        Project,
        Reason,
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
        if (unset := _unset_selector_error(needs_config, df, need)) is not None:
            raise RuntimeError(unset)
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


def _unset_selector_error(
    needs_config: NeedsSphinxConfig,
    df: DynamicFunctionParsed,
    need: NeedItem | NeedPartItem,
) -> str | None:
    """The error of a built-in call whose ``need.<field>`` selector is unset, if any."""
    # it imports this module
    from sphinx_needs.functions.order import BUILTINS, unset_selector

    if (
        df.name in needs_config.functions
        and needs_config.functions[df.name]["function"] is BUILTINS.get(df.name)
        and (attr := unset_selector(df, need)) is not None
    ):
        return (
            f"Error while applying need to function {df.name!r}: need.{attr} "
            "selects what the call reads, and is not set"
        )
    return None


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

    needs_config = NeedsSphinxConfig(app.config)

    if need is not None:
        if (unset := _unset_selector_error(needs_config, df, need)) is not None:
            log_warning(logger, unset, "dynamic_function", location=location)
            return "??"
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
# that is only a read of a value computed after the built-in functions -- by your own
# function, by a call whose filter cannot be read, or a union over one of those -- by
# a call computed last itself, before it. Nothing else is handed a record: an ``ndf`` role or a
# ``:style_row:`` runs after the pass, and a user's own function, which the pass calls
# without one, has none to give a built-in it calls; such a built-in gets
# ``reads=None`` and notes nothing. What no record holds -- your own function's reads,
# and those of a built-in call's filter or ``where`` -- is watched as it happens instead,
# in a stratum where it can read a value not computed yet (:class:`_LateReads`).


class UnresolvedReads:
    """The reads of values not computed yet, made by ONE call or ``<<…>>`` variant.

    ``resolve_functions`` creates one for each call and each ``<<…>>`` variant (shared
    by all the conditions it evaluates), hands it to the dynamic function as its
    ``reads`` keyword when the function is marked :func:`records_reads`, and reports
    what it holds as ``needs.derive_scope`` once the call is over. No other caller
    creates one: after the pass every value read is final, and a user's function's
    reads, through a built-in or otherwise, are watched instead (:class:`_LateReads`).

    Kept by the name read, in the order first read, each need named once per name.

    :param pending: The ``(need id, name)`` values of the pass not computed yet.
    :param shared: What the calls of one stratum of the pass (the link fields, the
        other fields, the late rules) work out once and share (the index of a join),
        or ``None`` outside the pass.
    """

    __slots__ = ("_pending", "_reads", "shared")

    def __init__(
        self,
        pending: Container[tuple[str, str]],
        shared: dict[Any, Any] | None = None,
    ) -> None:
        self._pending = pending
        self._reads: dict[str, dict[str, None]] = {}
        #: what the calls of the stratum share, from one call to the next
        self.shared = shared

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

    def noted(self, name: str, need_id: str) -> bool:
        """Whether ``name`` of the need ``need_id`` was noted already."""
        return need_id in self._reads.get(name, ())

    def is_pending(self, need_id: str, name: str) -> bool:
        """Whether the field or link ``name`` of the need ``need_id`` is computed in the
        pass and not computed yet."""
        return (need_id, name) in self._pending

    def reads(self) -> list[tuple[str, list[str]]]:
        """Return each name read, with the ids of the needs it was read on."""
        return [(name, list(ids)) for name, ids in self._reads.items()]


_DynamicFunctionT = TypeVar("_DynamicFunctionT", bound=Callable[..., Any])

#: the attribute of a dynamic function of your own declaring what it reads: the
#: :class:`Reads` :func:`~sphinx_needs.api.configuration.reads` made
READS_ATTRIBUTE: Final = "needs_reads"


@dataclass(frozen=True, slots=True)
class Reads:
    """What a dynamic function of your own reads,
    as :func:`~sphinx_needs.api.configuration.reads` declares it:
    the parameters whose argument is a field name, read on the call's own
    need (``own``) or on every need (``every``).

    Applied to a function, it declares it: ``reads(own="option")(my_function)`` is
    ``@reads(own="option")``. Given to
    :func:`~sphinx_needs.api.configuration.add_dynamic_function` as ``reads``, it
    declares a function you do not own.
    """

    own: tuple[str, ...] = ()
    every: tuple[str, ...] = ()

    def __call__(self, function: _DynamicFunctionT) -> _DynamicFunctionT:
        # through ``vars``: the type checker refuses an attribute assignment on a callable
        vars(function)[READS_ATTRIBUTE] = self
        return function


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


def _reads_phrase(
    reads: Sequence[tuple[str, Sequence[str]]], linked: Sequence[str] = ()
) -> str:
    """Each name once, with the one need it was read on, or a count and the first three.

    :param linked: Names read on every need the reader's own links name, which are not
        known yet.
    """
    return joined(
        [
            f"'{name}' on need '{ids[0]}'"
            if len(ids) == 1
            else f"'{name}' on {counted_ids(ids, ' needs')}"
            for name, ids in reads
        ]
        + [f"'{name}' on every need its links name" for name in linked]
    )


def _one(reads: Sequence[tuple[str, Sequence[str]]]) -> bool:
    """Whether the reads are one name read on one need."""
    return len(reads) == 1 and len(reads[0][1]) == 1


def _derive_scope_message(
    what: str,
    option: str,
    reads: Sequence[tuple[str, Sequence[str]]],
    cause: str,
    on: str = "",
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
    :param on: The needs the reader computes the field on, when it is more than one
        (``" on 3 needs (A, B, C)"``).
    :raises ValueError: If there is no read.
    """
    if not reads:
        raise ValueError("no read to report")
    when = "it was" if _one(reads) else "they were"
    return (
        f"{what} for option '{option}'{on} read {_reads_phrase(reads)} "
        f"before {when} computed: {cause}"
    )


def _kept(value: Any) -> str:
    """What a field that is not computed holds, from its placeholder value."""
    return (
        "the field keeps only its written items" if value else "the field is left empty"
    )


def _through_clause(through: tuple[Column, Reason] | None) -> str:
    """What a cycle member reads its cycle through, as its message says it.

    :param through: The column on the cycle the member reads, with why every need is
        its candidate; ``None`` for no column.
    """
    if through is None:
        return ""
    column, reason = through
    # it imports this module
    from sphinx_needs.functions.order import DeclaredRead, JoinRead

    if isinstance(reason, DeclaredRead):
        return f", through {reason.function}'s declared read of {column.field!r} on every need"
    if isinstance(reason, tuple):
        return (
            f", through its {reason[1]}, which are computed in the same step, "
            "so every need is a candidate"
        )
    if isinstance(reason, JoinRead):
        return f", through the join on {column.field!r}"
    if reason is not None:
        return (
            f", through the filter {reason!r}, which names a computed field, "
            "so every need is a candidate"
        )
    if column.candidates is not None:
        return f", through the filter {column.candidates!r}, which keeps a need on the cycle"
    return ", through a sum over every need"


def _argument_clause(
    node_reads: NodeReads, need_id: str, members: Sequence[Node]
) -> str:
    """A cycle member's ``need.<field>`` arguments on the cycle, as its message says
    them: a declared call reads each before it is computed."""
    on_cycle = sorted(
        {
            name
            for declared in node_reads.declared
            for name in declared.arguments
            if (need_id, name) in members
        }
    )
    if not on_cycle:
        return ""
    return f", through its argument{'s' if len(on_cycle) > 1 else ''} " + joined(
        [f"need.{name}" for name in on_cycle]
    )


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


def _out_of_scope_message(
    option: str, out_of_scope: OutOfScope, value: Any, stratum: int = 1
) -> str:
    """Return the ``needs.derive_scope`` message for a call or variant not computed.

    :param option: The field it computes.
    :param out_of_scope: The call or variant, and why it cannot be computed in its
        stratum.
    :param value: The value the field holds instead (its placeholder).
    :param stratum: The stratum it is computed in: a read out of the scope of stratum 1
        is of a value final after the link fields, one of stratum 2 of a value computed
        in the late step.
    """
    what = out_of_scope.what
    not_run = (
        "the condition is not evaluated"
        if what == "variant condition"
        else "the rule is not run"
        if what.startswith("derive rule")
        else "the call is not run"
    )
    if selectors := out_of_scope.selectors:
        return (
            f"{what} for option '{option}' names its target by "
            f"{joined([repr(s) for s in selectors])}, which "
            f"{'is' if len(selectors) == 1 else 'are'} computed in the same step: "
            f"{not_run} and {_kept(value)}"
        )
    if out_of_scope.unions:
        unions: dict[str, list[str]] = {}
        for name, read_id in out_of_scope.unions:
            unions.setdefault(name, []).append(read_id)
        read = list(unions.items())
        return (
            f"{what} for option '{option}' reads {_reads_phrase(read)}, "
            f"{'a union' if _one(read) else 'unions'} computed after your own "
            "functions and the calls whose filter cannot be read that fill "
            f"{'its' if _one(read) else 'their'} members, which this step cannot wait "
            f"for: {not_run} and {_kept(value)}"
        )
    names: dict[str, list[str]] = {}
    for name, read_id in out_of_scope.reads:
        names.setdefault(name, []).append(read_id)
    reads = list(names.items())
    linked = out_of_scope.linked
    one = _one(reads) if not linked else not reads and len(linked) == 1
    final = (
        "final only after the link fields are computed"
        if stratum == 1
        else "computed in the late step, after every other field "
        "(a derive rule of the kind 'hash' or 'fingerprint', or with "
        'after = "derived")'
    )
    return (
        f"{what} for option '{option}' reads {_reads_phrase(reads, linked)}, which "
        f"{'is' if one else 'are'} {final}: {not_run} and {_kept(value)}"
    )


class _Pass:
    """One ``resolve_functions`` pass: the values not computed yet, and why.

    :param project: The nodes of the pass.
    """

    def __init__(self, project: Project) -> None:
        self.project = project
        self.stratum: Stratum | None = None
        #: what the derive rules compute once per pass (the components of a
        #: ``transitive`` rule's links), shared by the needs
        self.rule_cache: dict[Any, Any] = {}
        #: what the calls compute once per stratum (the link fields, the other fields,
        #: the late rules): the index of a join's field, built from the values final in
        #: it, shared by the needs
        self.stratum_cache: dict[Any, Any] = {}
        #: the links the link-valued calls (:data:`LINK_CALLS`) of each ``(need id,
        #: link field)`` computed into its list, once stored: what
        #: ``needs.derive_dense`` counts on a link type without a rule
        self.called_links: dict[Node, tuple[int, frozenset[str]]] = {}
        #: the functions whose refused declaration was reported
        self.refused_warned: set[str] = set()
        #: the names of the fields some need computes in the pass (``parent_need``
        #: for a computed ``parent_needs``)
        self.computed_names: frozenset[str] = frozenset(
            name for _, name in project.nodes
        ) | (
            frozenset({"parent_need"})
            if project.field_of("parent_need") in project.computed_fields
            else frozenset()
        )
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

    def kind(self, node: Node) -> tuple[str, Sequence[str]]:
        """Why ``node``, not computed yet, is computed after its reader, with the
        functions that compute it.

        ``"union"``, a union computed after the nodes computed last; ``"user"``, your
        own function; ``"opaque"``, a call whose filter cannot be read; ``"later"``, a
        value of a later stratum; ``"other"``, a read the order did not account for.
        """
        node_reads = self.stratum.reads.get(node) if self.stratum is not None else None
        if self.stratum is not None and node in self.stratum.after_last:
            return "union", ()
        if node_reads is not None and node_reads.user_functions:
            return "user", node_reads.user_functions
        if node_reads is not None and node_reads.opaque:
            return "opaque", ()
        if self.stratum is not None and self.project.nodes.get(node, 0) > (
            self.stratum.stratum
        ):
            return "later", ()
        return "other", ()

    def cause(
        self,
        kind: str,
        group: Sequence[tuple[str, Sequence[str]]],
        functions: Sequence[str],
        *,
        reader_last: bool = False,
    ) -> str:
        """Why the values of ``group`` were read before they were computed.

        :param kind: What computes them (:meth:`kind`).
        :param functions: Your own functions computing them, for ``"user"``.
        :param reader_last: The reader is computed after the built-in functions itself
            (your own function, or a call whose filter cannot be read).
        """
        subject = "it is" if _one(group) else "they are"
        after = (
            ", after this call: your own functions, and the calls whose filter cannot "
            "be read, run after the built-in functions, in (need id, field) order"
        )
        if kind == "user":
            names = joined([f"'{f}'" for f in functions])
            plural = len(functions) > 1
            computed = f"{subject} computed by your own function{'s' if plural else ''} {names}"
            if reader_last:
                return computed + after
            return f"{computed}, which run{'' if plural else 's'} after the built-in functions"
        if kind == "opaque":
            computed = f"{subject} computed by a call whose filter cannot be read"
            if reader_last:
                return computed + after
            return f"{computed}, which runs after the other built-in functions"
        if kind == "union":
            return (
                f"{'it is a union' if _one(group) else 'they are unions'} computed "
                "after your own functions and the calls whose filter cannot be read "
                f"that fill {'its' if _one(group) else 'their'} members, after this "
                "call"
            )
        if kind == "later":
            name, ids = group[0]
            node = (ids[0], self.project.field_of(name))
            if self.project.nodes.get(node) == 2:
                return f"{subject} computed after the link fields, in a later step"
            return (
                f"{subject} computed in the late step, after every other field "
                "(a derive rule of the kind 'hash' or 'fingerprint', or with "
                'after = "derived")'
            )
        return (
            "the order of the pass did not account for this read; please "
            "report this at https://github.com/useblocks/sphinx-needs/issues"
        )

    def causes(
        self, reads: Sequence[tuple[str, Sequence[str]]]
    ) -> list[tuple[str, list[tuple[str, list[str]]]]]:
        """The reads of a call, grouped by why they were read before being computed.

        Such a value is computed after the built-in functions: by your own function,
        or by a call whose filter cannot be read, or it is a union computed after
        those, as a member of it is. Any other is a read the order did not account
        for.
        """
        groups: dict[str, list[tuple[str, list[str]]]] = {}
        functions: dict[str, None] = {}
        for name, ids in reads:
            for need_id in ids:
                kind, computing = self.kind((need_id, self.project.field_of(name)))
                functions.update(dict.fromkeys(computing))
                group = groups.setdefault(kind, [])
                if not group or group[-1][0] != name:
                    group.append((name, []))
                group[-1][1].append(need_id)
        return [
            (self.cause(kind, group, list(functions)), group)
            for kind, group in groups.items()
        ]


@dataclass
class _Found:
    """The reads of values not computed yet one reader made, for one cause."""

    #: the reader's first need, where the warning is located
    need: NeedItem
    #: the needs the reader computes a value of, which read them
    readers: dict[str, None] = dataclass_field(default_factory=dict)
    #: each name read, with the needs it was read on
    reads: dict[str, dict[str, None]] = dataclass_field(default_factory=dict)
    #: your own functions computing them, for the kind ``"user"``
    functions: dict[str, None] = dataclass_field(default_factory=dict)
    reader_last: bool = False


class _LateReads:
    """The reads of values not computed yet that only a call's run shows, in one
    stratum, and their report.

    The order of a stratum cannot put everything before its readers: your own
    functions that declare nothing, and the calls whose filter cannot be read, are
    computed after the built-in functions, in ``(need id, field)`` order, and read
    what they like. While such a call runs, and while a filter or ``where`` of a
    built-in call or rule is evaluated in a stratum that has such calls, every read
    of a value of the pass is watched (:mod:`sphinx_needs._read_watch`), and one not
    computed yet at that moment is noted. A call of a function that declares what it
    reads is watched in any stratum: any read of a value of its own stratum that its
    declaration does not name is noted too, computed yet or not. What the call's own
    record notes (a built-in marked ``records_reads``) is left to it. Nothing is
    changed: the reader runs as it would, and is told. Each reader is one ``needs.derive_scope`` per
    cause, naming the needs read: your own function, every call of it computing a
    field, or a built-in call or rule computing a field, on every need it computes
    it.

    :param pass_: The pass, at the stratum.
    """

    def __init__(self, pass_: _Pass) -> None:
        self.pass_ = pass_
        stratum = pass_.stratum
        #: the stratum computes nodes after its built-in ones: only then can a
        #: built-in node's filter read a value not computed yet
        self.late = stratum is not None and any(r.last for r in stratum.reads.values())
        self.found: dict[tuple[str, str, str], _Found] = {}
        #: the kinds the reads of one recorded list (by its id) gave a reader
        #: (``what``, ``option``), with the list, kept alive
        self._replays: dict[
            tuple[int, str, str], tuple[list[tuple[str, str]], list[str]]
        ] = {}
        #: why each node read before it was computed is computed after its reader
        #: (:meth:`_Pass.kind`), which the order of the stratum fixes
        self._kinds: dict[Node, tuple[str, Sequence[str]]] = {}

    def watch(
        self,
        item: DynamicFunctionParsed | DeriveCall,
        position: int,
        need: NeedItem,
        field: str,
        record: UnresolvedReads,
    ) -> AbstractContextManager[Any]:
        """Watch the reads of one call of a node while it runs, if they can read a
        value not computed yet.

        :param item: The call or the rule.
        :param position: Its position among the node's items.
        :param need: The need the node is of.
        :param field: The node's field.
        :param record: The call's record: what it notes itself is not noted again.
        """
        pass_ = self.pass_
        project = pass_.project
        node_reads = pass_.stratum.reads[(need.id, field)] if pass_.stratum else None
        own = (
            isinstance(item, DynamicFunctionParsed)
            and item.name not in project.builtins
        )
        if not own and not self.late:
            return nullcontext()
        declared = next(
            (
                d
                for d in (node_reads.declared if node_reads is not None else ())
                if d.position == position
            ),
            None,
        )
        what = (
            f"dynamic function '{item.name}'"
            if isinstance(item, DynamicFunctionParsed)
            else item.describe()
        )
        current = (need.id, field)
        reader_last = node_reads is not None and node_reads.last
        pending = pass_.pending
        field_of = project.field_of
        computed = pass_.computed_names
        kinds = self._kinds
        stratum = pass_.stratum.stratum if pass_.stratum is not None else 0
        #: the reads noted while the call runs, as ``(kind, need id, name, functions)``,
        #: or ``(kind, None, None, ())`` for a reader of a replay already noted;
        #: kept until the call is over, as the call's record may note them too
        noted: list[tuple[str, str | None, str | None, Sequence[str]]] = []

        def on_read(need_id: str, name: str) -> bool:
            # the watch passes on only the names some need computes; of those, an
            # undeclared reader's read of a value computed already is one lookup
            if declared is None and (need_id, name) not in pending:
                return False
            node = (need_id, field_of(name))
            if node == current:
                return False
            if declared is not None:
                if (computed_in := project.nodes.get(node)) is None:
                    return False
                if computed_in == stratum and not declared.covers(*node):
                    # strict: a value of its own step it does not declare, computed
                    # yet or not; one of an earlier step is final
                    noted.append(("undeclared", need_id, name, ()))
                    return True
                if (need_id, name) not in pending:
                    return False
            if record.noted(name, need_id):
                return False
            if (cause := kinds.get(node)) is None:
                cause = kinds[node] = pass_.kind(node)
            noted.append((cause[0], need_id, name, cause[1]))
            return True

        def replayed(reads: list[tuple[str, str]]) -> None:
            # a result computed once and used by every need computing the rule (a
            # ``links`` rule's candidates): the reads, worked out once per reader
            memo = self._replays.get(memo_key := (id(reads), what, field))
            if memo is not None and memo[0] is reads:
                noted.extend((kind, None, None, ()) for kind in memo[1])
                return
            start = len(noted)
            for need_id, name in reads:
                on_read(need_id, name)
            self._replays[memo_key] = (
                reads,
                list(dict.fromkeys(entry[0] for entry in noted[start:])),
            )

        @contextmanager
        def watched() -> Iterator[None]:
            try:
                with _read_watch.watching(
                    on_read, filters_only=not own, names=computed, replayed=replayed
                ):
                    yield
            finally:
                # what the call's record reports itself is not reported again
                for kind, need_id, name, functions in noted:
                    if need_id is None or name is None:
                        if (found := self.found.get((what, field, kind))) is not None:
                            found.readers[need.id] = None
                    elif not record.noted(name, need_id):
                        self._note(
                            what,
                            field,
                            kind,
                            need,
                            need_id,
                            name,
                            functions,
                            reader_last,
                        )

        return watched()

    def _note(
        self,
        what: str,
        option: str,
        kind: str,
        need: NeedItem,
        need_id: str,
        name: str,
        functions: Sequence[str] = (),
        reader_last: bool = False,
    ) -> None:
        found = self.found.get(key := (what, option, kind))
        if found is None:
            found = self.found[key] = _Found(need, reader_last=reader_last)
        found.readers[need.id] = None
        found.reads.setdefault(name, {})[need_id] = None
        for function in functions:
            found.functions[function] = None

    def report(self) -> None:
        """Warn of every reader and cause noted, in the order first noted."""
        for (what, option, kind), found in self.found.items():
            reads = [(name, list(ids)) for name, ids in found.reads.items()]
            on = (
                ""
                if len(found.readers) == 1
                else f" on {counted_ids(found.readers, ' needs')}"
            )
            if kind == "undeclared":
                it = "it" if _one(reads) else "them"
                function = what.removeprefix("dynamic function ")
                message = (
                    f"{what} for option '{option}'{on} read {_reads_phrase(reads)}, "
                    f"which {'is' if _one(reads) else 'are'} computed in its step and "
                    f"not among the reads {function} declares: the call is not ordered "
                    f"after {it}, and may read {it} before {'it is' if _one(reads) else 'they are'} "
                    f"computed; declare {it} among its reads"
                )
            else:
                cause = self.pass_.cause(
                    kind, reads, list(found.functions), reader_last=found.reader_last
                )
                message = _derive_scope_message(what, option, reads, cause, on)
            log_warning(logger, message, "derive_scope", location=_location(found.need))
        self.found = {}
        self._replays = {}


@dataclass(frozen=True, slots=True)
class _ReadsContext:
    """What the record of one node's calls needs from the pass.

    :ivar pass_: The pass.
    :ivar late: The reads of values not computed yet that the run of a call shows.
    """

    pass_: _Pass
    late: _LateReads

    def record(self) -> UnresolvedReads:
        """A new record, for one call or ``<<…>>`` variant."""
        return UnresolvedReads(self.pass_.pending, self.pass_.stratum_cache)

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
                    needs.values(),
                    needs_config,
                    filter_string,
                    current,
                    origin_docname=current["docname"],
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

    rules = materialise_derive_rules(needs, needs_schema)
    project = Project(
        needs,
        rules=rules,
        link_fields=list(needs_schema.iter_link_field_names()),
        variants=needs_config.variants,
        not_fields={*needs_config.filter_data, "build_tags", "var"},
        builtins={name: f["function"] for name, f in needs_config.functions.items()},
        copy_match=copy_match,
        sum_candidates=sum_candidates,
        content_refs=content_refs,
        fingerprint_names=list(fingerprint_names(needs_schema)),
        declared=_declarations(needs_config),
    )
    pass_ = _Pass(project)
    # the one reset of the pass: a link field's function reads no back link of an
    # earlier build, and the barrier builds them into the empty lists
    for need in needs.values():
        need.reset_backlinks()
    _resolve_stratum(app, needs, pass_, 1, needs_schema, needs_config)
    build_backlinks(needs, needs_schema, reset=False)
    _resolve_stratum(app, needs, pass_, 2, needs_schema, needs_config)
    # the late step: the derive rules of the kind ``hash`` or ``fingerprint``, or with
    # after = "derived"
    _resolve_stratum(app, needs, pass_, 3, needs_schema, needs_config)
    # from the final lists, on every build
    _warn_dense(needs, pass_, needs_schema, needs_config.derive_max_links_per_need)


#: The dynamic functions that compute a list of links: on a link type without a derive
#: rule, ``needs.derive_dense`` counts the links they computed.
LINK_CALLS = frozenset({"links_from_content", "links_from_filter", "links_from_match"})


@dataclass
class _Density:
    """The links a link type's rule, or its link-valued calls, computed on every need."""

    #: the links, summed over the needs
    links: int = 0
    #: the needs whose list was computed
    carriers: int = 0
    #: the longest list, and the need computing it (the lowest id of a tie)
    longest: int = -1
    longest_need: str = ""
    #: the kinds of the rule (``derive_by_type`` may differ per type), or the calls
    sources: set[str] = dataclass_field(default_factory=set)
    by_rule: bool = False

    def add(self, need_id: str, links: int) -> None:
        self.links += links
        self.carriers += 1
        if links > self.longest or (
            links == self.longest and need_id < self.longest_need
        ):
            self.longest, self.longest_need = links, need_id


def _warn_dense(
    needs: NeedsMutable, pass_: _Pass, schema: FieldsSchema, threshold: int
) -> None:
    """Warn of each link type whose computed lists hold more links than ``threshold``
    times the needs of the project (``needs.derive_dense``), once.

    The lists a ``links`` or ``content_links`` rule computed are counted, or, on a link
    type without a rule, the links :data:`LINK_CALLS` computed; never a written link,
    one a ``needextend`` adds, a back link, or a ``union``'s list, which holds the links
    of its members. A link stored is counted, dead or to a
    part; a link two calls of one need computed is stored, and counted, once. The
    needs of the project are every need, external and imported ones too, never a part.
    It counts the lists as the pass left them, so every build warns alike; ``0`` (or
    less) never warns, nor does a threshold that is not an integer (a boolean
    included), which Sphinx's type check reports.
    """
    if not isinstance(threshold, int) or isinstance(threshold, bool) or threshold <= 0:
        return
    densities: dict[str, _Density] = {}
    for (need_id, field), call in pass_.project.rules.items():
        if call.rule.link_valued:
            density = densities.setdefault(field, _Density(by_rule=True))
            if is_union(call.rule):
                # its links are its members' links, counted where they are computed
                continue
            density.sources.add(call.rule.kind)
            density.add(need_id, len(set(needs[need_id][field])))
    for (need_id, field), (links, calls) in pass_.called_links.items():
        # a derived link type ignores the calls written in it
        density = densities.setdefault(field, _Density())
        if not density.by_rule:
            density.sources.update(calls)
            density.add(need_id, links)
    most = threshold * len(needs)
    for field in schema.iter_link_field_names():
        if (density := densities.get(field)) is None or density.links <= most:
            continue
        if density.by_rule:
            kinds = sorted(density.sources)
            source = (
                f"its derive rule{'s' if len(kinds) > 1 else ''} "
                f"(kind{'s' if len(kinds) > 1 else ''} "
                f"{', '.join(repr(kind) for kind in kinds)})"
            )
            narrow = "the rule's where"
        else:
            calls = sorted(density.sources)
            source = (
                f"the dynamic function{'s' if len(calls) > 1 else ''} "
                f"{', '.join(calls)}"
            )
            narrow = "the calls' filter"
        log_warning(
            logger,
            f"Link type {field!r} stores {density.links} links computed by {source} on "
            f"{_count(density.carriers, 'need')}, more than {threshold} per need of the "
            f"project ({_count(len(needs), 'need')}, at most {most}); the longest list, "
            f"{_count(density.longest, 'link')}, is {density.longest_need}'s. "
            f"Narrow {narrow}, roll the set up on one need over the back links (a count "
            "or collect over a '_back' field), or show it in a view such as needtable; "
            "to keep it, raise needs_derive_max_links_per_need (0 never warns) or add "
            "'needs.derive_dense' to suppress_warnings",
            "derive_dense",
            location=None,
        )


def _count(number: int, noun: str) -> str:
    return f"{number} {noun}{'' if number == 1 else 's'}"


def materialise_derive_rules(
    needs: NeedsMutable, schema: FieldsSchema
) -> dict[tuple[str, str], DeriveCall]:
    """Give every derived field of every need from the project's sources its rule.

    Each pass reads the rules from the current schema, so a need's derived values never
    depend on the configuration it was created under. The rule is the field's one
    computed item (a :class:`~sphinx_needs.derive.DeriveCall`), and the field holds its
    empty value until it is computed; a rule that cannot be read leaves it empty. The
    rule is the one of the need's type (``derive_by_type``), else ``derive``; a need of
    a type without one holds the field's default (else ``None``, or its empty value),
    and has no computed item; the default, and whether the field is nullable, are
    those of the need's type. A need created by ``needimport`` or loaded as an external
    need keeps the values it carries: no rule runs on it.

    :return: The rule of each ``(need id, field)`` computed by one.
    """
    # imported here, as the order module imports this one
    from sphinx_needs.functions.order import typed_empty

    derived = [
        field
        for field in (*schema.iter_extra_fields(), *schema.iter_link_fields())
        if field.derived
    ]
    rules: dict[tuple[str, str], DeriveCall] = {}
    if not derived:
        return rules
    for need_id, need in needs.items():
        if need["is_import"] or need["is_external"]:
            continue
        # the fields as the need's type declares them: its nullable and default
        type_schema = schema.for_type(need["type"])
        for derived_field in derived:
            field = type_schema.get_any_field(derived_field.name)
            # an overlay keeps the field's derivation (add_type_overlay)
            assert field is not None and field.derived
            rule = field.rule_for(need["type"])
            if rule is None:
                need._set_resolved(field.name, field.off_type_value())
                continue
            if isinstance(rule, DeriveRule):
                rules[(need_id, field.name)] = DeriveCall(rule)
            need._set_resolved(field.name, typed_empty(field))
    return rules


def _declarations(config: NeedsSphinxConfig) -> dict[str, Declaration]:
    """The declaration of what it reads of each registered function carrying one, as
    its registration checked it."""
    return {
        name: declaration
        for name, registered in config.functions.items()
        if (declaration := registered.get("reads")) is not None
    }


def declaration_of(
    function: Callable[..., Any], reads: Any
) -> Declaration | str | None:
    """The declaration of what a function being registered reads, or why it is none.

    :param function: The function.
    :param reads: ``add_dynamic_function``'s ``reads``; ``None`` for the declaration the
        function carries (``needs_reads``), if any.
    :return: ``None`` for no declaration, else the declaration, or why it cannot be
        used: it is no :class:`Reads`, or names what is not a parameter of the function
        after ``app``, ``need`` and ``needs``.
    """
    # it imports this module
    from sphinx_needs.functions.order import Declaration

    if reads is None:
        reads = getattr(function, READS_ATTRIBUTE, None)
    if reads is None:
        return None
    if not isinstance(reads, Reads):
        return (
            f"its declaration is {type(reads).__name__}, not one "
            "sphinx_needs.api.reads made"
        )
    try:
        signature = inspect.signature(function)
    except (TypeError, ValueError) as err:
        return f"its parameters cannot be read: {err}"
    parameters = list(signature.parameters.values())[3:]
    known = {parameter.name: parameter for parameter in parameters}
    for name in (*reads.own, *reads.every):
        parameter = known.get(name)
        if parameter is None:
            return f"{name!r} is not a parameter of it after app, need and needs"
        if parameter.kind is inspect.Parameter.VAR_KEYWORD:
            return f"{name!r} is its keyword arguments, not a parameter"
    return Declaration(signature.replace(parameters=parameters), reads.own, reads.every)


def _warn_refused(project: Project, warned: set[str]) -> None:
    """Warn once of each function whose declaration could not be applied to a call."""
    for name, ((need_id, field), why) in project.refused.items():
        if name in warned:
            continue
        warned.add(name)
        log_warning(
            logger,
            f"dynamic function {name!r} declares what it reads, but the declaration "
            f"cannot be applied to its call for option {field!r} of need {need_id!r}: "
            f"{why}; such a call is computed after the built-in functions, as a call "
            "of a function that declares nothing",
            "config",
            location=_location(project.needs[need_id]),
        )


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
    _warn_refused(pass_.project, pass_.refused_warned)
    # a value your own function computes is final only at the end of its stratum
    pass_.stratum_cache = {}
    reads_ctx = _ReadsContext(pass_, _LateReads(pass_))
    for step in stratum.steps:
        if step.cycle:
            for need_id, field in step.nodes:
                needs[need_id]._set_resolved(
                    field, placeholder(needs[need_id], field, schema)
                )
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
                        _through_clause(through)
                        + _argument_clause(node_reads, need_id, step.nodes)
                        + own,
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
            value = placeholder(need, field, schema)
            need._set_resolved(field, value)
            for out_of_scope in node_reads.scope:
                log_warning(
                    logger,
                    _out_of_scope_message(field, out_of_scope, value, number),
                    "derive_scope",
                    location=_location(need),
                )
        else:
            _resolve_field(app, needs, need, field, schema, config, reads_ctx)
        pass_.finish((need_id, field))
    reads_ctx.late.report()


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
    the order written and joined by the field's type. A failure (a call that fails, or
    a result the field cannot hold) is one ``needs.dynamic_function`` warning, and the
    field holds its placeholder, as a cycle member does: a link or array field its
    written items, any other field its typed empty value.
    """
    needs_schema = schema
    needs_config = config
    var_proxy = needs_config.variant_data_proxy
    # the fields as the need's type declares them
    type_schema = needs_schema.for_type(need["type"])
    try:
        if (field_schema := type_schema.get_any_field(field)) is None:
            raise RuntimeError("does not exist in schema")
        resolved: list[Any] = []
        # the links the link-valued calls compute, and the calls (``needs.derive_dense``)
        called: set[Any] = set()
        calls: set[str] = set()
        items = reads_ctx.pass_.project.items((need.id, field))
        for position, item in enumerate(items):
            if isinstance(item, DeriveCall):
                with (
                    _reads_reported(item.describe(), field, need, reads_ctx) as reads,
                    reads_ctx.late.watch(item, position, need, field, reads),
                ):
                    # imported here, as the common module imports this one
                    from sphinx_needs.functions.common import execute_rule

                    value = execute_rule(
                        app,
                        need,
                        needs,
                        item.rule,
                        field_schema,
                        needs_schema,
                        reads=reads,
                        cache=reads_ctx.pass_.rule_cache,
                    )
                if value is None:
                    # the rule found no value: the field holds its empty value, which
                    # is not a result, so its schema does not check it
                    from sphinx_needs.functions.order import typed_empty

                    # a list (an array's or a link type's) has no items to add
                    if isinstance(empty := typed_empty(field_schema), list):
                        resolved.extend(empty)
                    else:
                        resolved.append(empty)
                    continue
                if not (
                    field_schema.type_check(value)
                    or (
                        field_schema.type == "array"
                        and field_schema.type_check_item(value)
                    )
                ):
                    raise ValueError(
                        f"{item.describe()} value {type(value)} is not of type "
                        f"{field_schema.type!r}"
                    )
                value = _in_field_type(value, field_schema)
                # checked against the field's own declaration, as its rules are: a
                # type's narrower schema is the validation's to check, on its needs
                if (own := needs_schema.global_declaration(field)) is None:
                    raise RuntimeError("does not exist in schema")
                if (
                    refused := _refused_by_schema(
                        value, own, reads_ctx.pass_.rule_cache
                    )
                ) is not None:
                    raise ValueError(
                        f"{item.describe()} value {_shown(value)!r} is refused by the "
                        f"field's schema: {refused}"
                    )
                if isinstance(value, list | tuple):
                    resolved.extend(value)
                else:
                    resolved.append(value)
            elif isinstance(item, DynamicFunctionParsed):
                with _reads_reported(
                    f"dynamic function '{item.name}'", field, need, reads_ctx
                ) as reads:
                    with reads_ctx.late.watch(item, position, need, field, reads):
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
                    if item.name in LINK_CALLS and isinstance(field_schema, LinkSchema):
                        calls.add(item.name)
                        called.update(
                            func_return
                            if isinstance(func_return, list | tuple)
                            else (func_return,)
                        )
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
            need._set_resolved(
                field,
                None
                if not values and field_schema.nullable
                else " ".join(str(el) for el in values),
            )
        elif field_schema.type in {"integer", "number", "boolean"}:
            # TODO(mh) unboxing the list for non-joinable types
            if len(resolved) > 1:
                raise ValueError(
                    f"Field {field!r} of type {field_schema.type!r} cannot have multiple values"
                )
            # the type of the field, not of the result: an integer a call returns
            # is a float in a number field, as an authored value is
            need._set_resolved(field, _in_field_type(resolved[0], field_schema))
        else:
            need._set_resolved(
                field,
                None
                if resolved and not values and field_schema.nullable
                else _in_field_type(values, field_schema),
            )
        if calls:
            reads_ctx.pass_.called_links[(need.id, field)] = (
                len(called),
                frozenset(calls),
            )
    except Exception as err:
        log_warning(
            logger,
            f"Error while resolving dynamic values for field {field!r}, of need {need['id']!r}: {err}",
            "dynamic_function",
            location=(need["docname"], need["lineno"]) if need["docname"] else None,
        )
        # it imports this module
        from sphinx_needs.functions.order import placeholder

        need._set_resolved(field, placeholder(need, field, type_schema))


def _in_field_type(value: Any, field_schema: FieldShape) -> Any:
    """A computed value in the type of the field holding it.

    An integer in a ``number`` field (a rule's ``count``, a ``sum`` or ``copy`` of an
    ``integer`` field, or an integer a ``[[…]]`` returns, or the items of either in an
    array of numbers) is stored as a float, as an authored value of the field is, so
    that it is exported and hashed as one. A boolean is not a number here.
    """

    def number(item: Any) -> Any:
        if isinstance(item, int) and not isinstance(item, bool):
            return float(item)
        return item

    if field_schema.type == "number":
        return number(value)
    if field_schema.type == "array" and field_schema.item_type == "number":
        if isinstance(value, list | tuple):
            return [number(item) for item in value]
        return number(value)
    return value


def _shown(value: Any) -> Any:
    """A rule's result as a message shows it: a link as its id."""
    if isinstance(value, list | tuple):
        return [_shown(item) for item in value]
    return value.to_filter_string() if isinstance(value, NeedLink) else value


def _refused_by_schema(
    value: Any, field_schema: FieldSchema | LinkSchema, cache: dict[Any, Any]
) -> str | None:
    """Why the field's own ``schema`` refuses a rule's result, if it does.

    The result is checked as schema validation checks the field's value (a link list
    as its ids); ``None``, no value, is not checked. *field_schema* is the field's
    global declaration, never a need type's (a type's narrower schema is the
    validation's to check), so the field's validator is compiled once per pass.
    """
    if value is None:
        return None
    key = ("field schema", field_schema.name)
    if (validator := cache.get(key)) is None:
        # imported here, as the schema module imports the data module, which this
        # module's callers import
        from sphinx_needs.schema.core import compile_validator

        validator = cache[key] = compile_validator(
            {"properties": {field_schema.name: field_schema.schema}}
        )
    error = next(
        iter(
            validator.compiled.iter_errors(instance={field_schema.name: _shown(value)})
        ),
        None,
    )
    return None if error is None else error.message


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
        try:
            holds = bool(eval(expr, context.copy()))
        except Exception as error:
            # a condition has no facets: ``source`` undefined there, or a facet read
            # failing on a field named ``source``, says so
            if not unavailable(error, expr):
                raise
            raise ValueError(explained(error, "a variant condition", expr)) from None
        if holds:
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
