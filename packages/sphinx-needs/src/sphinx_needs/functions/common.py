"""
Collection of common sphinx-needs functions for dynamic values

.. note:: The function parameters ``app``, ``need``, ``needs`` are set automatically and can not be overridden by user.
   So is the keyword-only ``reads`` of the functions marked ``records_reads``.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from operator import itemgetter
from typing import Any

from docutils import nodes
from sphinx.application import Sphinx

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import NeedsMutable, SphinxNeedsData
from sphinx_needs.exceptions import NeedsInvalidFilter
from sphinx_needs.filter_common import (
    filter_needs_and_parts,
    filter_single_need,
)
from sphinx_needs.functions.functions import UnresolvedReads, records_reads
from sphinx_needs.logging import log_warning
from sphinx_needs.need_item import NeedItem, NeedLink, NeedPartItem
from sphinx_needs.nodes import Need
from sphinx_needs.roles.need_ref import NeedRef
from sphinx_needs.utils import logger
from sphinx_needs.views import NeedsView


def test(
    app: Sphinx,
    need: NeedItem | NeedPartItem | None,
    needs: NeedsMutable | NeedsView,
    *args: Any,
    **kwargs: Any,
) -> str:
    """
    Test function for dynamic functions in sphinx needs.

    Collects every given args and kwargs and returns a single string, which contains their values/keys.

    .. syntax-example::

        .. req:: test requirement

            :ndf:`test('arg_1', [1,2,3], my_keyword='awesome')`

    :return: single test string
    """
    need_id = "none" if need is None else need["id"]
    return f"Test output of dynamic function; need: {need_id}; args: {args}; kwargs: {kwargs}"


def echo(
    app: Sphinx,
    need: NeedItem | NeedPartItem | None,
    needs: NeedsMutable | NeedsView,
    text: str,
    *args: Any,
    **kwargs: Any,
) -> str:
    """
    .. versionadded:: 0.6.3

    Just returns the given string back.
    Mostly useful for tests.

    .. syntax-example::

       A nice :ndf:`echo("first test")` for a dynamic function.

    """
    return text


@records_reads
def copy(
    app: Sphinx,
    need: NeedItem | NeedPartItem | None,
    needs: NeedsMutable | NeedsView,
    option: str,
    need_id: str | None = None,
    lower: bool = False,
    upper: bool = False,
    filter: str | None = None,
    *,
    reads: UnresolvedReads | None = None,
) -> Any:
    """
    Copies the value of one need option to another

    .. syntax-example::

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

           The following copy command copies the title of the need with the lowest id
           under the same highest section (headline):

           :ndf:`copy('title', filter='current_need["sections"][-1]==sections[-1]')`

    .. test:: test of current_need value
       :id: copy_4

       The following copy command copies the title of the need with the lowest id
       under the same highest section (headline):

       :ndf:`copy('title', filter='current_need["sections"][-1]==sections[-1]')`

    :param option: Name of the option to copy
    :param need_id: id of the need, which contains the source option. If None, current need is taken
    :param upper: Is set to True, copied value will be uppercase
    :param lower: Is set to True, copied value will be lowercase
    :param filter: :ref:`filter_string`; of the needs it matches,
        the match with the lowest id is the copy source, comparing ids as strings
        (so ``REQ_10`` comes before ``REQ_9``).
    :return: string of copied need option
    """
    if need_id:
        need = needs[need_id]

    if filter:
        location = (
            (need["docname"], need["lineno"]) if need and need["docname"] else None
        )
        result = filter_needs_and_parts(
            needs.values(),
            NeedsSphinxConfig(app.config),
            filter,
            need,
            location=location,
        )
        if result:
            # the lowest id, so the source does not depend on the order the needs
            # reached the environment (document names, the last build's re-reads, -j)
            need = min(result, key=itemgetter("id"))

    if need is None:
        raise ValueError("Need not found")

    if option not in need:
        raise ValueError(f"Option {option} not found in need {need['id']}")

    if reads is not None:
        reads.note_read(need, option)
    value = need[option]

    if lower:
        return str(value).lower()
    if upper:
        return str(value).upper()

    return value


@records_reads
def check_linked_values(
    app: Sphinx,
    need: NeedItem | NeedPartItem | None,
    needs: NeedsMutable | NeedsView,
    result: Any,
    search_option: str,
    search_value: Any,
    filter_string: str | None = None,
    one_hit: bool = False,
    *,
    reads: UnresolvedReads | None = None,
) -> Any:
    """
    Returns a specific value, if for all linked needs a given option has a given value.

    The linked needs can be filtered by using the ``filter`` option.

    If ``one_hit`` is set to True, only one linked need must have a positive match for the searched value.

    **Examples**

    **Needs used as input data**

    .. syntax-example::

        .. req:: Input A
           :id: clv_A
           :status: in progress

        .. req:: Input B
           :id: clv_B
           :status: in progress

        .. spec:: Input C
           :id: clv_C
           :status: closed

    **Example 1: Positive check**

    Status gets set to *progress*.

    .. syntax-example::

        .. spec:: result 1: Positive check
           :links: clv_A, clv_B
           :status: [[check_linked_values('progress', 'status', 'in progress' )]]
           :collapse: False

    **Example 2: Negative check**

    Status gets not set to *progress*, because status of linked need *clv_C* does not match *"in progress"*.

    .. syntax-example::

        .. spec:: result 2: Negative check
           :links: clv_A, clv_B, clv_C
           :status: [[check_linked_values('progress', 'status', 'in progress' )]]
           :collapse: False

    **Example 3: Positive check thanks of used filter**

    status gets set to *progress*, because linked need *clv_C* is not part of the filter.

    .. syntax-example::

        .. spec:: result 3: Positive check thanks of used filter
           :links: clv_A, clv_B, clv_C
           :status: [[check_linked_values('progress', 'status', 'in progress', 'type == "req" ' )]]
           :collapse: False

    **Example 4: Positive check thanks of one_hit option**

    Even *clv_C* has not the searched status, status gets anyway set to *progress*.
    That's because ``one_hit`` is used so that only one linked need must have the searched
    value.

    .. syntax-example::

        .. spec:: result 4: Positive check thanks of one_hit option
           :links: clv_A, clv_B, clv_C
           :status: [[check_linked_values('progress', 'status', 'in progress', one_hit=True )]]
           :collapse: False

    **Result 5: Two checks and a joint status**
    Two checks are performed and both are positive. So their results get joined.

    .. syntax-example::

        .. spec:: result 5: Two checks and a joint status
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
    if need is None:
        raise ValueError("No need given for check_linked_values")

    needs_config = NeedsSphinxConfig(app.config)
    if reads is not None:
        reads.note_read(need, "links")
    links = need["links"]
    if not isinstance(search_value, list):
        search_value = [search_value]

    for link in links:
        need = needs[link]
        # noted before the filter, which may read a computed field itself and so keep
        # or drop this need by the order the needs are resolved in
        if reads is not None:
            reads.note_read(need, search_option)
        if filter_string:
            try:
                if not filter_single_need(need, needs_config, filter_string):
                    continue
            except Exception as e:
                log_warning(
                    logger,
                    f"CheckLinkedValues: Filter {filter_string} not valid: Error: {e}",
                    "filter",
                    None,
                )

        need_value = need[search_option]
        if not one_hit and need_value not in search_value:
            return None
        elif one_hit and need_value in search_value:
            return result

    return result


