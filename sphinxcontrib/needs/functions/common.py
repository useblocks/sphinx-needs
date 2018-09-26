"""
Collection of common sphinx-needs functions for dynamic values

.. note:: The function parameters ``app``, ``need``, ``needs`` are set automatically and can not be overridden by user.
"""


def test(app, need, needs, *args, **kwargs):
    """
    Test function for dynamic functions in sphinx needs.

    Collects every given args and kwargs and returns a single string, which contains their values/keys.

    :return: single test string
    """
    return "Test output of need {}. args: {}. kwargs: {}".format(need['id'], args, kwargs)


def copy(app, need, needs, option, need_id=None):
    """
    Copies the value of one need option to another

    .. code-block:: jinja

        .. req:: copy-example
           :id: copy_1
           :status: open

        .. spec:: copy-example implementation
           :id: copy_2
           :status: [[copy("status", "copy_1")]]
           :comment: [[copy("id")]]

           Copies status of ``copy_1`` to own status.
           Sets also a comment, which copies the id of own need.

    .. req:: copy-example
           :id: copy_1
           :status: open

    .. spec:: copy-example implementation
       :id: copy_2
       :status: [[copy("status", "copy_1")]]
       :comment: [[copy("id")]]

       Copies status of ``copy_1`` to own status.
       Sets also a comment, which copies the id of own need.

    :param option: Name of the option to copy
    :param need_id: id of the need, which contains the source option. If None, current need is taken
    :return: string of copied need option
    """
    if need_id is not None:
        need = needs[need_id]

    return need[option]

