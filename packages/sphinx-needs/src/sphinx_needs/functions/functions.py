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
from typing import Any, Protocol, TypeAlias, TypeVar

from docutils import nodes
from sphinx.application import Sphinx
from sphinx.environment import BuildEnvironment

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import NeedsMutable, SphinxNeedsData
from sphinx_needs.debug import measure_time_func
from sphinx_needs.exceptions import FunctionParsingException
from sphinx_needs.logging import get_logger, log_warning
from sphinx_needs.need_item import NeedItem, NeedLink, NeedPartItem
from sphinx_needs.nodes import Need
from sphinx_needs.roles.need_func import NeedFunc
from sphinx_needs.variant_data import (
    VariantDataError,
    VariantDataParsed,
    lookup_variant_data,
)
from sphinx_needs.variants import VariantFunctionParsed
from sphinx_needs.views import NeedsView

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
    if need is not None:
        try:
            df = df.apply_need(need)
        except Exception as err:
            raise RuntimeError(
                f"Error while applying need to function {df.name!r}: {err}"
            ) from err

    needs_config = NeedsSphinxConfig(app.config)

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


# -- reads of a value computed in the same pass ------------------------------------
#
# ``resolve_functions`` writes each result into its need as it goes, need by need in
# the order the needs reached the environment, so a call or a variant condition that
# reads a field another one computes sees the computed value or the unresolved one
# depending on that order (document names, the documents the last build re-read,
# ``-j``). Each such read is reported as ``needs.derive_unresolved``. The pass opens an
# ``UnresolvedReads`` record for each call and each ``<<…>>`` variant: a built-in
# marked ``records_reads`` receives it as its ``reads`` keyword and notes what it
# reads, ``_get_variant`` notes the names the variant's evaluated conditions read, and
# the pass reports the record once the call is over. Nothing else is handed a record:
# an ``ndf`` role or a ``:style_row:`` runs after the pass, and a user's own function,
# which the pass calls without one, has none to give a built-in it calls; such a
# built-in gets ``reads=None`` and notes nothing.

#: how many needs one read names; the rest are counted
_UNRESOLVED_NAMED = 3


class UnresolvedReads:
    """The reads of computed values made by ONE call or ``<<…>>`` variant.

    ``resolve_functions`` creates one for each call and each ``<<…>>`` variant (shared
    by all the conditions it evaluates), hands it to the dynamic function as its
    ``reads`` keyword when the function is marked :func:`records_reads`, and reports
    what it holds as ``needs.derive_unresolved`` once the call is over. No other caller
    creates one: after the pass every value read is final, and a user's function is
    opaque (its reads, through a built-in or otherwise, are not reported).

    Kept by the name read, in the order first read, each need named once per name.
    """

    __slots__ = ("_reads",)

    def __init__(self) -> None:
        self._reads: dict[str, dict[str, None]] = {}

    def note(self, name: str, need_id: str) -> None:
        """Record that ``name`` was read on the need ``need_id``, unconditionally.

        :meth:`note_read` is the form that checks the field is computed in the pass.
        """
        self._reads.setdefault(name, {})[need_id] = None

    def note_read(self, need: NeedItem | NeedPartItem, name: str) -> None:
        """Note that the field or link ``name`` of ``need`` was read.

        It is recorded only when the field carries a dynamic value of its own
        (:meth:`.NeedItem.carries_dynamic_value`), so is computed in the same pass:
        whether the pass has computed it yet depends on the order the needs are
        resolved in, and the warning must not.

        :param need: The need read: the call's own need or another one.
        :param name: The field or link read.
        """
        # the pass hands its functions whole needs, so only a need is noted; a need
        # part is admitted by the types (a ``filter``'s result is typed so), not noted
        if isinstance(need, NeedItem) and need.carries_dynamic_value(name):
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