@records_reads
def calc_sum(
    app: Sphinx,
    need: NeedItem | NeedPartItem | None,
    needs: NeedsMutable | NeedsView,
    option: str,
    filter: str | None = None,
    links_only: bool = False,
    *,
    reads: UnresolvedReads | None = None,
) -> float:
    """
    Sums the values of a given option in filtered needs up to single number.

    Useful e.g. for calculating the amount of needed hours for implementation of all linked
    specification needs.

    The values are added in ascending need-id order, comparing ids as strings
    (so ``REQ_10`` comes before ``REQ_9``);
    with ``links_only``, in the order the links are written.
    The order can change the last digits of a total of non-integer values,
    so it is fixed rather than left to the order the needs were read in.


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

    .. syntax-example::

       .. req:: Result 1
          :amount: [[calc_sum("hours")]]
          :collapse: False


    **Example 2**

    .. syntax-example::

       .. req:: Result 2
          :amount: [[calc_sum("hours", "hours is not None and hours > 10")]]
          :collapse: False

    **Example 3**

    .. syntax-example::

       .. req:: Result 3
          :links: sum_input_1; sum_input_3
          :amount: [[calc_sum("hours", links_only="True")]]
          :collapse: False

    **Example 4**

    .. syntax-example::

       .. req:: Result 4
          :links: sum_input_1; sum_input_3
          :amount: [[calc_sum("hours", "hours is not None and hours > 10", "True")]]
          :collapse: False

    :param option: Options, from which the numbers shall be taken
    :param filter: Filter string, which all needs must passed to get their value added.
    :param links_only: If "True", only linked needs are taken into account.

    :return: A float number
    """
    if need is None:
        raise ValueError("No need given for calc_sum")

    needs_config = NeedsSphinxConfig(app.config)
    if links_only and reads is not None:
        reads.note_read(need, "links")
    # float addition is not associative, so the order decides a total's last digits:
    # ascending need id (plain string order, not the natural order links are sorted
    # in), so a total does not depend on the order the needs reached the environment;
    # ``links_only`` keeps the order the links are written in
    check_needs = (
        [needs[link] for link in need["links"]]
        if links_only
        else (needs[need_id] for need_id in sorted(needs))
    )

    calculated_sum = 0.0

    for check_need in check_needs:
        # noted before the filter, which may read a computed field itself and so keep
        # or drop this need by the order the needs are resolved in
        if reads is not None:
            reads.note_read(check_need, option)
        if filter:
            try:
                if not filter_single_need(check_need, needs_config, filter):
                    continue
            except ValueError:
                pass
            except NeedsInvalidFilter as ex:
                log_warning(
                    logger,
                    f"Given filter is not valid. Error: {ex}",
                    "filter",
                    None,
                )

        # TODO(mh) added TypeError for None values
        with contextlib.suppress(ValueError, TypeError):
            calculated_sum += float(check_need[option])

    return calculated_sum


