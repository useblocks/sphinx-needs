"""A ``filter-func`` that reports how many needs it was handed.

A scope restricts the *input* of a filter function, not its output, so the first
returned value is the size of the ``needs`` the function received. It is what a
test can assert the scope on, since the numbers of a filter-func pie are
whatever the function returns.
"""


def sizes(needs, results):
    results.append(len(list(needs)))
    results.append(1)


def open_reqs(needs, results):
    """A ``filter-func`` that narrows the needs it was handed, rather than iterating.

    ``needs`` is a view, and a view can be narrowed further -- which is what
    ``docs/api.rst`` promises by publishing the views as injected into filters.
    A scoped chart has to hand over the same kind of object as an unscoped one,
    so this function must work with and without a scope; under ``:status: open``
    it reports the open requirements.
    """
    results.append(len(needs.filter_types(["req"])))
    results.append(1)
