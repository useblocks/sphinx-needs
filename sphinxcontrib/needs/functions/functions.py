# -*- coding: utf-8 -*-

"""
Sphinx-needs functions module
=============================

Cares about the correct registration and execution of sphinx-needs functions to support dynamic values
in need configurations.
"""

import ast
import re

from docutils import nodes
from sphinx.errors import SphinxError

from sphinxcontrib.needs.logging import get_logger
from sphinxcontrib.needs.utils import NEEDS_FUNCTIONS  # noqa: F401

logger = get_logger(__name__)
unicode = str
ast_boolean = ast.NameConstant


def register_func(need_function):
    """
    Registers a new sphinx-needs function for the given sphinx environment.
    :param env: Sphinx environment
    :param need_function: Python method
    :return: None
    """

    # if not hasattr(env, 'needs_functions'):
    #     env.needs_functions = {}
    global NEEDS_FUNCTIONS
    if NEEDS_FUNCTIONS is None:
        NEEDS_FUNCTIONS = {}

    func_name = need_function.__name__

    if func_name in NEEDS_FUNCTIONS.keys():
        # We can not throw an exception here, as using sphinx-needs in different sphinx-projects with the
        # same python interpreter session does not clean NEEDS_FUNCTIONS.
        # This is mostly the case during tet runs.
        logger.info(f"sphinx-needs: Function name {func_name} already registered. Ignoring the new one!")

    # env.needs_functions[func_name] = {
    NEEDS_FUNCTIONS[func_name] = {"name": func_name, "function": need_function}


def execute_func(env, need, func_string):
    """
    Executes a given function string.
    :param env: Sphinx environment
    :param need: Actual need, which contains the found function string
    :param func_string: string of the found function. Without [[ ]]
    :return: return value of executed function
    """
    global NEEDS_FUNCTIONS
    func_name, func_args, func_kwargs = _analyze_func_string(func_string, need)

    # if func_name not in env.needs_functions.keys():
    if func_name not in NEEDS_FUNCTIONS.keys():
        raise SphinxError("Unknown dynamic sphinx-needs function: {}. Found in need: {}".format(func_name, need["id"]))

    # func = env.needs_functions[func_name]['function']

    func = NEEDS_FUNCTIONS[func_name]["function"]
    func_return = func(env, need, env.needs_all_needs, *func_args, **func_kwargs)

    if not isinstance(func_return, (str, int, float, list, unicode)) and func_return:
        raise SphinxError(
            "Return value of function {} is of type {}. Allowed are str, int, float".format(
                func_name, type(func_return)
            )
        )

    if isinstance(func_return, list):
        for element in func_return:
            if not isinstance(element, (str, int, float, unicode)):
                raise SphinxError(
                    "Element of return list of function {} is of type {}. "
                    "Allowed are str, int, float".format(func_name, type(func_return))
                )
    return func_return


func_pattern = re.compile(r"\[\[(.*?)\]\]")  # RegEx to detect function strings


def find_and_replace_node_content(node, env, need):
    """
    Search inside a given node and its children for nodes of type Text,
    if found check if it contains a function string and run/replace it.

    :param node: Node to analyse
    :return: None
    """
    new_children = []
    if not node.children and isinstance(node, nodes.Text) or isinstance(node, nodes.reference):
        if isinstance(node, nodes.reference):
            try:
                new_text = node.attributes["refuri"]
            except KeyError:
                # If no refuri is set, we don't not need to modify anything.
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

            func_string = func_string.replace("‘", "'")
            func_string = func_string.replace("’", "'")
            func_return = execute_func(env, need, func_string)

            # This should never happen, but we can not be sure.
            if isinstance(func_return, list):
                func_return = ", ".join(func_return)

            new_text = new_text.replace("[[{}]]".format(func_string_org), func_return)

        if isinstance(node, nodes.reference):
            node.attributes["refuri"] = new_text
            # Call normal handling for children of reference node (will contain related Text node with link-text)
            for child in node.children:
                new_child = find_and_replace_node_content(child, env, need)
                new_children.append(new_child)
                node.children = new_children
        else:
            node = nodes.Text(new_text, new_text)
        return node
    else:
        for child in node.children:
            new_child = find_and_replace_node_content(child, env, need)
            new_children.append(new_child)
        node.children = new_children
    return node


