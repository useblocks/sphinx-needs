# flake8: noqa
from sphinxcontrib.needs.functions.functions import register_func, execute_func, resolve_dynamic_values, \
    find_and_replace_node_content, FunctionParsingException

from sphinxcontrib.needs.functions.common import test, copy

needs_common_functions = [test, copy]
