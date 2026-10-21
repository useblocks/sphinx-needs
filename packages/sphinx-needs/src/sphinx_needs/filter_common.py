"""
filter_base is used to provide common filter functionality for directives
like needtable, needlist and needflow.
"""

from __future__ import annotations

import ast
import json
import math
import re
from collections.abc import Callable, Iterable, Mapping
from functools import lru_cache
from pathlib import Path
from timeit import default_timer as timer
from types import CodeType
from typing import Any, Literal, TypedDict, TypeVar, overload

from docutils import nodes
from docutils.parsers.rst import directives
from docutils.statemachine import StringList
from sphinx.application import Sphinx
from sphinx.util.docutils import SphinxDirective

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import NeedsFilteredBaseType, NeedsMutable
from sphinx_needs.debug import measure_time, measure_time_func
from sphinx_needs.exceptions import NeedsInvalidFilter
from sphinx_needs.logging import log_warning
from sphinx_needs.need_item import NeedItem, NeedPartItem
from sphinx_needs.needs_schema import AllowedTypes
from sphinx_needs.ubquery import ORIGIN_KEY, CompiledFilter, compile_portable
from sphinx_needs.utils import check_and_get_external_filter_func
from sphinx_needs.utils import logger as log
from sphinx_needs.views import NeedsAndPartsListView, NeedsView

_NeedOrPartT = TypeVar("_NeedOrPartT", bound=NeedItem | NeedPartItem)
"""A need or a need part: what a filter selects from, and so what it returns."""


class FilterAttributesType(TypedDict):
    status: list[str]
    tags: list[str]
    types: list[str]
    filter: str | None
    """``:filter:`` option value, None if the option was not given."""
    sort_by: str | None
    """``:sort_by:`` option value, None if the option was not given."""
    filter_code: StringList
    """The directive's content: filter code, empty if it has none."""
    filter_func: str | None
    filter_warning: str | None
    """If set, the filter is exported with this ID in the needs.json file."""


class FilterBase(SphinxDirective):
    has_content = True

    base_option_spec: dict[str, Callable[[str], Any]] = {
        "status": directives.unchanged_required,
        "tags": directives.unchanged_required,
        "types": directives.unchanged_required,
        "filter": directives.unchanged_required,
        "filter-func": directives.unchanged_required,
        "sort_by": directives.unchanged,
        "export_id": directives.unchanged,
        "filter_warning": directives.unchanged,
    }

    def collect_filter_attributes(self) -> FilterAttributesType:
        _tags = str(self.options.get("tags", ""))
        tags = (
            [tag.strip() for tag in re.split(";|,", _tags) if len(tag) > 0]
            if _tags
            else []
        )

        status_option = self.options.get("status")
        status = (
            [stat.strip() for stat in re.split(";|,", str(status_option))]
            if status_option
            else []
        )

        types = self.options.get("types", [])
        if isinstance(types, str):
            types = [typ.strip() for typ in re.split(";|,", types)]

        if "export_id" in self.options:
            log_warning(
                log,
                "The 'export_id' option is deprecated, instead use the `needs_debug_filters` configuration.",
                "deprecated",
                location=self.get_location(),
            )

        # Add the need and all needed information
        collected_filter_options: FilterAttributesType = {
            "status": status,
            "tags": tags,
            "types": types,
            "filter": self.options.get("filter"),
            "sort_by": self.options.get("sort_by"),
            "filter_code": self.content,
            "filter_func": self.options.get("filter-func"),
            "filter_warning": self.options.get("filter_warning"),
        }
        return collected_filter_options


def sort_key(value: object, /, *, ignore_case: bool) -> tuple[Any, ...]:
    """The key a need is sorted by, from its value of the sort field.

    An unset value (``None``) comes first, whatever the field's type, as an empty
    string always has. The values are then grouped in bands, so that two values never
    meet in a comparison Python refuses: booleans, then numbers, then text. A list is
    compared as its items' text joined with ``", "``, and any other value as its text.
    A NaN comes after the other numbers. Callers break ties by the need's id (#2253).

    :param value: The need's value of the sort field.
    :param ignore_case: Compare text lower-cased, so that ``"Z"`` does not come before
        ``"a"`` (``needtable``'s ``:sort:``; ``:sort_by:`` compares it as it is).
    :return: A key every other value's key compares with.
    """
    if value is None:
        return (0,)
    if isinstance(value, bool):
        return (1, value)
    if isinstance(value, int | float):
        # a NaN compares neither below nor above anything, so it is placed on its own
        return (2, 1, 0) if math.isnan(value) else (2, 0, value)
    if isinstance(value, list | tuple):
        value = ", ".join(str(item) for item in value)
    text = str(value)
    return (3, text.lower() if ignore_case else text)


