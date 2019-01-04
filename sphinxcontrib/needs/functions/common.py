"""
Collection of common sphinx-needs functions for dynamic values

.. note:: The function parameters ``app``, ``need``, ``needs`` are set automatically and can not be overridden by user.
"""
# flake8: noqa

from sphinxcontrib.needs.filter_common import filter_single_need, NeedInvalidFilter
from sphinxcontrib.needs.utils import logger


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


def check_linked_values(app, need, needs, result, search_option, search_value, filter_string=None, one_hit=False):
    """
    Returns a specific value, if for all linked needs a given option has a given value.

    The linked needs can be filtered by using the ``filter`` option.

    If ``one_hit`` is set to True, only one linked need must have a positive match for the searched value.

    **Examples**

    **Needs used as input data**

    .. code-block:: jinja

        .. req:: Input A
           :id: clv_A
           :status: in progress

        .. req:: Input B
           :id: clv_B
           :status: in progress

        .. spec:: Input C
           :id: clv_C
           :status: closed

    .. req:: Input A
       :id: clv_A
       :status: in progress
       :collapse: False

    .. req:: Input B
       :id: clv_B
       :status: in progress
       :collapse: False

    .. spec:: Input C
       :id: clv_C
       :status: closed
       :collapse: False


    **Example 1: Positive check**

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


    **Example 2: Negative check**

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


    **Example 3: Positive check thanks of used filter**

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

    **Example 4: Positive check thanks of one_hit option**

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
    :param filter_string: Checks are only performed on linked needs, which pass the defined filter
    :param one_hit: If True, only one linked need must have a positive check
    :return: result, if all checks are positive
    """
    links = need["links"]
    if not isinstance(search_value, list):
        search_value = [search_value]

    for link in links:
        if filter_string is not None:
            try:
                if not filter_single_need(needs[link], filter_string):
                    continue
            except Exception as e:
                logger.warning("CheckLinkedValues: Filter {0} not valid: Error: {1}".format(filter_string, e))

        if not one_hit and not needs[link][search_option] in search_value:
            return None
        elif one_hit and needs[link][search_option] in search_value:
            return result

    return result


def calc_sum(app, need, needs, option, filter=None, links_only=False):
    """
    Sums the values of a given option in filtered needs up to single number.

    Useful e.g. for calculating the amount of needed hours for implementation of all linked
    specification needs.


    **Input data**

    .. spec:: Do this
       :id: sum_input_1
       :hours: 7
       :collapse: False

    .. spec:: Do that
       :id: sum_input_2
       :hours: 15
       :collapse: False

    .. spec:: Do too much
       :id: sum_input_3
       :hours: 110
       :collapse: False

    **Example 2**

    .. code-block:: jinja

       .. req:: Result 1
          :amount: [[calc_sum("hours")]]

    .. req:: Result 1
       :amount: [[calc_sum("hours")]]
       :collapse: False


    **Example 2**

    .. code-block:: jinja

       .. req:: Result 2
          :amount: [[calc_sum("hours", "hours.isdigit() and float(hours) > 10")]]

    .. req:: Result 2
       :amount: [[calc_sum("hours", "hours.isdigit() and float(hours) > 10")]]
       :collapse: False

    **Example 3**

    .. code-block:: jinja

       .. req:: Result 3
          :links: sum_input_1; sum_input_3
          :amount: [[calc_sum("hours", links_only="True")]]

    .. req:: Result 3
       :links: sum_input_1; sum_input_3
       :amount: [[calc_sum("hours", links_only="True")]]
       :collapse: False

    **Example 4**

    .. code-block:: jinja

       .. req:: Result 4
          :links: sum_input_1; sum_input_3
          :amount: [[calc_sum("hours", "hours.isdigit() and float(hours) > 10", "True")]]

    .. req:: Result 4
       :links: sum_input_1; sum_input_3
       :amount: [[calc_sum("hours", "hours.isdigit() and float(hours) > 10", "True")]]
       :collapse: False

    :param option: Options, from which the numbers shall be taken
    :param filter: Filter string, which all needs must passed to get their value added.
    :param links_only: If "True", only linked needs are taken into account.

    :return: A float number
    """
    if not links_only:
        check_needs = needs.values()
    else:
        check_needs = []
        for link in need["links"]:
            check_needs.append(needs[link])

    calculated_sum = 0

    for check_need in check_needs:
        if filter is not None:
            try:
                if not filter_single_need(check_need, filter):
                    continue
            except ValueError as e:
                pass
            except NeedInvalidFilter as ex:
                logger.warning('Given filter is not valid. Error: {}'.format(ex))
        try:
            calculated_sum += float(check_need[option])
        except ValueError:
            pass

    return calculated_sum





