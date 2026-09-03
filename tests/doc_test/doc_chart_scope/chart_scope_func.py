"""A ``filter-func`` that reports how many needs it was handed.

A scope restricts the *input* of a filter function, not its output, so the first
returned value is the size of the ``needs`` the function received. It is what a
test can assert the scope on, since the numbers of a filter-func pie are
whatever the function returns.
"""


def sizes(needs, results):
    results.append(len(list(needs)))
    results.append(1)