def process_filters(
    app: Sphinx,
    needs_view: NeedsView,
    filter_data: NeedsFilteredBaseType,
    origin: str,
    location: nodes.Element,
    include_external: bool = True,
) -> list[NeedItem | NeedPartItem]:
    """
    Filters all needs with given configuration.
    Used by needlist, needtable and needflow.

    :param app: Sphinx application object
    :param filter_data: Filter configuration
    :param origin: Origin of the request (e.g. needlist, needtable, needflow)
    :param location: Origin node of the request
    :param include_external: Boolean, which decides to include external needs or not

    :return: list of needs, which passed the filters
    """
    start = timer()
    needs_config = NeedsSphinxConfig(app.config)

    # filter string to record (will be joined by 'and')
    full_filter: list[str] = []

    # check if include external needs
    if not include_external:
        full_filter.append("is_external == False")
        needs_view = needs_view.filter_is_external(False)

    # Check if external filter code is defined
    try:
        ff_result = check_and_get_external_filter_func(filter_data.get("filter_func"))
    except NeedsInvalidFilter as e:
        log_warning(
            log,
            str(e),
            "filter_func",
            location=location,
        )
        return []

    filter_code = (
        "\n".join(filter_data["filter_code"]) if filter_data["filter_code"] else None
    )

    found_needs: list[NeedItem | NeedPartItem] = []
    # which tier answered the filter, and why one reached eval: the debug report's
    tier: tuple[_FilterTier, str | None]

    if (not filter_code or filter_code.isspace()) and not ff_result:
        # TODO these may not be correct for parts
        filtered_needs = needs_view
        if filter_data["status"]:
            full_filter.append(f"status in {filter_data['status']!r}")
            filtered_needs = filtered_needs.filter_statuses(filter_data["status"])
        if filter_data["tags"]:
            full_filter.append(
                " or ".join(f"{tag!r} in tags" for tag in filter_data["tags"])
            )
            filtered_needs = filtered_needs.filter_has_tag(filter_data["tags"])
        if filter_data["types"]:
            full_filter.append(
                f"type in {filter_data['types']!r} or type_name in {filter_data['types']!r}"
            )
            filtered_needs = filtered_needs.filter_types(
                filter_data["types"], or_type_names=True
            )
        if filter_data["filter"]:
            full_filter.append(filter_data["filter"])

        # Get need by filter string
        found_needs = filter_needs_parts(
            filtered_needs.to_list_with_parts(),
            needs_config,
            filter_data["filter"],
            location=location,
            origin_docname=filter_data["docname"],
        )
        tier = (
            _filter_tier(filter_data["filter"])
            if needs_config.debug_filters
            else ("index", None)
        )
    else:
        # The filter results may be dirty, as it may continue manipulated needs.
        found_dirty_needs: list[NeedItem | NeedPartItem] = []

        if filter_code:  # code from content
            full_filter.append(filter_code)
            # the namespace the filter code runs in: it is the user's code that
            # leaves the matches under `results`, so its values are not ours to type
            context: dict[str, Any] = {
                "needs": needs_view.to_list_with_parts(),
                "results": [],
            }
            exec(filter_code, context)
            found_dirty_needs = context["results"]
            tier = ("eval", "filter-code")
        elif ff_result:  # code from external file
            full_filter.append(ff_result.sig)
            args = []
            if ff_result.args:
                args = ff_result.args.split(",")
            args_context = {f"arg{index + 1}": arg for index, arg in enumerate(args)}

            # Decorate function to allow time measurments
            filter_func = measure_time_func(
                ff_result.func, category="filter_func", source="user"
            )
            filter_func(
                needs=needs_view.to_list_with_parts(),
                results=found_dirty_needs,
                **args_context,
            )
            tier = ("eval", "filter-func")
        else:
            log_warning(
                log, "Something went wrong running filter", "filter", location=location
            )
            return []

        # Check if config allow unsafe filters
        if needs_config.allow_unsafe_filters:
            found_needs = found_dirty_needs
        else:
            # Just take the ids from search result and use the related, but original need
            found_need_ids = [x["id_complete"] for x in found_dirty_needs]
            for need in needs_view.to_list_with_parts():
                if need["id_complete"] in found_need_ids:
                    found_needs.append(need)

    if sort_by := filter_data["sort_by"]:
        try:
            found_needs = sorted(
                found_needs,
                # equal values are ordered by id: the needs' own order changes
                # between a fresh and an incremental build
                key=lambda node: (
                    sort_key(node[sort_by], ignore_case=False),
                    node["id_complete"],
                ),
            )
        except KeyError as e:
            log_warning(
                log,
                f"Sorting parameter {sort_by} not valid: Error: {e}",
                "filter",
                location=location,
            )
            return []

    duration = timer() - start

    if (
        needs_config.filter_max_time is not None
        and duration > needs_config.filter_max_time
    ):
        log_warning(
            log,
            f"Filtering took {duration:.3f}s, which is longer than the configured maximum of {needs_config.filter_max_time}s.",
            "filter",
            location=location,
        )

    if needs_config.debug_filters and full_filter:
        # Store basic filter configuration and result global list.
        # Needed mainly for exporting the result to needs.json (if builder "needs" is used).
        record: dict[str, Any] = {
            "origin": origin,
            "source": str(location.source) if location.source else None,
            "line": location.line,
            "filter": full_filter[0]
            if len(full_filter) == 1
            else " and ".join(f"({f})" for f in full_filter),
            "needs_count": len(found_needs),
            "runtime": duration,
            "tier": tier[0],
        }
        if tier[0] == "eval":
            record["fallback_reason"] = tier[1]
        json_line = json.dumps(record)
        with Path(str(app.outdir), "debug_filters.jsonl").open("a") as f:
            f.write(json_line + "\n")

    return found_needs


