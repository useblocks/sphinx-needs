# flake8: noqa
from sphinxcontrib.needs.functions.common import (
    calc_sum,
    check_linked_values,
    copy,
    echo,
    links_from_content,
    test,
)
from sphinxcontrib.needs.functions.functions import (
    FunctionParsingException,
    execute_func,
    find_and_replace_node_content,
    register_func,
    resolve_dynamic_values,
)

needs_common_functions = [test, echo, copy, check_linked_values, calc_sum, links_from_content]
