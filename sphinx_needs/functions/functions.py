"""
Sphinx-needs functions module
=============================

Cares about the correct registration and execution of sphinx-needs functions to support dynamic values
in need configurations.
"""

from __future__ import annotations

import ast
import re
from typing import Any, Protocol

from docutils import nodes
from sphinx.application import Sphinx
from sphinx.environment import BuildEnvironment
from sphinx.errors import SphinxError
from sphinx.util.tags import Tags

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import (
    NeedsCoreFields,
    NeedsInfoType,
    NeedsMutable,
    SphinxNeedsData,
)
from sphinx_needs.debug import measure_time_func
from sphinx_needs.logging import get_logger, log_warning
from sphinx_needs.nodes import Need
from sphinx_needs.roles.need_func import NeedFunc
from sphinx_needs.utils import match_variants
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
        need: NeedsInfoType | None,
        needs: NeedsView | NeedsMutable,
        *args: Any,
        **kwargs: Any,
    ) -> str | int | float | list[str] | list[int] | list[float] | None: ...


def execute_func(
    app: Sphinx,
    need: NeedsInfoType | None,
    needs: NeedsView | NeedsMutable,
    func_string: str,
    location: str | tuple[str | None, int | None] | nodes.Node | None,
) -> str | int | float | list[str] | list[int] | list[float] | None:
    """Executes a given function string.

    :param env: Sphinx environment
    :param need: Actual need, which contains the found function string
    :param func_string: string of the found function. Without ``[[ ]]``
    :param location: source location of the function call
    :return: return value of executed function
    """
    try:
        func_name, func_args, func_kwargs = _analyze_func_string(func_string, need)
    except FunctionParsingException as err:
        log_warning(
            logger,
            f"Function string {func_string!r} could not be parsed: {err}",
            "dynamic_function",
            location=location,
        )
        return "??"

    needs_config = NeedsSphinxConfig(app.config)

    if func_name not in needs_config.functions:
        log_warning(
            logger,
            f"Unknown function {func_name!r}",
            "dynamic_function",
            location=location,
        )
        return "??"

    func = measure_time_func(
        needs_config.functions[func_name]["function"],
        category="dyn_func",
        source="user",
    )

    try:
        func_return = func(
            app,
            need,
            needs,
            *func_args,
            **func_kwargs,
        )
    except Exception as e:
        log_warning(
            logger,
            f"Error while executing function {func_name!r}: {e}",
            "dynamic_function",
            location=location,
        )
        return "??"

    if func_return is not None and not isinstance(func_return, (str, int, float, list)):
        log_warning(
            logger,
            f"Return value of function {func_name!r} is of type {type(func_return)}. Allowed are str, int, float, list",
            "dynamic_function",
            location=location,
        )
        return "??"
    if isinstance(func_return, list):
        for i, element in enumerate(func_return):
            if not isinstance(element, (str, int, float)):
                log_warning(
                    logger,
                    f"Return value item {i} of function {func_name!r} is of type {type(element)}. Allowed are str, int, float",
                    "dynamic_function",
                    location=location,
                )
                return "??"
    return func_return


FUNC_RE = re.compile(r"\[\[(.*?)\]\]")  # RegEx to detect function strings