_FilterTier = Literal["index", "fast", "eval", "refused"]
"""The tier of filter evaluation that answers a filter string: the index path, the
fast path of the portable grammar (:mod:`sphinx_needs.ubquery`), or Python's ``eval``;
or ``"refused"`` for a constant, which no tier answers (:func:`_is_constant_filter`)."""


@lru_cache(maxsize=256)
def _is_constant_filter(filter_string: str) -> bool:
    """Whether *filter_string* is a constant, which every tier refuses.

    A filter is read for its truth, need by need, and a constant has the same truth on
    every need, so it says nothing about one: a literal (``"x"``, ``0``, ``1.5``,
    ``None``, ``b"x"``, ``...``), a number with one sign (``-5``, ``+5``), a tuple,
    list, set or dict display with no unpacking, whatever it holds (``[1]``, ``{1}``,
    ``{}``, ``("x",)``, and so the trailing-comma typo ``status == "open",``), a
    generator expression (``(t for t in tags)``, a generator object, true whatever it
    would yield), or an f-string with no placeholder (``f"x"``), parenthesised or not.
    Such a filter is reported, once, before any tier runs, and selects nothing.
    ``True`` and ``False`` are the exception: they are the spelling of "every need" and
    "no need". A constant inside a larger filter (``True and owner``) is an operand like
    any other, and so is a constant expression (``-True``, ``--5``, ``not 1``,
    ``1 == 1``); a display that unpacks (``[*tags]``, ``{**x}``), a list, set or dict
    comprehension and an f-string with a placeholder depend on the need, and are read
    by their truth, as any filter is.

    Leading spaces and tabs are read past, as Python's ``eval`` reads past them.
    It is decided by the string alone, once per string: the engine's tiers ask it on
    every call, :func:`filter_single_need` need by need.
    """
    try:
        node = ast.parse(filter_string.lstrip(" \t"), mode="eval").body
    except (SyntaxError, ValueError):
        return False
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub | ast.UAdd):
        # a signed number; a signed boolean, or a second sign, is arithmetic
        node = node.operand
        return (
            isinstance(node, ast.Constant)
            and isinstance(node.value, int | float | complex)
            and not isinstance(node.value, bool)
        )
    if isinstance(node, ast.Tuple | ast.List | ast.Set):
        # a display holds as many items on every need, unless it unpacks one
        return not any(isinstance(item, ast.Starred) for item in node.elts)
    if isinstance(node, ast.Dict):
        # a None key is a ** unpack
        return None not in node.keys
    if isinstance(node, ast.GeneratorExp):
        # a generator object is true, whatever it would yield
        return True
    if isinstance(node, ast.JoinedStr):
        # an f-string with no placeholder is a string
        return not any(isinstance(value, ast.FormattedValue) for value in node.values)
    return isinstance(node, ast.Constant) and not isinstance(node.value, bool)


def _constant_filter_message(filter_string: str, prefix: str = "Filter") -> str:
    """The report of a constant filter (see :func:`_is_constant_filter`)."""
    return (
        f"{prefix} {filter_string!r} not valid. Error: it is a constant, "
        "which says nothing about a need, so it selects none."
    )


