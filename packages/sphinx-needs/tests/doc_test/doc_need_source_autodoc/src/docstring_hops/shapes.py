"""The module docstring.

.. req:: Module docstring
   :id: R_MODULE
"""

from docstring_hops.base import Base


def area_of(shape):
    """A module function.

    .. req:: Module function
       :id: R_FUNC
    """


#: A module attribute.
#:
#: .. req:: Module attribute
#:    :id: R_DATA
LIMIT = 3


class Shape(Base):
    """A class.

    .. req:: Class
       :id: R_CLASS
    """

    #: A class attribute.
    #:
    #: .. req:: Class attribute
    #:    :id: R_ATTR
    sides = 0

    def summary(self):
        # an override without a docstring: autodoc gives it ``Base.summary``'s
        pass

    def area(self):
        """A method.

        .. req:: Method
           :id: R_METHOD
        """

    #: An alias of a method, in the class.
    #:
    #: .. req:: Alias of a method
    #:    :id: R_CLASS_ALIAS
    other = area

    @staticmethod
    def make():
        """A staticmethod.

        .. req:: Staticmethod
           :id: R_STATIC
        """

    @classmethod
    def build(cls):
        """A classmethod.

        .. req:: Classmethod
           :id: R_CLASSMETHOD
        """

    @property
    def size(self):
        """A property.

        .. req:: Property
           :id: R_PROPERTY
        """
        return 1

    class Inner:
        """A nested class.

        .. req:: Nested class
           :id: R_NESTED
        """

        def deep(self):
            """A method of the nested class.

            .. req:: Nested method
               :id: R_NESTED_METHOD
            """


class Oops(Exception):
    """An exception.

    .. req:: Exception
       :id: R_EXCEPTION
    """
