"""A package that removes its submodule from its namespace."""

from docstring_hops.deleted import _impl

g = _impl.g
del _impl
