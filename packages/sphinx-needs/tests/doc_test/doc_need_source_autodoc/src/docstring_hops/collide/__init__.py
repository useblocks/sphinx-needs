"""A package whose class has the name of one of its submodules."""

from docstring_hops.collide import Thing as _submodule  # noqa: F401, N813


class Thing:
    """The class, which replaces the submodule as the package's ``Thing``.

    .. req:: Class named like a submodule
       :id: R_COLLIDE
    """

    def area(self):
        """Its method.

        .. req:: Method of a class named like a submodule
           :id: R_COLLIDE_METHOD
        """
