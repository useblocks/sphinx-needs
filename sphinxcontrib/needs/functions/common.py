"""
Collection of common sphinx-needs functions for dynamic values

.. note:: The function parameters ``app``, ``need``, ``needs`` are set automatically and can not be overridden by user.
"""
# flake8: noqa


import re


def test(app, need, needs, *args, **kwargs):
    """
    Test function for dynamic functions in sphinx needs.

    Collects every given args and kwargs and returns a single string, which contains their values/keys.

    .. code-block:: jinja

        .. req:: test requirement

            [[test('arg_1', [1,2,3], my_keyword='awesome')]]

    .. req:: test requirement

        [[test('arg_1', [1,2,3], my_keyword='awesome')]]

    :return: single test string
    """
    return "Test output of need {}. args: {}. kwargs: {}".format(need['id'], args, kwargs)


def copy(app, need, needs, option, need_id=None):
    """
    Copies the value of one need option to another

    .. code-block:: jinja

        .. req:: copy-example
           :id: copy_1
           :tags: tag_1, tag_2, tag_3
           :status: open

        .. spec:: copy-example implementation
           :id: copy_2
           :status: [[copy("status", "copy_1")]]
           :links: copy_1
           :comment: [[copy("id")]]

           Copies status of ``copy_1`` to own status.
           Sets also a comment, which copies the id of own need.

        .. test:: test of specification and requirement
           :id: copy_3
           :links: copy_2; [[copy('links', 'copy_2')]]
           :tags: [[copy('tags', 'copy_1')]]

           Set own link to ``copy_2`` and also copies all links from it.

           Also copies all tags from copy_1.

    .. req:: copy-example
       :id: copy_1
       :tags: tag_1, tag_2, tag_3
       :status: open

    .. spec:: copy-example implementation
       :id: copy_2
       :status: [[copy("status", "copy_1")]]
       :links: copy_1
       :comment: [[copy("id")]]

       Copies status of ``copy_1`` to own status.
       Sets also a comment, which copies the id of own need.

    .. test:: test of specification and requirement
       :id: copy_3
       :links: copy_2; [[copy('links', 'copy_2')]]
       :tags: [[copy('tags', 'copy_1')]]

       Set own link to ``copy_2`` and also copies all links from it.

       Also copies all tags from copy_1.

    :param option: Name of the option to copy
    :param need_id: id of the need, which contains the source option. If None, current need is taken
    :return: string of copied need option
    """
    if need_id is not None:
        need = needs[need_id]

    return need[option]


def check_linked_values(app, need, needs, result, search_option, search_value, filter=None, one_hit=False):
    """
    Returns a specific value, if for all linked needs a given option has a given value.

    The linked needs can be filtered by using the ``filter`` option.

    If ``one_hit`` is set to True, only one linked need must have a positive match for the searched value.

    **Examples**

    **Needs used as input data**

    .. code-block:: jinja

        .. req:: example A
           :id: clv_A
           :status: in progress

        .. req:: example B
           :id: clv_B
           :status: in progress

        .. spec:: example C
           :id: clv_C
           :status: closed

    .. req:: example A
       :id: clv_A
       :status: in progress
       :collapse: False

    .. req:: example B
       :id: clv_B
       :status: in progress
       :collapse: False

    .. spec:: example C
       :id: clv_C
       :status: closed
       :collapse: False


    **Result 1: Positive check**

    Status gets set to *progress*.

    .. code-block:: jinja

        .. spec:: result 1: Positive check
           :links: clv_A, clv_B
           :status: [[check_linked_values('progress', 'status', 'in progress' )]]

    .. spec:: result 1: Positive check
       :id: clv_1
       :links: clv_A, clv_B
       :status: [[check_linked_values('progress', 'status', 'in progress' )]]
       :collapse: False


    **Result 2: Negative check**

    Status gets not set to *progress*, because status of linked need *clv_C* does not match *"in progress"*.

    .. code-block:: jinja

        .. spec:: result 2: Negative check
           :links: clv_A, clv_B, clv_C
           :status: [[check_linked_values('progress', 'status', 'in progress' )]]

    .. spec:: result 2: Negative check
       :id: clv_2
       :links: clv_A, clv_B, clv_C
       :status: [[check_linked_values('progress', 'status', 'in progress' )]]
       :collapse: False


    **Result 3: Positive check thanks of used filter**

    status gets set to *progress*, because linked need *clv_C* is not part of the filter.

    .. code-block:: jinja

        .. spec:: result 3: Positive check thanks of used filter
           :links: clv_A, clv_B, clv_C
           :status: [[check_linked_values('progress', 'status', 'in progress', 'type == "req" ' )]]

    .. spec:: result 3: Positive check thanks of used filter
       :id: clv_3
       :links: clv_A, clv_B, clv_C
       :status: [[check_linked_values('progress', 'status', 'in progress', 'type == "req" ' )]]
       :collapse: False

    **Result 4: Positive check thanks of one_hit option**

    Even *clv_C* has not the searched status, status gets anyway set to *progress*.
    That's because ``one_hit`` is used so that only one linked need must have the searched
    value.

    .. code-block:: jinja

        .. spec:: result 4: Positive check thanks of one_hit option
           :links: clv_A, clv_B, clv_C
           :status: [[check_linked_values('progress', 'status', 'in progress', one_hit=True )]]

    .. spec:: result 4: Positive check thanks of one_hit option
       :id: clv_4
       :links: clv_A, clv_B, clv_C
       :status: [[check_linked_values('progress', 'status', 'in progress', one_hit=True )]]
       :collapse: False

    **Result 5: Two checks and a joint status**
    Two checks are performed and both are positive. So their results get joined.

    .. code-block:: jinja

        .. spec:: result 5: Two checks and a joint status
           :links: clv_A, clv_B, clv_C
           :status: [[check_linked_values('progress', 'status', 'in progress', one_hit=True )]] [[check_linked_values('closed', 'status', 'closed', one_hit=True )]]

    .. spec:: result 5: Two checks and a joint status
       :id: clv_5
       :links: clv_A, clv_B, clv_C
       :status: [[check_linked_values('progress', 'status', 'in progress', one_hit=True )]] [[check_linked_values('closed', 'status', 'closed', one_hit=True )]]
       :collapse: False

    :param result: value, which gets returned if all linked needs have parsed the checks
    :param search_option: option name, which is used n linked needs for the search
    :param search_value: value, which an option of a linked need must match
    :param filter: Checks are only performed on linked needs, which pass the defined filter
    :param one_hit: If True, only one linked need must have a positive check
    :return: result, if all checks are positive
    """
    links = need["links"]
    if not isinstance(search_value, list):
        search_value = [search_value]

    for link in links:
        if filter is not None:
            filter_context = needs[link].copy()
            filter_context["search"] = re.search
            try:
                if not eval(filter, None, filter_context):
                    continue
            except Exception as e:
                print("Filter {0} not valid: Error: {1}".format(filter, e))

        if not one_hit and not needs[link][search_option] in search_value:
            return None
        elif one_hit and needs[link][search_option] in search_value:
            return result

    return result
