def f():
    """A function whose ``__module__`` names the package that re-exports it.

    .. req:: Rewritten module
       :id: R_REWRITE
    """


f.__module__ = "docstring_hops.rewrite"
