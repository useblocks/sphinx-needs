"""
Collection of common sphinx-needs functions for dynamic values

.. note:: The function parameters ``app``, ``need``, ``needs`` are set automatically and can not be overridden by user.
"""

from __future__ import annotations

import contextlib
import re
from typing import Any

from sphinx.application import Sphinx

from sphinx_needs.api.exceptions import NeedsInvalidFilter
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import NeedsInfoType
from sphinx_needs.filter_common import filter_needs, filter_single_need
from sphinx_needs.utils import logger


def test(
    app: Sphinx,
    need: NeedsInfoType,
    needs: dict[str, NeedsInfoType],
    *args: Any,
    **kwargs: Any,
) -> str:
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
    return f"Test output of need {need['id']}. args: {args}. kwargs: {kwargs}"


def echo(
    app: Sphinx,
    need: NeedsInfoType,
    needs: dict[str, NeedsInfoType],
    text: str,
    *args: Any,
    **kwargs: Any,
) -> str:
    """
    .. versionadded:: 0.6.3

    Just returns the given string back.
    Mostly useful for tests.

    .. code-block:: jinja

       A nice :need_func:`[[echo("first")]] test` for need_func.

    **Result**: A nice :need_func:`[[echo("first")]] test` for need_func.

    """
    return text


def copy(
    app: Sphinx,
    need: NeedsInfoType,
    needs: dict[str, NeedsInfoType],
    option: str,
    need_id: str | None = None,
    lower: bool = False,
    upper: bool = False,
    filter: str | None = None,
) -> Any:
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

    If the filter_string needs to compare a value from the current need and the value is unknown yet,
    you can reference the valued field by using ``current_need["my_field"]`` inside the filter string.
    Small example::

        .. test:: test of current_need value
           :id: copy_4

           The es the title of the first need found under the same highest
           section (headline):

           [[copy('title', filter='current_need["sections"][-1]==sections[-1]')]]

    .. test:: test of current_need value
       :id: copy_4

       The following copy command copies the title of the first need found under the same  highest
       section (headline):

            [[copy('title', filter='current_need["sections"][-1]==sections[-1]')]]

    This filter possibilities get really powerful in combination with :ref:`needs_global_options`.


    :param option: Name of the option to copy
    :param need_id: id of the need, which contains the source option. If None, current need is taken
    :param upper: Is set to True, copied value will be uppercase
    :param lower: Is set to True, copied value will be lowercase
    :param filter: :ref:`filter_string`, which first result is used as copy source.
    :return: string of copied need option
    """
    if need_id:
        need = needs[need_id]

    if filter:
        result = filter_needs(
            needs.values(),
            NeedsSphinxConfig(app.config),
            filter,
            need,
            location=(need["docname"], need["lineno"]) if need["docname"] else None,
        )
        if result:
            need = result[0]

    value = need[option]  # type: ignore[literal-required]

    # TODO check if str?

    if lower:
        return value.lower()
    if upper:
        return value.upper()

    return value


def check_linked_values(
    app: Sphinx,
    need: NeedsInfoType,
    needs: dict[str, NeedsInfoType],
    result: Any,
    search_option: str,
    search_value: Any,
    filter_string: str | None = None,
    one_hit: bool = False,
) -> Any:
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
    needs_config = NeedsSphinxConfig(app.config)
    links = need["links"]
    if not isinstance(search_value, list):
        search_value = [search_value]

    for link in links:
        need = needs[link]
        if filter_string:
            try:
                if not filter_single_need(need, needs_config, filter_string):
                    continue
            except Exception as e:
                logger.warning(
                    f"CheckLinkedValues: Filter {filter_string} not valid: Error: {e} [needs]",
                    type="needs",
                )

        need_value = need[search_option]  # type: ignore[literal-required]
        if not one_hit and need_value not in search_value:
            return None
        elif one_hit and need_value in search_value:
            return result

    return result


def calc_sum(
    app: Sphinx,
    need: NeedsInfoType,
    needs: dict[str, NeedsInfoType],
    option: str,
    filter: str | None = None,
    links_only: bool = False,
) -> float:
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
    needs_config = NeedsSphinxConfig(app.config)
    check_needs = (
        [needs[link] for link in need["links"]] if links_only else needs.values()
    )

    calculated_sum = 0.0

    for check_need in check_needs:
        if filter:
            try:
                if not filter_single_need(check_need, needs_config, filter):
                    continue
            except ValueError:
                pass
            except NeedsInvalidFilter as ex:
                logger.warning(
                    f"Given filter is not valid. Error: {ex} [needs]", type="needs"
                )

        with contextlib.suppress(ValueError):
            calculated_sum += float(check_need[option])  # type: ignore[literal-required]

    return calculated_sum


def links_from_content(
    app: Sphinx,
    need: NeedsInfoType,
    needs: dict[str, NeedsInfoType],
    need_id: str | None = None,
    filter: str | None = None,
) -> list[str]:
    """
    Extracts links from content of a need.

    All need-links set by using ``:need:`NEED_ID``` get extracted.

    Same links are only added once.

    Example:

    .. req:: Requirement 1
       :id: CON_REQ_1

    .. req:: Requirement 2
       :id: CON_REQ_2

    .. spec:: Test spec
       :id: CON_SPEC_1
       :links: [[links_from_content()]]

       This specification cares about the realisation of:

       * :need:`CON_REQ_1`
       * :need:`My need <CON_REQ_2>`

    .. spec:: Test spec 2
       :id: CON_SPEC_2
       :links: [[links_from_content('CON_SPEC_1')]]

       Links retrieved from content of :need:`CON_SPEC_1`

    Used code of **CON_SPEC_1**::

       .. spec:: Test spec
          :id: CON_SPEC_1
          :links: [[links_from_content()]]

          This specification cares about the realisation of:

          * :need:`CON_REQ_1`
          * :need:`CON_REQ_2`

       .. spec:: Test spec 2
          :id: CON_SPEC_2
          :links: [[links_from_content('CON_SPEC_1')]]

          Links retrieved from content of :need:`CON_SPEC_1`

    :param need_id: ID of need, which provides the content. If not set, current need is used.
    :param filter: :ref:`filter_string`, which a found need-link must pass.
    :return: List of linked need-ids in content
    """
    source_need = needs[need_id] if need_id else need

    links = re.findall(r":need:`(\w+)`|:need:`.+\<(.+)\>`", source_need["content"])
    raw_links = []
    for link in links:
        if link[0] and link[0] not in raw_links:
            raw_links.append(link[0])
        elif link[1] and link[0] not in raw_links:
            raw_links.append(link[1])

    if filter:
        needs_config = NeedsSphinxConfig(app.config)
        filtered_links = []
        for link in raw_links:
            if link not in filtered_links and filter_single_need(
                needs[link], needs_config, filter
            ):
                filtered_links.append(link)
        return filtered_links

    return raw_links