def _report_constant_filter(
    filter_string: str,
    location: tuple[str, int | None] | nodes.Node | None,
    append_warning: str,
) -> None:
    """Report a constant filter as one ``needs.filter`` warning."""
    if append_warning:
        append_warning = f" {append_warning}"
    log_warning(
        log,
        f"{_constant_filter_message(filter_string)}{append_warning}",
        "filter",
        location=location,
    )


def _filter_tier(filter_string: str | None) -> tuple[_FilterTier, str | None]:
    """The tier that answers *filter_string* over a view of needs, as
    :func:`filter_needs_view` and :func:`filter_needs_parts` take it, and, for ``eval``,
    the construct that kept the string out of the portable grammar.

    The first two tiers decide by the string alone, never by the needs, so this asks
    each the question it asks itself: the index path whether it answers the whole
    string (its own analysis, over an empty view), the fast path whether the string
    compiles. No filter at all is answered by the view's indexes.

    :return: The tier, and the reason for ``eval`` (None for the others).
    """
    if not filter_string:
        return "index", None
    if _is_constant_filter(filter_string):
        return "refused", None
    try:
        body = ast.parse(filter_string).body
    except Exception:
        body = []
    if len(body) == 1 and isinstance((expr := body[0]), ast.Expr):
        _, requires_eval = _analyze_and_apply_expr(
            NeedsView._from_needs({}), expr.value
        )
        if not requires_eval:
            return "index", None
    compiled = compile_portable(filter_string)
    if compiled.predicate is not None:
        return "fast", None
    return "eval", compiled.rejection


def filter_scope_ids(
    needs_view: NeedsView,
    config: NeedsSphinxConfig,
    /,
    *,
    status: list[str],
    tags: list[str],
    types: list[str],
    filter: str | None,
    location: nodes.Element,
    origin_docname: str,
) -> frozenset[str] | None:
    """Resolve the selection options of a chart directive into a scope of needs.

    ``needpie`` and ``needbar`` count one filter per content line or grid cell,
    rather than the single filter the need-listing directives take.
    The four selection options therefore do not select what such a chart *shows*;
    they select the needs (and parts) it counts over, once for the whole chart.
    Each content line is then counted as ``line-result`` intersected with this scope,
    so a line can only ever count needs that are in the scope,
    and a literal numeric line is not affected at all.

    The scope is the same set of needs that the same four options select on a
    need-listing directive such as ``needlist``: each option narrows the view in
    turn, exactly as ``process_filters`` narrows it there, each one matching
    any-of its own values; ``:types:`` matches the directive name or the
    human-readable type title; and ``:filter:`` is evaluated last, over needs
    *and* parts. Parts follow their need for ``:status:``, ``:tags:`` and
    ``:types:``, exactly as they do there -- including that the ``id`` fast path
    admits sibling parts once the view has been narrowed, which is inherited
    behaviour rather than a property of the scope.

    :param needs_view: all needs of the project, unfiltered.
    :param config: used to evaluate the ``filter`` expression.
    :param status: the ``:status:`` option values, empty if the option was not given.
    :param tags: the ``:tags:`` option values, empty if the option was not given.
    :param types: the ``:types:`` option values, empty if the option was not given.
    :param filter: the ``:filter:`` option value, None if the option was not given.
    :param location: the chart node, used to locate warnings of an invalid ``filter``.
    :param origin_docname: the document the chart is written on,
        so that ``c.this_doc()`` can be used in ``filter``.

    :return: the ``id_complete`` of every need and part in the scope,
        or None if no selection option was given.
        None means "no scope", which is not the same as an empty scope:
        an unscoped chart counts its lines over the whole project.
    """
    if not (status or tags or types or filter):
        # no selection option given: the chart counts over the whole project,
        # exactly as it did before these options existed
        return None

    # the same narrowing calls, in the same order, that process_filters applies
    # for a need-listing directive, so that the scope of a chart and the result
    # of a needlist with the same options hold the same needs
    filtered_needs = needs_view
    if status:
        filtered_needs = filtered_needs.filter_statuses(status)
    if tags:
        filtered_needs = filtered_needs.filter_has_tag(tags)
    if types:
        filtered_needs = filtered_needs.filter_types(types, or_type_names=True)

    parts = filtered_needs.to_list_with_parts()
    members: Iterable[NeedItem | NeedPartItem] = (
        filter_needs_parts(
            parts,
            config,
            filter,
            location=location,
            origin_docname=origin_docname,
        )
        if filter
        else parts
    )

    return frozenset(need["id_complete"] for need in members)


