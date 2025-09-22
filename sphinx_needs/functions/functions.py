"""
Sphinx-needs functions module
=============================

Cares about the correct registration and execution of sphinx-needs functions to support dynamic values
in need configurations.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, TypeAlias

from docutils import nodes
from sphinx.application import Sphinx
from sphinx.environment import BuildEnvironment

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import NeedsMutable, SphinxNeedsData
from sphinx_needs.debug import measure_time_func
from sphinx_needs.exceptions import FunctionParsingException
from sphinx_needs.logging import get_logger, log_warning
from sphinx_needs.need_item import NeedItem, NeedPartItem
from sphinx_needs.nodes import Need
from sphinx_needs.roles.need_func import NeedFunc
from sphinx_needs.variants import VariantFunctionParsed
from sphinx_needs.views import NeedsView

logger = get_logger(__name__)
unicode = str
ast_boolean = ast.NameConstant


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
    ) -> str | int | float | list[str] | list[int] | list[float] | None: ...


def _execute_dynamic_func(
    app: Sphinx,
    need: NeedItem | NeedPartItem | None,
    needs: NeedsView | NeedsMutable,
    df: DynamicFunctionParsed,
) -> str | int | float | list[str] | list[int] | list[float] | None:
    """Executes a given function string.

    :param env: Sphinx environment
    :param need: Actual need, which contains the found function string
    :param func_string: string of the found function. Without ``[[ ]]``
    :param location: source location of the function call
    :return: return value of executed function
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
        raise RuntimeError(f"Error while executing function {df.name!r}: {e}") from e

    return func_return


def execute_func(
    app: Sphinx,
    need: NeedItem | NeedPartItem | None,
    needs: NeedsView | NeedsMutable,
    df: str | DynamicFunctionParsed,
    location: str | tuple[str | None, int | None] | nodes.Node | None,
) -> str | int | float | list[str] | list[int] | list[float] | None:
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
            if not isinstance(element, str | int | float):
                log_warning(
                    logger,
                    f"Return value item {i} of function {df.name!r} is of type {type(element)}. Allowed are str, int, float",
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
    Search inside a given node and its children for nodes of type Text,
    if found, check if it contains a function string and run/replace it.

    :param node: Node to analyse
    :param env: Sphinx environment
    :param need: Need data
    :param extract: If True, the function has been called from a needextract node
    """
    new_children = []
    if isinstance(node, NeedFunc):
        return node.get_text(env, need)
    elif (not node.children and isinstance(node, nodes.Text)) or isinstance(
        node, nodes.reference
    ):
        if isinstance(node, nodes.reference):
            try:
                new_text = node.attributes["refuri"]
            except KeyError:
                # If no refuri is set, we don't need to modify anything.
                # So stop here and return the untouched node.
                return node
        else:
            new_text = node
        func_match = FUNC_RE.findall(new_text)
        for func_string in func_match:
            # sphinx is replacing ' and " with language specific quotation marks (up and down), which makes
            # it impossible for the later used AST render engine to detect a python function call in the given
            # string. Therefor a replacement is needed for the execution of the found string.
            func_string_org = func_string[:]
            func_string = func_string.replace("„", '"')
            func_string = func_string.replace("“", '"')
            func_string = func_string.replace("”", '"')
            func_string = func_string.replace("”", '"')

            func_string = func_string.replace("‘", "'")  # noqa: RUF001
            func_string = func_string.replace("’", "'")  # noqa: RUF001

            msg = f"The [[{func_string}]] syntax in need content is deprecated. Replace with :ndf:`{func_string}` instead."
            log_warning(logger, msg, "deprecated", location=node)

            func_return = execute_func(
                env.app, need, SphinxNeedsData(env).get_needs_view(), func_string, node
            )

            if isinstance(func_return, list):
                func_return = ", ".join(str(el) for el in func_return)

            new_text = new_text.replace(
                f"[[{func_string_org}]]",
                "" if func_return is None else str(func_return),
            )

        if isinstance(node, nodes.reference):
            node.attributes["refuri"] = new_text
            # Call normal handling for children of reference node (will contain related Text node with link-text)
            for child in node.children:
                new_child = find_and_replace_node_content(child, env, need)
                new_children.append(new_child)
                node.children = new_children
        else:
            node = nodes.Text(new_text)
        return node
    else:
        for child in node.children:
            if isinstance(child, nodes.literal_block | nodes.literal | Need):
                # Do not parse literal blocks or nested needs
                new_children.append(child)
                continue
            new_child = find_and_replace_node_content(child, env, need)
            new_children.append(new_child)
        node.children = new_children
    return node


def resolve_functions(
    app: Sphinx,
    needs: NeedsMutable,
    needs_config: NeedsSphinxConfig,
) -> None:
    """Resolve all dynamic/variant functions in all needs."""
    needs_schema = SphinxNeedsData(app.env).get_schema()
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
                        func_return = _execute_dynamic_func(app, need, needs, item)
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
                        var_context: dict[str, Any] = {
                            **need,
                            **needs_config.filter_data,
                            **dict.fromkeys(app.builder.tags, True),
                        }
                        if (
                            var_return := _get_variant(
                                item, needs_config.variants, var_context
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
    variant: VariantFunctionParsed, variants: dict[str, str], context: dict[str, Any]
) -> None | str | int | float | bool:
    for expr, _, value in variant.expressions:
        expr = variants.get(expr, expr)
        if bool(eval(expr, context.copy())):
            return value
    return variant.final_value


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


def _detect_and_execute_field(
    content: Any, need: NeedItem, needs: NeedsMutable, app: Sphinx
) -> tuple[str | None, str | int | float | list[str] | list[int] | list[float] | None]:
    """Detects if given need field value is a function call and executes it."""
    content = str(content)

    func_match = FUNC_RE.search(content)
    if func_match is None:
        return None, None

    func_call = func_match.group(1)  # Extract function call
    func_return = execute_func(
        app,
        need,
        needs,
        func_call,
        (need["docname"], need["lineno"]) if need["docname"] else None,
    )  # Execute function call and get return value

    return func_call, func_return


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
            func_call = func.body[0].value  # type: ignore[attr-defined]
            assert isinstance(func_call, ast.Call)
            func_name = func_call.func.id  # type: ignore[attr-defined]
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
