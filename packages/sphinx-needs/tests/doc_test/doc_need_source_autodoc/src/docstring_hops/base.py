class Base:
    """The base class, in a module of its own."""

    def describe(self):
        """A method a class in another module inherits.

        .. req:: Inherited method
           :id: R_INHERITED
        """

    def summary(self):
        """A method an override without a docstring inherits the docstring of.

        .. req:: Inherited docstring
           :id: R_OVERRIDE
        """