def resolve_max_items(max_items: int | None, config: NeedsSphinxConfig) -> int:
    """Resolve the effective item limit of a view directive.

    Note that only an unset option falls back to the configuration,
    so an explicit ``:max_items: 0`` means "no limit" whatever the configuration says.

    :param max_items: the directive option value, or None if the option was not given.
    :param config: used for the ``needs_views_max_items`` fallback.

    :return: the effective limit, where zero or less means no limit.
    """
    return config.views_max_items if max_items is None else max_items


def apply_max_items(
    needs: list[NeedItem | NeedPartItem],
    max_items: int | None,
    config: NeedsSphinxConfig,
) -> tuple[list[NeedItem | NeedPartItem], int]:
    """Apply the ``max_items`` cap to an already filtered and sorted list of needs.

    :param needs: the filtered, sorted needs.
    :param max_items: the directive option value, or None if the option was not given.
    :param config: used for the ``needs_views_max_items`` fallback.

    :return: the (possibly truncated) needs, and the total before any truncation.
    """
    total = len(needs)
    limit = resolve_max_items(max_items, config)
    if limit <= 0 or total <= limit:
        return needs, total
    return needs[:limit], total


def filter_needs_mutable(
    needs: NeedsMutable,
    config: NeedsSphinxConfig,
    filter_string: str | None = "",
    current_need: NeedItem | None = None,
    *,
    location: tuple[str, int | None] | nodes.Node | None = None,
    append_warning: str = "",
    origin_docname: str | None = None,
) -> list[NeedItem]:
    return filter_needs(
        needs.values(),
        config,
        filter_string,
        current_need,
        location=location,
        append_warning=append_warning,
        origin_docname=origin_docname,
    )


@overload
def _analyze_and_apply_expr(
    needs: NeedsView, expr: ast.expr
) -> tuple[NeedsView, bool]: ...


@overload
def _analyze_and_apply_expr(
    needs: NeedsAndPartsListView, expr: ast.expr
) -> tuple[NeedsAndPartsListView, bool]: ...


def _analyze_and_apply_expr(
    needs: NeedsView | NeedsAndPartsListView, expr: ast.expr
) -> tuple[NeedsView | NeedsAndPartsListView, bool]:
    """Analyze the expr for known filter patterns,
    and apply them to the given needs.

    :returns: the needs (potentially filtered),
        and a boolean denoting if it still requires python eval filtering
    """
    if isinstance(expr, ast.Constant):
        if isinstance(expr.value, str | bool):
            # True / False, or a string beside `and` ("value" and ...), read by its
            # truth; a string alone is refused before this (_is_constant_filter)
            return needs if expr.value else needs.filter_ids([]), False

    elif isinstance(expr, ast.Name):
        # x
        if expr.id == "is_external":
            return needs.filter_is_external(True), False

    elif isinstance(expr, ast.Compare):
        # <expr1> <comp> <expr2>
        if len(expr.ops) == 1 and isinstance(expr.ops[0], ast.Eq):
            # x == y
            if (
                isinstance(expr.left, ast.Name)
                and len(expr.comparators) == 1
                and isinstance(expr.comparators[0], ast.Constant)
            ):
                # x == "value"
                field = expr.left.id
                value = expr.comparators[0].value
            elif (
                isinstance(expr.left, ast.Constant)
                and len(expr.comparators) == 1
                and isinstance(expr.comparators[0], ast.Name)
            ):
                # "value" == x
                field = expr.comparators[0].id
                value = expr.left.value
            else:
                return needs, True

            if field == "id":
                # id == value; an id is a string, so no other constant matches
                ids = [value] if isinstance(value, str) else []
                return needs.filter_ids(ids), False
            elif field == "type":
                # type == value; a type is a string, so no other constant matches
                types = [value] if isinstance(value, str) else []
                return needs.filter_types(types), False
            elif field == "status":
                # status == value; a status is a string or None
                statuses = [value] if value is None or isinstance(value, str) else []
                return needs.filter_statuses(statuses), False
            elif field == "is_external":
                # is_external == value; as in Python, a constant equal to a bool
                # (True, 1, 0.0) selects as that bool, and any other matches nothing
                if value in (True, False):
                    return needs.filter_is_external(bool(value)), False
                return needs.filter_ids([]), False

        elif len(expr.ops) == 1 and isinstance(expr.ops[0], ast.In):
            # <expr1> in <expr2>
            if (
                isinstance(expr.left, ast.Name)
                and len(expr.comparators) == 1
                and isinstance(expr.comparators[0], ast.List | ast.Tuple | ast.Set)
                and all(
                    isinstance(elt, ast.Constant) for elt in expr.comparators[0].elts
                )
            ):
                constants = [
                    elt.value
                    for elt in expr.comparators[0].elts
                    if isinstance(elt, ast.Constant)
                ]
                values = [value for value in constants if isinstance(value, str)]
                if expr.left.id == "id":
                    # id in ["a", "b", ...]
                    return needs.filter_ids(values), False
                if expr.left.id == "status":
                    # status in ["a", "b", ...]; a status is a string or None
                    statuses = [
                        value
                        for value in constants
                        if value is None or isinstance(value, str)
                    ]
                    return needs.filter_statuses(statuses), False
                elif expr.left.id == "type":
                    # type in ["a", "b", ...]
                    return needs.filter_types(values), False
            elif (
                isinstance(expr.left, ast.Constant)
                and len(expr.comparators) == 1
                and isinstance(expr.comparators[0], ast.Name)
                and expr.comparators[0].id == "tags"
                and isinstance(expr.left.value, str)
            ):
                # "value" in tags
                return needs.filter_has_tag([expr.left.value]), False

    elif isinstance((and_op := expr), ast.BoolOp) and isinstance(and_op.op, ast.And):
        # x and y and ...
        requires_eval = False
        for operand in and_op.values:
            needs, _requires_eval = _analyze_and_apply_expr(needs, operand)
            requires_eval |= _requires_eval
        return needs, requires_eval

    return needs, True


