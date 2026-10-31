"""Objects made at run time, and aliases."""

from docstring_hops.shapes import area_of


def make():
    class Made:
        """A class made in a function.

        .. req:: Made class
           :id: R_MADE
        """

        def go(self):
            """Its method.

            .. req:: Made method
               :id: R_MADE_METHOD
            """

    return Made


Made = make()

#: An alias of a function of this module: autodoc names the docstring by the function's
#: ``__qualname__``.
#:
#: .. req:: Alias of a function here
#:    :id: R_ALIAS_HERE
alias = make

#: An alias of a function of another module.
#:
#: .. req:: Alias of a function there
#:    :id: R_ALIAS_THERE
far = area_of

#: An alias of a function with no Python source.
#:
#: .. req:: Alias of a builtin
#:    :id: R_ALIAS_BUILTIN
length = len

# a function made at run time: its ``__qualname__``, ``generated``, is no definition of this
# file's syntax
_namespace = {"__name__": __name__}
exec(
    '''def generated():
    """A function made by ``exec``.

    .. req:: Made by exec
       :id: R_GENERATED
    """
''',
    _namespace,
)
made_at_run_time = _namespace["generated"]