def resolve_dynamic_values(env):
    """
    Resolve dynamic values inside need data.

    Rough workflow:

    #. Parse all needs and their data for a string like [[ my_func(a,b,c) ]]
    #. Extract function name and call parameters
    #. Execute registered function name with extracted call parameters
    #. Replace original string with return value

    :param env: Sphinx environment
    :return: return value of given function
    """
    # Only perform calculation if not already done yet
    if env.needs_workflow["dynamic_values_resolved"]:
        return

    needs = env.needs_all_needs
    for need in needs.values():
        for need_option in need:
            if need_option in ["docname", "lineno", "target_node", "content", "content_node"]:
                # dynamic values in this data are not allowed.
                continue
            if not isinstance(need[need_option], (list, set)):
                func_call = True
                while func_call:
                    try:
                        func_call, func_return = _detect_and_execute(need[need_option], need, env)
                    except FunctionParsingException:
                        raise SphinxError(
                            "Function definition of {option} in file {file}:{line} has "
                            "unsupported parameters. "
                            "supported are str, int/float, list".format(
                                option=need_option, file=need["docname"], line=need["lineno"]
                            )
                        )

                    if func_call is None:
                        continue
                    # Replace original function string with return value of function call
                    if func_return is None:
                        need[need_option] = need[need_option].replace("[[{}]]".format(func_call), "")
                    else:
                        need[need_option] = need[need_option].replace("[[{}]]".format(func_call), str(func_return))

                    if need[need_option] == "":
                        need[need_option] = None
            else:
                new_values = []
                for element in need[need_option]:
                    try:
                        func_call, func_return = _detect_and_execute(element, need, env)
                    except FunctionParsingException:
                        raise SphinxError(
                            "Function definition of {option} in file {file}:{line} has "
                            "unsupported parameters. "
                            "supported are str, int/float, list".format(
                                option=need_option, file=need["docname"], line=need["lineno"]
                            )
                        )
                    if func_call is None:
                        new_values.append(element)
                    else:
                        # Replace original function string with return value of function call
                        if isinstance(need[need_option], (str, int, float)):
                            new_values.append(element.replace("[[{}]]".format(func_call), str(func_return)))
                        else:
                            if isinstance(need[need_option], (list, set)):
                                if isinstance(func_return, (list, set)):
                                    new_values += func_return
                                else:
                                    new_values += [func_return]

                need[need_option] = new_values

    # Finally set a flag so that this function gets not executed several times
    env.needs_workflow["dynamic_values_resolved"] = True


def check_and_get_content(content, need, env):
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
        content = content.encode("utf-8")

    func_match = func_pattern.search(content)
    if func_match is None:
        return content

    func_call = func_match.group(1)  # Extract function call
    func_return = execute_func(env, need, func_call)  # Execute function call and get return value

    # Replace the function_call with the calculated value
    content = content.replace("[[{}]]".format(func_call), func_return)
    return content


def _detect_and_execute(content, need, env):
    try:
        content = str(content)
    except UnicodeEncodeError:
        content = content.encode("utf-8")

    func_match = func_pattern.search(content)
    if func_match is None:
        return None, None

    func_call = func_match.group(1)  # Extract function call
    func_return = execute_func(env, need, func_call)  # Execute function call and get return value

    return func_call, func_return


def _analyze_func_string(func_string, need):
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
        need_id = need["id"] or "UNKNOWN"
        raise SphinxError("Parsing function string failed for need {}: {}. {}".format(need_id, func_string, e))
    try:
        func_call = func.body[0].value
        func_name = func_call.func.id
    except AttributeError:
        raise SphinxError("Given dynamic function string is not a valid python call. Got: {}".format(func_string))

    func_args = []
    for arg in func_call.args:
        if isinstance(arg, ast.Num):
            func_args.append(arg.n)
        elif isinstance(arg, ast.Str):
            func_args.append(arg.s)
        elif isinstance(arg, ast.BoolOp):
            func_args.append(arg.s)
        elif isinstance(arg, ast.List):
            arg_list = []
            for element in arg.elts:
                if isinstance(element, ast.Num):
                    arg_list.append(element.n)
                elif isinstance(element, ast.Str):
                    arg_list.append(element.s)
            func_args.append(arg_list)
        elif isinstance(arg, ast.Attribute):
            if arg.value.id == "need" and need:
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
                "Unsupported type found in function definition: {}. "
                "Supported are numbers, strings, bool and list".format(func_string)
            )
    func_kargs = {}
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