def filter_needs_view(
    needs: NeedsView,
    config: NeedsSphinxConfig,
    filter_string: str | None = "",
    current_need: NeedItem | None = None,
    *,
    location: tuple[str, int | None] | nodes.Node | None = None,
    append_warning: str = "",
    strict_eval: bool = False,
    origin_docname: str | None = None,
) -> list[NeedItem]:
    if not filter_string:
        return list(needs.values())
    if _is_constant_filter(filter_string):
        _report_constant_filter(filter_string, location, append_warning)
        return []

    try:
        body = ast.parse(filter_string).body
    except Exception:
        pass  # warning already emitted in filter_needs
    else:
        if len(body) == 1 and isinstance((expr := body[0]), ast.Expr):
            needs, requires_eval = _analyze_and_apply_expr(needs, expr.value)
            if not requires_eval:
                return list(needs.values())

    if strict_eval:
        # this is mainly used for testing purposes, to check if expression analysis is working
        raise RuntimeError(
            f"Strict eval mode, but no simple filter found: {filter_string!r}"
        )

    return filter_needs(
        needs.values(),
        config,
        filter_string,
        current_need,
        location=location,
        append_warning=append_warning,
        origin_docname=origin_docname,
    )


def filter_needs_parts(
    needs: NeedsAndPartsListView,
    config: NeedsSphinxConfig,
    filter_string: str | None = "",
    current_need: NeedItem | None = None,
    *,
    location: tuple[str, int | None] | nodes.Node | None = None,
    append_warning: str = "",
    strict_eval: bool = False,
    origin_docname: str | None = None,
) -> list[NeedItem | NeedPartItem]:
    if not filter_string:
        return list(needs)
    if _is_constant_filter(filter_string):
        _report_constant_filter(filter_string, location, append_warning)
        return []

    try:
        body = ast.parse(filter_string).body
    except Exception:
        pass  # warning already emitted in filter_needs
    else:
        if len(body) == 1 and isinstance((expr := body[0]), ast.Expr):
            needs, requires_eval = _analyze_and_apply_expr(needs, expr.value)
            if not requires_eval:
                return list(needs)

    if strict_eval:
        # this is mainly used for testing purposes, to check if expression analysis is working
        raise RuntimeError(
            f"Strict eval mode, but no simple filter found: {filter_string!r}"
        )

    return filter_needs_and_parts(
        needs,
        config,
        filter_string,
        current_need,
        location=location,
        append_warning=append_warning,
        origin_docname=origin_docname,
    )


@measure_time("filtering")
def filter_needs(
    needs: Iterable[NeedItem],
    config: NeedsSphinxConfig,
    filter_string: str | None = "",
    current_need: NeedItem | None = None,
    *,
    location: tuple[str, int | None] | nodes.Node | None = None,
    append_warning: str = "",
    origin_docname: str | None = None,
) -> list[NeedItem]:
    return filter_needs_and_parts(
        needs,
        config,
        filter_string=filter_string,
        current_need=current_need,
        location=location,
        append_warning=append_warning,
        origin_docname=origin_docname,
    )


