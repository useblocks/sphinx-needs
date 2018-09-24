"""
Sphinx-needs functions module
=============================

Cares about the correct registration and execution of sphinx-needs functions to support dynamic values
in need configurations.
"""

import ast
from sphinx.errors import SphinxError


def register_func(env, need_function):
    """
    Registers a new sphhinx-needs function for the given sphinx environment.
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
