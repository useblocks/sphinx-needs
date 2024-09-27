"""
filter_base is used to provide common filter functionality for directives
like needtable, needlist and needflow.
"""

from __future__ import annotations

import ast
import re
from timeit import default_timer as timer
from types import CodeType
from typing import Any, Iterable, TypedDict, overload

from docutils import nodes
from docutils.parsers.rst import directives
from sphinx.application import Sphinx
from sphinx.util.docutils import SphinxDirective

from sphinx_needs.api.exceptions import NeedsInvalidFilter
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import (
    NeedsFilteredBaseType,
    NeedsInfoType,
    NeedsMutable,
    SphinxNeedsData,
)
from sphinx_needs.debug import measure_time, measure_time_func
from sphinx_needs.logging import log_warning
from sphinx_needs.utils import check_and_get_external_filter_func
from sphinx_needs.utils import logger as log
from sphinx_needs.views import NeedsAndPartsListView, NeedsView


class FilterAttributesType(TypedDict):
    status: list[str]
    tags: list[str]
    types: list[str]
    filter: str
    sort_by: str
    filter_code: list[str]
    filter_func: str | None
    export_id: str
    filter_warning: str | None
    """If set, the filter is exported with this ID in the needs.json file."""


class FilterBase(SphinxDirective):
    has_content = True

    base_option_spec = {
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

        status = self.options.get("status")
        if status:
            try:
                status = str(status)
                status = [stat.strip() for stat in re.split(";|,", status)]
            except Exception:
                # If we could not transform/use status information, we just skip this status
                pass
        else:
            status = []

        types = self.options.get("types", [])
        if isinstance(types, str):
            types = [typ.strip() for typ in re.split(";|,", types)]

        if self.options.get("export_id", ""):
            # this is used by needs builders
            SphinxNeedsData(self.env).has_export_filters = True

        # Add the need and all needed information
        collected_filter_options: FilterAttributesType = {
            "status": status,
            "tags": tags,
            "types": types,
            "filter": self.options.get("filter"),
            "sort_by": self.options.get("sort_by"),
            "filter_code": self.content,
            "filter_func": self.options.get("filter-func"),
            "export_id": self.options.get("export_id", ""),
            "filter_warning": self.options.get("filter_warning"),
        }
        return collected_filter_options


def process_filters(
    app: Sphinx,
    needs_view: NeedsView,
    filter_data: NeedsFilteredBaseType,
    origin: str,
    location: nodes.Element,
    include_external: bool = True,
) -> list[NeedsInfoType]:
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

    # check if include external needs
    if not include_external:
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

    found_needs: list[NeedsInfoType] = []

    if (not filter_code or filter_code.isspace()) and not ff_result:
        # TODO these may not be correct for parts
        filtered_needs = needs_view
        if filter_data["status"]:
            filtered_needs = filtered_needs.filter_statuses(filter_data["status"])
        if filter_data["tags"]:
            filtered_needs = filtered_needs.filter_has_tag(filter_data["tags"])
        if filter_data["types"]:
            filtered_needs = filtered_needs.filter_types(
                filter_data["types"], or_type_names=True
            )

        # Get need by filter string
        found_needs = filter_needs_parts(
            filtered_needs.to_list_with_parts(),
            needs_config,
            filter_data["filter"],
            location=location,
        )
    else:
        # The filter results may be dirty, as it may continue manipulated needs.
        found_dirty_needs: list[NeedsInfoType] = []

        if filter_code:  # code from content
            # TODO better context type
            context: dict[str, NeedsAndPartsListView] = {
                "needs": needs_view.to_list_with_parts(),
                "results": [],  # type: ignore[dict-item]
            }
            exec(filter_code, context)
            found_dirty_needs = context["results"]  # type: ignore[assignment]
        elif ff_result:  # code from external file
            args = []
            if ff_result.args:
                args = ff_result.args.split(",")
            args_context = {f"arg{index+1}": arg for index, arg in enumerate(args)}

            # Decorate function to allow time measurments
            filter_func = measure_time_func(
                ff_result.func, category="filter_func", source="user"
            )
            filter_func(
                needs=needs_view.to_list_with_parts(),
                results=found_dirty_needs,
                **args_context,
            )
        else:
            log_warning(
                log, "Something went wrong running filter", None, location=location
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

    if sort_key := filter_data["sort_by"]:
        try:
            found_needs = sorted(
                found_needs,
                key=lambda node: node[sort_key] or "",  # type: ignore[literal-required]
            )
        except KeyError as e:
            log_warning(
                log,
                f"Sorting parameter {sort_key} not valid: Error: {e}",
                None,
                location=location,
            )
            return []

    # Store basic filter configuration and result global list.
    # Needed mainly for exporting the result to needs.json (if builder "needs" is used).
    filter_list = SphinxNeedsData(app.env).get_or_create_filters()

    filter_list[filter_data["target_id"]] = {
        "origin": origin,
        "location": f"{location.source}:{location.line}",
        "filter": filter_data["filter"] or "",
        "status": filter_data["status"],
        "tags": filter_data["tags"],
        "types": filter_data["types"],
        "export_id": filter_data["export_id"].upper(),
        "amount": len(found_needs),
        "runtime": timer() - start,
    }

    return found_needs


def filter_needs_mutable(
    needs: NeedsMutable,
    config: NeedsSphinxConfig,
    filter_string: None | str = "",
    current_need: NeedsInfoType | None = None,
    *,
    location: tuple[str, int | None] | nodes.Node | None = None,
    append_warning: str = "",
) -> list[NeedsInfoType]:
    return filter_needs(
        needs.values(),
        config,
        filter_string,
        current_need,
        location=location,
        append_warning=append_warning,
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
    if isinstance((name := expr), ast.Name):
        # x
        if name.id == "is_external":
            return needs.filter_is_external(True), False

    elif isinstance((compare := expr), ast.Compare):
        # <expr1> <comp> <expr2>
        if len(compare.ops) == 1 and isinstance(compare.ops[0], ast.Eq):
            # x == y
            if (
                isinstance(compare.left, ast.Name)
                and len(compare.comparators) == 1
                and isinstance(compare.comparators[0], (ast.Str, ast.Constant))
            ):
                # x == "value"
                field = compare.left.id
                value = compare.comparators[0].s
            elif (
                isinstance(compare.left, (ast.Str, ast.Constant))
                and len(compare.comparators) == 1
                and isinstance(compare.comparators[0], ast.Name)
            ):
                # "value" == x
                field = compare.comparators[0].id
                value = compare.left.s
            else:
                return needs, True

            if field == "id":
                # id == "value"
                return needs.filter_ids([value]), False
            elif field == "type":
                # type == "value"
                return needs.filter_types([value]), False
            elif field == "status":
                # status == "value"
                return needs.filter_statuses([value]), False

        elif len(compare.ops) == 1 and isinstance(compare.ops[0], ast.In):
            # <expr1> in <expr2>
            if (
                isinstance(compare.left, ast.Name)
                and len(compare.comparators) == 1
                and isinstance(compare.comparators[0], (ast.List, ast.Tuple, ast.Set))
                and all(
                    isinstance(elt, (ast.Str, ast.Constant))
                    for elt in compare.comparators[0].elts
                )
            ):
                values = [elt.s for elt in compare.comparators[0].elts]  # type: ignore[attr-defined]
                if compare.left.id == "id":
                    # id in ["a", "b", ...]
                    return needs.filter_ids(values), False
                if compare.left.id == "status":
                    # status in ["a", "b", ...]
                    return needs.filter_statuses(values), False
                elif compare.left.id == "type":
                    # type in ["a", "b", ...]
                    return needs.filter_types(values), False
            elif (
                isinstance(compare.left, (ast.Str, ast.Constant))
                and len(compare.comparators) == 1
                and isinstance(compare.comparators[0], ast.Name)
                and compare.comparators[0].id == "tags"
            ):
                # "value" in tags
                return needs.filter_has_tag([compare.left.s]), False

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
    filter_string: None | str = "",
    current_need: NeedsInfoType | None = None,
    *,
    location: tuple[str, int | None] | nodes.Node | None = None,
    append_warning: str = "",
) -> list[NeedsInfoType]:
    if not filter_string:
        return list(needs.values())

    try:
        body = ast.parse(filter_string).body
    except Exception:
        pass  # warning already emitted in filter_needs
    else:
        if len(body) == 1 and isinstance((expr := body[0]), ast.Expr):
            needs, requires_eval = _analyze_and_apply_expr(needs, expr.value)
            if not requires_eval:
                return list(needs.values())

    return filter_needs(
        needs.values(),
        config,
        filter_string,
        current_need,
        location=location,
        append_warning=append_warning,
    )


def filter_needs_parts(
    needs: NeedsAndPartsListView,
    config: NeedsSphinxConfig,
    filter_string: None | str = "",
    current_need: NeedsInfoType | None = None,
    *,
    location: tuple[str, int | None] | nodes.Node | None = None,
    append_warning: str = "",
) -> list[NeedsInfoType]:
    if not filter_string:
        return list(needs)

    try:
        body = ast.parse(filter_string).body
    except Exception:
        pass  # warning already emitted in filter_needs
    else:
        if len(body) == 1 and isinstance((expr := body[0]), ast.Expr):
            needs, requires_eval = _analyze_and_apply_expr(needs, expr.value)
            if not requires_eval:
                return list(needs)

    return filter_needs(
        needs,
        config,
        filter_string,
        current_need,
        location=location,
        append_warning=append_warning,
    )


@measure_time("filtering")
def filter_needs(
    needs: Iterable[NeedsInfoType],
    config: NeedsSphinxConfig,
    filter_string: None | str = "",
    current_need: NeedsInfoType | None = None,
    *,
    location: tuple[str, int | None] | nodes.Node | None = None,
    append_warning: str = "",
) -> list[NeedsInfoType]:
    """
    Filters given needs based on a given filter string.
    Returns all needs, which pass the given filter.

    :param needs: list of needs, which shall be filtered
    :param config: NeedsSphinxConfig object
    :param filter_string: strings, which gets evaluated against each need
    :param current_need: current need, which uses the filter.
    :param location: source location for error reporting (docname, line number)
    :param append_warning: additional text to append to any failed filter warning

    :return: list of found needs
    """
    if not filter_string:
        return list(needs)

    found_needs = []

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
            ):
                found_needs.append(filter_need)
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

    return found_needs


def need_search(*args: Any, **kwargs: Any) -> bool:
    return re.search(*args, **kwargs) is not None


@measure_time("filtering")
def filter_single_need(
    need: NeedsInfoType,
    config: NeedsSphinxConfig,
    filter_string: str = "",
    needs: Iterable[NeedsInfoType] | None = None,
    current_need: NeedsInfoType | None = None,
    filter_compiled: CodeType | None = None,
) -> bool:
    """
    Checks if a single need/need_part passes a filter_string

    :param need: the data for a single need
    :param config: NeedsSphinxConfig object
    :param filter_compiled: An already compiled filter_string to safe time
    :param need: need or need_part
    :param filter_string: string, which is used as input for eval()
    :param needs: list of all needs
    :return: True, if need passes the filter_string, else False
    """
    filter_context: dict[str, Any] = need.copy()  # type: ignore
    if needs:
        filter_context["needs"] = needs
    if current_need:
        filter_context["current_need"] = current_need
    else:
        filter_context["current_need"] = need

    # Get needs external filter data and merge to filter_context
    filter_context.update(config.filter_data)

    filter_context["search"] = need_search
    result = False
    try:
        # Set filter_context as globals and not only locals in eval()!
        # Otherwise, the vars not be accessed in list comprehensions.
        if filter_compiled:
            result = eval(filter_compiled, filter_context)
        else:
            result = eval(filter_string, filter_context)
        if not isinstance(result, bool):
            raise NeedsInvalidFilter(
                f"Filter did not evaluate to a boolean, instead {type(result)}: {result}"
            )
    except Exception as e:
        raise NeedsInvalidFilter(f"Filter {filter_string!r} not valid. Error: {e}.")
    return result
