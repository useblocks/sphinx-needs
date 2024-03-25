"""
Sphinx-needs functions module
=============================

Cares about the correct registration and execution of sphinx-needs functions to support dynamic values
in need configurations.
"""

from __future__ import annotations

import ast
import re
from typing import Any, Callable, Dict, List, Union

from docutils import nodes
from sphinx.application import Sphinx
from sphinx.environment import BuildEnvironment
from sphinx.errors import SphinxError

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import NeedsInfoType, SphinxNeedsData
from sphinx_needs.debug import measure_time_func
from sphinx_needs.logging import get_logger
from sphinx_needs.utils import NEEDS_FUNCTIONS, match_variants  # noqa: F401

logger = get_logger(__name__)
unicode = str
ast_boolean = ast.NameConstant

# TODO these functions also take optional *args and **kwargs
DynamicFunction = Callable[
    [Sphinx, NeedsInfoType, Dict[str, NeedsInfoType]],
    Union[str, int, float, List[Union[str, int, float]]],
]


def register_func(need_function: DynamicFunction, name: str | None = None) -> None:
    """
    Registers a new sphinx-needs function for the given sphinx environment.
    :param env: Sphinx environment
    :param need_function: Python method
    :param name: Name of the function as string
    :return: None
    """

    global NEEDS_FUNCTIONS
    if NEEDS_FUNCTIONS is None:
        NEEDS_FUNCTIONS = {}

    if name is None:
        func_name = need_function.__name__
    else:
        func_name = name

    if func_name in NEEDS_FUNCTIONS:
        # We can not throw an exception here, as using sphinx-needs in different sphinx-projects with the
        # same python interpreter session does not clean NEEDS_FUNCTIONS.
        # This is mostly the case during tet runs.
        logger.info(
            f"sphinx-needs: Function name {func_name} already registered. Ignoring the new one!"
        )

    NEEDS_FUNCTIONS[func_name] = {"name": func_name, "function": need_function}


def execute_func(app: Sphinx, need: NeedsInfoType, func_string: str) -> Any:
    """Executes a given function string.

    :param env: Sphinx environment
    :param need: Actual need, which contains the found function string
    :param func_string: string of the found function. Without ``[[ ]]``
    :return: return value of executed function
    """
    global NEEDS_FUNCTIONS
    func_name, func_args, func_kwargs = _analyze_func_string(func_string, need)

    if func_name not in NEEDS_FUNCTIONS:
        raise SphinxError(
            "Unknown dynamic sphinx-needs function: {}. Found in need: {}".format(
                func_name, need["id"]
            )
        )

    func = measure_time_func(
        NEEDS_FUNCTIONS[func_name]["function"], category="dyn_func", source="user"
    )
    func_return = func(
        app,
        need,
        SphinxNeedsData(app.env).get_or_create_needs(),
        *func_args,
        **func_kwargs,
    )

    if not isinstance(func_return, (str, int, float, list, unicode)) and func_return:
        raise SphinxError(
            f"Return value of function {func_name} is of type {type(func_return)}. Allowed are str, int, float"
        )

    if isinstance(func_return, list):
        for element in func_return:
            if not isinstance(element, (str, int, float, unicode)):
                raise SphinxError(
                    f"Element of return list of function {func_name} is of type {type(func_return)}. "
                    "Allowed are str, int, float"
                )
    return func_return


func_pattern = re.compile(r"\[\[(.*?)\]\]")  # RegEx to detect function strings


def find_and_replace_node_content(
    node: nodes.Node, env: BuildEnvironment, need: NeedsInfoType
) -> nodes.Node:
    """
    Search inside a given node and its children for nodes of type Text,
    if found, check if it contains a function string and run/replace it.

    :param node: Node to analyse
    :return: None
    """
    new_children = []
    if (
        not node.children
        and isinstance(node, nodes.Text)
        or isinstance(node, nodes.reference)
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
        func_match = func_pattern.findall(new_text)
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
            func_return = execute_func(env.app, need, func_string)

            # This should never happen, but we can not be sure.
            if isinstance(func_return, list):
                func_return = ", ".join(func_return)

            new_text = new_text.replace(f"[[{func_string_org}]]", func_return)

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
            new_child = find_and_replace_node_content(child, env, need)
            new_children.append(new_child)
        node.children = new_children
    return node


def resolve_dynamic_values(needs: dict[str, NeedsInfoType], app: Sphinx) -> None:
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
    for need in needs.values():
        for need_option in need:
            if need_option in [
                "docname",
                "lineno",
                "content",
                "content_node",
                "content_id",
            ]:
                # dynamic values in this data are not allowed.
                continue
            if not isinstance(need[need_option], (list, set)):
                func_call: str | None = "init"
                while func_call:
                    try:
                        func_call, func_return = _detect_and_execute(
                            need[need_option], need, app
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
                        func_call, func_return = _detect_and_execute(element, need, app)
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
                    else:
                        # Replace original function string with return value of function call
                        if isinstance(need[need_option], (str, int, float)):
                            new_values.append(
                                element.replace(f"[[{func_call}]]", str(func_return))
                            )
                        else:
                            if isinstance(need[need_option], (list, set)):
                                if isinstance(func_return, (list, set)):
                                    new_values += func_return
                                else:
                                    new_values += [func_return]

                need[need_option] = new_values


def resolve_variants_options(
    needs: dict[str, NeedsInfoType],
    needs_config: NeedsSphinxConfig,
    tags: dict[str, bool],
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
        need_context.update(**tags)  # Add sphinx tags to filter context

        for var_option in variants_options:
            if var_option in need and need[var_option] not in (None, "", []):
                if not isinstance(need[var_option], (list, set, tuple)):
                    option_value: str = need[var_option]
                    need[var_option] = match_variants(
                        option_value, need_context, needs_config.variants
                    )
                else:
                    option_value = need[var_option]
                    need[var_option] = match_variants(
                        option_value, need_context, needs_config.variants
                    )


def check_and_get_content(
    content: str, need: NeedsInfoType, env: BuildEnvironment
) -> str:
    """
    Checks if the given content is a function call.
    If not, content is returned.
    If it is, the functions gets executed and its returns value replaces the related part in content.

    :param content: option content string
    :param need: need
    :param env: Sphinx environment object
    :return: string
    """

    try:
        content = str(content)
    except UnicodeEncodeError:
        content = content.encode("utf-8")  # type: ignore

    func_match = func_pattern.search(content)
    if func_match is None:
        return content

    func_call = func_match.group(1)  # Extract function call
    func_return = execute_func(
        env.app, need, func_call
    )  # Execute function call and get return value

    # Replace the function_call with the calculated value
    content = content.replace(f"[[{func_call}]]", func_return)
    return content


def _detect_and_execute(
    content: Any, need: NeedsInfoType, app: Sphinx
) -> tuple[str | None, Any]:
    """Detects if given content is a function call and executes it."""
    try:
        content = str(content)
    except UnicodeEncodeError:
        content = content.encode("utf-8")

    func_match = func_pattern.search(content)
    if func_match is None:
        return None, None

    func_call = func_match.group(1)  # Extract function call
    func_return = execute_func(
        app, need, func_call
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
        raise SphinxError(
            f"Parsing function string failed for need {need_id}: {func_string}. {e}"
        )
    try:
        func_call = func.body[0].value  # type: ignore
        func_name = func_call.func.id
    except AttributeError:
        raise SphinxError(
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