def find_and_replace_node_content(
    node: nodes.Node, env: BuildEnvironment, need: NeedsInfoType
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
            if isinstance(child, (nodes.literal_block, nodes.literal, Need)):
                # Do not parse literal blocks or nested needs
                new_children.append(child)
                continue
            new_child = find_and_replace_node_content(child, env, need)
            new_children.append(new_child)
        node.children = new_children
    return node


def resolve_dynamic_values(needs: NeedsMutable, app: Sphinx) -> None:
    """
    Resolve dynamic values inside need data.

    Rough workflow:

    #. Parse all needs and their field values for a string like ``[[ my_func(a, b, c) ]]``
    #. Extract function name and call parameters
    #. Execute registered function name with extracted call parameters
    #. Replace original string with return value

    The registered functions should take the following parameters:

    - ``app``: Sphinx application
    - ``need``: Need data
    - ``all_needs``: All needs of the current sphinx project
    - ``*args``: optional arguments (specified in the function string)
    - ``**kwargs``: optional keyword arguments (specified in the function string)
    """

    config = NeedsSphinxConfig(app.config)

    allowed_fields: set[str] = {
        *(
            k
            for k, v in NeedsCoreFields.items()
            if v.get("allow_df", False) or v.get("deprecate_df", False)
        ),
        *config.extra_options,
        *(link["option"] for link in config.extra_links),
    }
    deprecated_fields: set[str] = {
        *(k for k, v in NeedsCoreFields.items() if v.get("deprecate_df", False)),
    }

    for need in needs.values():
        for need_option in need:
            if need_option not in allowed_fields:
                continue
            if not isinstance(need[need_option], (list, set)):
                func_call: str | None = "init"
                while func_call:
                    try:
                        func_call, func_return = _detect_and_execute_field(
                            need[need_option], need, needs, app
                        )
                    except FunctionParsingException:
                        raise SphinxError(
                            "Function definition of {option} in file {file}:{line} has "
                            "unsupported parameters. "
                            "supported are str, int/float, list".format(
                                option=need_option,
                                file=need["docname"],
                                line=need["lineno"],
                            )
                        )

                    if func_call is None:
                        continue
                    if need_option in deprecated_fields:
                        log_warning(
                            logger,
                            f"Usage of dynamic functions is deprecated in field {need_option!r}, found in need {need['id']!r}",
                            "deprecated",
                            location=(need["docname"], need["lineno"])
                            if need.get("docname")
                            else None,
                        )

                    # Replace original function string with return value of function call
                    if func_return is None:
                        need[need_option] = need[need_option].replace(
                            f"[[{func_call}]]", ""
                        )
                    else:
                        need[need_option] = need[need_option].replace(
                            f"[[{func_call}]]", str(func_return)
                        )

                    if need[need_option] == "":
                        need[need_option] = None
            else:
                new_values = []
                for element in need[need_option]:
                    try:
                        func_call, func_return = _detect_and_execute_field(
                            element, need, needs, app
                        )
                    except FunctionParsingException:
                        raise SphinxError(
                            "Function definition of {option} in file {file}:{line} has "
                            "unsupported parameters. "
                            "supported are str, int/float, list".format(
                                option=need_option,
                                file=need["docname"],
                                line=need["lineno"],
                            )
                        )
                    if func_call is None:
                        new_values.append(element)
                    elif isinstance(func_return, (list, set)):
                        new_values += func_return
                    else:
                        new_values += [func_return]

                need[need_option] = new_values


def resolve_variants_options(
    needs: NeedsMutable,
    needs_config: NeedsSphinxConfig,
    tags: Tags,
) -> None:
    """
    Resolve variants options inside need data.

    These are fields specified by the user,
    that have string values with a special markup syntax like ``var_a:open``.
    These need to be resolved to the actual value.

    Rough workflow:
    #. Parse all needs and their fields for variant handling
    #. Replace original string with return value

    """
    variants_options = needs_config.variant_options

    if not variants_options:
        return

    for need in needs.values():
        # Data to use as filter context.
        need_context: dict[str, Any] = {**need}
        need_context.update(
            **needs_config.filter_data
        )  # Add needs_filter_data to filter context
        need_context.update(
            **{tag: True for tag in tags}
        )  # Add sphinx tags to filter context
        location = (need["docname"], need["lineno"]) if need.get("docname") else None

        for var_option in variants_options:
            if (
                var_option in need
                and isinstance(need[var_option], (str, list, tuple, set))
                and (
                    result := match_variants(
                        need[var_option],
                        need_context,
                        needs_config.variants,
                        location=location,
                    )
                )
                is not None
            ):
                need[var_option] = result


def check_and_get_content(
    content: str,
    need: NeedsInfoType | None,
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
    content: Any, need: NeedsInfoType, needs: NeedsMutable, app: Sphinx
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


def _analyze_func_string(
    func_string: str, need: NeedsInfoType | None
) -> tuple[str, list[Any], dict[str, Any]]:
    """
    Analyze given function string and extract:

    * function name
    * function arguments
    * function keyword arguments

    All given arguments must by of type string, int/float or list.

    :param func_string: string of the function
    :return: function name, arguments, keyword arguments
    """
    try:
        func = ast.parse(func_string)
    except SyntaxError as e:
        need_id = need["id"] if need else "UNKNOWN"
        raise FunctionParsingException(
            f"Parsing function string failed for need {need_id}: {func_string}. {e}"
        )
    try:
        func_call = func.body[0].value  # type: ignore
        func_name = func_call.func.id
    except AttributeError:
        raise FunctionParsingException(
            f"Given dynamic function string is not a valid python call. Got: {func_string}"
        )

    func_args: list[Any] = []
    for arg in func_call.args:
        if isinstance(arg, ast.Num):
            func_args.append(arg.n)
        elif isinstance(arg, (ast.Str, ast.BoolOp)):
            func_args.append(arg.s)  # type: ignore
        elif isinstance(arg, ast.List):
            arg_list: list[Any] = []
            for element in arg.elts:
                if isinstance(element, ast.Num):
                    arg_list.append(element.n)
                elif isinstance(element, ast.Str):
                    arg_list.append(element.s)
            func_args.append(arg_list)
        elif isinstance(arg, ast.Attribute):
            if arg.value.id == "need" and need:  # type: ignore
                func_args.append(need[arg.attr])
            else:
                raise FunctionParsingException("usage of need attribute not supported.")
        elif isinstance(arg, ast.NameConstant):
            if isinstance(arg.value, bool):
                func_args.append(arg.value)
            else:
                raise FunctionParsingException(
                    "Unsupported type found in function definition. Supported are numbers, strings, bool and list"
                )
        else:
            raise FunctionParsingException(
                f"Unsupported type found in function definition: {func_string}. "
                "Supported are numbers, strings, bool and list"
            )
    func_kargs: dict[str, Any] = {}
    for keyword in func_call.keywords:
        kvalue = keyword.value
        kkey = keyword.arg
        if isinstance(kvalue, ast.Num):
            func_kargs[kkey] = kvalue.n
        elif isinstance(kvalue, ast.Str):
            func_kargs[kkey] = kvalue.s
        elif isinstance(kvalue, ast_boolean):  # Check if Boolean
            func_kargs[kkey] = kvalue.value
        elif isinstance(kvalue, ast.List):
            arg_list = []
            for element in kvalue.elts:
                if isinstance(element, ast.Num):
                    arg_list.append(element.n)
                elif isinstance(element, ast.Str):
                    arg_list.append(element.s)
            func_kargs[kkey] = arg_list
        else:
            raise FunctionParsingException()

    return func_name, func_args, func_kargs


class FunctionParsingException(BaseException):
    """Called if parsing of given function string has not worked"""