@measure_time("filtering")
def filter_needs_and_parts(
    needs: Iterable[_NeedOrPartT],
    config: NeedsSphinxConfig,
    filter_string: str | None = "",
    current_need: NeedItem | NeedPartItem | None = None,
    *,
    location: tuple[str, int | None] | nodes.Node | None = None,
    append_warning: str = "",
    origin_docname: str | None = None,
) -> list[_NeedOrPartT]:
    """
    Filters given needs based on a given filter string.
    Returns all needs, which pass the given filter.

    :param needs: list of needs, which shall be filtered;
        the result holds items of it, so needs alone give needs alone
    :param config: NeedsSphinxConfig object
    :param filter_string: strings, which gets evaluated against each need
    :param current_need: current need, which uses the filter.
    :param location: source location for error reporting (docname, line number)
    :param append_warning: additional text to append to any failed filter warning

    :return: list of found needs
    """
    if not filter_string:
        return list(needs)
    if _is_constant_filter(filter_string):
        _report_constant_filter(filter_string, location, append_warning)
        return []

    # === Fast path: try compiled predicate to avoid eval() entirely ===
    compiled = compile_portable(filter_string)
    simple_pred = compiled.predicate

    if simple_pred is not None:
        fallback = _fast_path_context(
            config.filter_data, config.variant_data_proxy, compiled, origin_docname
        )
        found_needs: list[_NeedOrPartT] = []
        error_reported = False
        for filter_need in needs:
            try:
                # read for its truth: a value's own method may give no boolean
                if simple_pred(filter_need, fallback):
                    found_needs.append(filter_need)
            except Exception as e:
                # whatever a value's method raises, as the eval loop below: the need
                # is excluded and the filter reported once, and the build goes on
                if not error_reported:
                    if append_warning:
                        append_warning = f" {append_warning}"
                    log_warning(
                        log,
                        f"Filter {filter_string!r} not valid. Error: {e}.{append_warning}",
                        "filter",
                        location=location,
                    )
                    error_reported = True
        return found_needs

    # === Slow path: fall back to eval() per item ===
    found_needs_slow: list[_NeedOrPartT] = []

    # https://docs.python.org/3/library/functions.html?highlight=compile#compile
    filter_compiled = compile(filter_string, "<string>", "eval")
    error_reported = False
    for filter_need in needs:
        try:
            if filter_single_need(
                filter_need,
                config,
                filter_string,
                needs,
                current_need,
                filter_compiled=filter_compiled,
                origin_docname=origin_docname,
            ):
                found_needs_slow.append(filter_need)
        except Exception as e:
            if not error_reported:  # Let's report a filter-problem only once
                if append_warning:
                    append_warning = f" {append_warning}"
                log_warning(
                    log,
                    f"{e}{append_warning}",
                    "filter",
                    location=location,
                )
                error_reported = True

    return found_needs_slow


def _fast_path_context(
    filter_data: Mapping[str, Any],
    var_proxy: Any,
    compiled: CompiledFilter,
    origin_docname: str | None,
) -> dict[str, Any] | None:
    """The mapping a compiled filter's predicate reads beside the need.

    What the ``eval`` tier's context holds besides the need's fields: the
    ``needs_filter_data`` keys, the variant data under ``var``, and, for a predicate
    that reads it (``c.this_doc()``), the document the filter is written in. The
    document is passed per call, never compiled in: one compiled filter serves every
    document a string is written in.

    The caller passes the two configuration values it has read: a read of one costs
    more than the rest of a per-need call, and :func:`filter_single_need` is called
    need by need.

    :return: The mapping, or None when the predicate needs nothing of it.
    """
    origin = origin_docname if compiled.reads_origin else None
    if not filter_data and var_proxy is None and origin is None:
        return None
    fallback: dict[str, Any] = dict(filter_data) if filter_data else {}
    if var_proxy is not None:
        fallback["var"] = var_proxy
    if origin is not None:
        fallback[ORIGIN_KEY] = origin
    return fallback


def need_search(*args: Any, **kwargs: Any) -> bool:
    return re.search(*args, **kwargs) is not None


class PredicateContextData(TypedDict):
    """Data for the predicate context."""

    id: str
    type: str
    title: str
    tags: list[str]
    status: str | None
    docname: str | None
    is_external: bool
    is_import: bool


@measure_time("check_default_predicate")
def apply_default_predicate(
    predicate: str,
    config: NeedsSphinxConfig,
    context: PredicateContextData,
    extras: dict[str, AllowedTypes | None],
    links: dict[str, list[str]],
) -> bool:
    """Checks if a single need passes a default predicate.

    :raises NeedsInvalidFilter: if the predicate is not valid, or is a constant
    """
    if _is_constant_filter(predicate):
        raise NeedsInvalidFilter(_constant_filter_message(predicate, "Predicate"))
    predicate_context: dict[str, Any] = {
        **context,
        **extras,
        **links,
        **config.filter_data,
    }
    if (var_proxy := config.variant_data_proxy) is not None:
        predicate_context["var"] = var_proxy
    try:
        # Set filter_context as globals and not only locals in eval()!
        # Otherwise, the vars not be accessed in list comprehensions.
        # a predicate is read for its truth, as a filter is
        result = bool(eval(predicate, predicate_context))
    except Exception as e:
        raise NeedsInvalidFilter(f"Predicate {predicate!r} not valid. Error: {e}.")
    return result


