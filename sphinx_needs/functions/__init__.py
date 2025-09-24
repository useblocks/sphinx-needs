from sphinx_needs.functions.common import (
    calc_sum,
    check_linked_values,
    copy,
    echo,
    links_from_content,
    test,
)
from sphinx_needs.functions.functions import (  # noqa: F401
    DynamicFunction,
    execute_func,
    find_and_replace_node_content,
)

NEEDS_COMMON_FUNCTIONS: list[DynamicFunction] = [
    test,
    echo,
    copy,
    check_linked_values,
    calc_sum,
    links_from_content,
]
