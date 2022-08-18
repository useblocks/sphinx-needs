from sphinx_needs.functions.common import (
    calc_sum,
    check_linked_values,
    copy,
    echo,
    links_from_content,
    test,
)
from sphinx_needs.functions.functions import (  # noqa: F401
    FunctionParsingException,
    execute_func,
    find_and_replace_node_content,
    register_func,
    resolve_dynamic_values,
    resolve_variants_options,
)

needs_common_functions = [test, echo, copy, check_linked_values, calc_sum, links_from_content]