def _derive_unresolved_message(
    what: str, option: str, reads: Sequence[tuple[str, Sequence[str]]]
) -> str:
    """Return the ``needs.derive_unresolved`` message for the reads of one call.

    ubCode's words up to the reads, then a statement that holds whether or not the
    value read had been computed yet. Each name is said once, with the one need it was
    read on, or with how many and the first three; several names are joined
    ``a, b and c``.

    :param what: The reader: ``dynamic function 'copy'``, or ``variant condition``.
    :param option: The field the reader computes.
    :param reads: Each name read, with the ids of the needs it was read on, in order.
    :raises ValueError: If there is no read.
    """
    if not reads:
        raise ValueError("no read to report")
    parts: list[str] = []
    for name, ids in reads:
        if len(ids) == 1:
            parts.append(f"'{name}' on need '{ids[0]}'")
            continue
        named = ", ".join(ids[:_UNRESOLVED_NAMED])
        if len(ids) > _UNRESOLVED_NAMED:
            named += f" and {len(ids) - _UNRESOLVED_NAMED} more"
        parts.append(f"'{name}' on {len(ids)} needs ({named})")
    read = parts[0] if len(parts) == 1 else f"{', '.join(parts[:-1])} and {parts[-1]}"
    carries = "carries" if len(reads) == 1 and len(reads[0][1]) == 1 else "carry"
    return (
        f"{what} for option '{option}' read {read}, which {carries} a dynamic function "
        "or variant computed in the same pass: the value read depends on the order the "
        "needs are resolved in"
    )


@contextmanager
def _reads_reported(
    what: str, option: str, need: NeedItem
) -> Iterator[UnresolvedReads]:
    """Open the record of one call or ``<<…>>`` variant, and report its reads after it.

    They are reported whatever the outcome, so a call that fails because of a value it
    read still says what it read. The warning is located at the reading need.

    :param what: The reader, as the message names it.
    :param option: The field the reader computes.
    :param need: The need the reader belongs to.
    """
    reads = UnresolvedReads()
    try:
        yield reads
    finally:
        if noted := reads.reads():
            log_warning(
                logger,
                _derive_unresolved_message(what, option, noted),
                "derive_unresolved",
                location=(need["docname"], need["lineno"]) if need["docname"] else None,
            )


def resolve_functions(
    app: Sphinx,
    needs: NeedsMutable,
    needs_config: NeedsSphinxConfig,
) -> None:
    """Resolve all dynamic/variant functions in all needs.

    A read, by a built-in function or a variant condition, of a field that is itself
    computed in this pass is reported as ``needs.derive_unresolved``, once per call:
    each call and each ``<<…>>`` variant gets its own :class:`UnresolvedReads`, which
    is handed to the built-ins marked :func:`records_reads` and to the variant's
    conditions.
    """
    needs_schema = SphinxNeedsData(app.env).get_schema()
    var_proxy = needs_config.variant_data_proxy
    for need in needs.values():
        if not need.has_dynamic_fields:
            continue
        for field in list(need._dynamic_fields):
            try:
                if (field_schema := needs_schema.get_any_field(field)) is None:
                    raise RuntimeError("does not exist in schema")
                resolved: list[Any] = []
                for item in need._dynamic_fields[field].value:
                    if isinstance(item, DynamicFunctionParsed):
                        with _reads_reported(
                            f"dynamic function '{item.name}'", field, need
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
                        with _reads_reported("variant condition", field, need) as reads:
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

                if field_schema.type == "string":
                    need[field] = " ".join(str(el) for el in resolved)
                elif field_schema.type in {"integer", "number", "boolean"}:
                    # TODO(mh) unboxing the list for non-joinable types
                    if len(resolved) > 1:
                        raise ValueError(
                            f"Field {field!r} of type {field_schema.type!r} cannot have multiple values"
                        )
                    need[field] = resolved[0]
                else:
                    need[field] = resolved
            except Exception as err:
                log_warning(
                    logger,
                    f"Error while resolving dynamic values for field {field!r}, of need {need['id']!r}: {err}",
                    "dynamic_function",
                    location=(need["docname"], need["lineno"])
                    if need["docname"]
                    else None,
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
