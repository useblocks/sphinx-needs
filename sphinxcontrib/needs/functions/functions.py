"""
Sphinx-needs functions module
=============================

Cares about the correct registration and execution of sphinx-needs functions to support dynamic values
in need configurations.
"""

import ast
from docutils import nodes
import re
from sphinx.errors import SphinxError


def register_func(env, need_function):
    """
    Registers a new sphinx-needs function for the given sphinx environment.
    :param env: Sphinx environment
    :param need_function: Python method
    :return: None
    """

    if not hasattr(env, 'needs_functions'):
        env.needs_functions = {}

    func_name = need_function.__name__

    if func_name in env.needs_functions.keys():
        raise SphinxError('sphinx-needs: Function name {} already registered.'.format(func_name))

    env.needs_functions[func_name] = {
        'name': func_name,
        'function': need_function
    }
    pass


def execute_func(env, need, func_string):
    func_name, func_args, func_kwargs = _analyze_func_string(func_string)

    if func_name not in env.needs_functions.keys():
        raise SphinxError('Unknown dynamic sphinx-needs function: {}'.format(func_name))

    func = env.needs_functions[func_name]['function']
    func_return = func(env, need, env.needs_all_needs, *func_args, **func_kwargs)

    if not isinstance(func_return, (str, int, float)):
        raise SphinxError('Return value of function {} is of type {}. Allowed are str, int, float'.format(
            func_name, type(func_return)))

    return func_return


func_pattern = re.compile('\[\[(.*)\]\]')


def find_and_replace_node_content(node, env, need):
    """
    Search inside a given node and its children for nodes of type Text,
    if found check if it contains a function string and run/replace it.

    :param node: Node to analyse
    :return: None
    """
    new_children = []
    if not node.children:
        if isinstance(node, nodes.Text):
            func_match = func_pattern.findall(str(node))
            new_text = node
            for func_string in func_match:
                func_string_org = func_string[:]
                func_string = func_string.replace('„', '"')
                func_string = func_string.replace('“', '"')
                func_string = func_string.replace('”', '"')
                func_string = func_string.replace('‘', '"')
                func_string = func_string.replace('’', '"')
                func_return = execute_func(env, need, func_string)
                new_text = new_text.replace('[[{}]]'.format(func_string_org), func_return)
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
    if env.needs_workflow['dynamic_values_resolved']:
        return

    needs = env.needs_all_needs
    for key, need in needs.items():
        for need_option in need:
            if need_option in ['docname', 'lineno', 'target_node', 'content']:
                # dynamic values in this data are not allowed.
                continue

            func_match = func_pattern.match(str(need[need_option]))
            if func_match is None:
                continue

            func_call = func_match.group(1)  # Extract function call
            try:
                return_value = execute_func(env, need, func_call)  # Exceute function call and get return value
            except FunctionParsingException:
                raise SphinxError("Function definition of {option} in file {file}:{line} has "
                                  "unsupported parameters. "
                                  "supported are str, int/float, list".format(option=need_option,
                                                                              file=need['docname'],
                                                                              line=need['lineno']))
            need[need_option] = return_value  # Replace original function string with return value of function call

    # Finally set a flag so that this function gets not executed several times
    env.needs_workflow['dynamic_values_resolved'] = True


def _analyze_func_string(func_string):
    func = ast.parse(func_string)
    func_call = func.body[0].value
    func_name = func_call.func.id

    func_args = []
    for arg in func_call.args:
        if isinstance(arg, ast.Num):
            func_args.append(arg.n)
        elif isinstance(arg, ast.Str):
            func_args.append(arg.s)
        elif isinstance(arg, ast.List):
            arg_list = []
            for element in arg.elts:
                if isinstance(element, ast.Num):
                    arg_list.append(element.n)
                elif isinstance(element, ast.Str):
                    arg_list.append(element.s)
            func_args.append(arg_list)
        else:
            raise FunctionParsingException()
    func_kargs = {}
    for keyword in func_call.keywords:
        kvalue = keyword.value
        kkey = keyword.arg
        if isinstance(kvalue, ast.Num):
            func_kargs[kkey] = kvalue.n
        elif isinstance(kvalue, ast.Str):
            func_kargs[kkey] = kvalue.s
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