def _find_need_refs(node: nodes.Node) -> Iterator[NeedRef]:
    """Yield ``NeedRef`` nodes, without descending into nested ``Need`` nodes."""
    for child in node.children:
        if isinstance(child, NeedRef):
            yield child
        elif not isinstance(child, Need):
            yield from _find_need_refs(child)


def links_from_content(
    app: Sphinx,
    need: NeedItem | NeedPartItem | None,
    needs: NeedsMutable | NeedsView,
    need_id: str | None = None,
    filter: str | None = None,
) -> list[NeedLink]:
    """
    Extracts need references from the content of a need.

    All need-links set by using ``:need:`NEED_ID``` are extracted
    from the parsed doctree node of the source need.

    Same links are only added once.

    .. versionchanged:: 8.0.0

       Previously used a regex on raw RST source text to extract ``:need:`` references.
       Now walks the parsed doctree, which correctly handles custom titles
       (e.g. ``:need:`My Title <REQ_001>```) and nested content.

       This function requires the source need to have a stored doctree node.
       It will emit a warning and return an empty list for needs without a
       stored node (e.g. external needs or need parts).

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
    if need_id:
        source_need_id = need_id
    elif need is None:
        raise ValueError("No need found for links_from_content")
    elif isinstance(need, NeedPartItem):
        location = (need["docname"], need["lineno"]) if need["docname"] else None
        log_warning(
            logger,
            "links_from_content does not support need parts",
            "dynamic_function",
            location=location,
        )
        return []
    else:
        source_need_id = need["id"]

    need_node = SphinxNeedsData(app.env).get_need_node(source_need_id)
    if need_node is None:
        # This can happen for external needs or hidden needs,
        # which do not have a stored doctree node.
        source_need = needs.get(source_need_id)
        if source_need is not None:
            location = (
                (source_need["docname"], source_need["lineno"])
                if source_need["docname"]
                else None
            )
        elif need is not None:
            location = (need["docname"], need["lineno"]) if need["docname"] else None
        else:
            location = None
        log_warning(
            logger,
            f"links_from_content: no stored node for need {source_need_id!r}",
            "dynamic_function",
            location=location,
        )
        return []

    raw_links: list[NeedLink] = []
    for ref_node in _find_need_refs(need_node):
        need_link: NeedLink = ref_node["need_link"]
        if need_link not in raw_links:
            raw_links.append(need_link)

    if filter:
        needs_config = NeedsSphinxConfig(app.config)
        filtered_links: list[NeedLink] = []
        for link in raw_links:
            target = needs.get(link.id)
            if (
                target is not None
                and link not in filtered_links
                and filter_single_need(target, needs_config, filter)
            ):
                filtered_links.append(link)
        return filtered_links

    return raw_links