def filter_import_item(
    context: dict[str, Any], config: NeedsSphinxConfig, filter_string: str
) -> bool:
    """Filters a single item from an imported needs.json file.

    :raises NeedsInvalidFilter: if the filter is not valid, or is a constant
    """
    if _is_constant_filter(filter_string):
        raise NeedsInvalidFilter(_constant_filter_message(filter_string))
    filter_context = context.copy()
    # Get needs external filter data and merge to filter_context
    filter_context.update(config.filter_data)
    if (var_proxy := config.variant_data_proxy) is not None:
        filter_context["var"] = var_proxy
    filter_context["search"] = need_search
    try:
        # Set filter_context as globals and not only locals in eval()!
        # Otherwise, the vars not be accessed in list comprehensions.
        # a filter is read for its truth, whatever its value
        result = bool(eval(filter_string, filter_context))
    except Exception as e:
        raise NeedsInvalidFilter(f"Filter {filter_string!r} not valid. Error: {e}.")
    return result


@measure_time("filtering")
def filter_single_need(
    need: NeedItem | NeedPartItem,
    config: NeedsSphinxConfig,
    filter_string: str = "",
    needs: Iterable[NeedItem | NeedPartItem] | None = None,
    current_need: NeedItem | NeedPartItem | None = None,
    filter_compiled: CodeType | None = None,
    *,
    origin_docname: str | None = None,
) -> bool:
    """Checks if a single need/need_part passes a filter_string.

    :param need: the data for a single need
    :param config: NeedsSphinxConfig object
    :param filter_string: string, which is used as input for eval()
    :param needs: list of all needs
    :param current_need: set the current_need in the filter context as this, otherwise the need itself
    :param filter_compiled: An already compiled filter_string to save time
    :param origin_docname: The origin docname that the filter was called from, if any

    :return: True, if need passes the filter_string, else False
    :raises NeedsInvalidFilter: if the filter fails on the need, or is a constant
    """
    if _is_constant_filter(filter_string):
        raise NeedsInvalidFilter(_constant_filter_message(filter_string))
    var_proxy = config.variant_data_proxy

    # === Fast path: short-circuit simple expressions ===
    compiled = compile_portable(filter_string)
    simple_pred = compiled.predicate
    if simple_pred is not None:
        # called need by need: the mapping is built only for a predicate that reads it
        filter_data = config.filter_data
        fallback = (
            _fast_path_context(filter_data, var_proxy, compiled, origin_docname)
            if filter_data
            or var_proxy is not None
            or (origin_docname is not None and compiled.reads_origin)
            else None
        )
        try:
            # read for its truth: a value's own method may give no boolean
            return bool(simple_pred(need, fallback))
        except NeedsInvalidFilter:
            raise
        except Exception as e:
            raise NeedsInvalidFilter(f"Filter {filter_string!r} not valid. Error: {e}.")

    # === Slow path: fall back to eval() ===
    filter_context: dict[str, Any] = need.filter_context()
    if needs:
        filter_context["needs"] = needs
    if current_need:
        filter_context["current_need"] = current_need
    else:
        filter_context["current_need"] = need

    # Get needs external filter data and merge to filter_context
    filter_context.update(config.filter_data)
    if var_proxy is not None:
        filter_context["var"] = var_proxy

    filter_context["search"] = need_search

    filter_context["c"] = NeedCheckContext(need, origin_docname)

    try:
        # Set filter_context as globals and not only locals in eval()!
        # Otherwise, the vars not be accessed in list comprehensions.
        # a filter is read for its truth, whatever its value (#1773)
        result = bool(eval(filter_compiled or filter_string, filter_context))
    except Exception as e:
        raise NeedsInvalidFilter(f"Filter {filter_string!r} not valid. Error: {e}.")
    return result


class NeedCheckContext:
    """A namespace for filter checks of the current need."""

    __slots__ = ("_need", "_origin_docname")

    def __init__(
        self, need: NeedItem | NeedPartItem, origin_docname: str | None
    ) -> None:
        self._need = need
        self._origin_docname = origin_docname

    def this_doc(self) -> bool:
        if self._origin_docname is None:
            raise ValueError("`this_doc` can not be used in this context")
        return self._need.is_in_document(self._origin_docname)
