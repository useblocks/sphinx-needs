"""
Collection of common sphinx-needs functions for dynamic values

.. note:: The function parameters ``app``, ``need``, ``needs`` are set automatically and can not be overridden by user.
   The keyword-only ``reads`` of the functions marked ``records_reads`` is reserved too:
   do not give it in a call (doing so fails the call).
"""

from __future__ import annotations

import contextlib
import hashlib
import json
from collections.abc import Callable, Collection, Iterable, Iterator, Mapping
from operator import itemgetter
from typing import Any

from docutils import nodes
from sphinx.application import Sphinx

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import NeedsMutable, SphinxNeedsData
from sphinx_needs.derive import DeriveRule
from sphinx_needs.exceptions import NeedsInvalidFilter
from sphinx_needs.filter_common import (
    filter_needs_and_parts,
    filter_single_need,
)
from sphinx_needs.functions.functions import UnresolvedReads, records_reads
from sphinx_needs.logging import log_warning
from sphinx_needs.need_item import (
    NeedItem,
    NeedLink,
    NeedPartItem,
    _link_natural_sort_key,
)
from sphinx_needs.needs_schema import FieldSchema, FieldsSchema, LinkSchema
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
    :param upper: Is set to True, copied value will be uppercase (each item, for a list)
    :param lower: Is set to True, copied value will be lowercase (each item, for a list)
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
            origin_docname=need["docname"] if need else None,
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

    if isinstance(value, list | tuple) and (lower or upper):
        # each item of a list, not the list's printed form
        return [str(item).lower() if lower else str(item).upper() for item in value]
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

    A link to a need part (``REQ_1.a``) checks the part's need,
    and a link to no need is skipped.

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
        # a link to a need part (``ID.part``) reads the part's need; a link to no need
        # is skipped (it is reported as a dead link)
        if (target_id := NeedLink.parse_address(link).id) not in needs:
            continue
        need = needs[target_id]
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

        if reads is not None:
            reads.note_read(need, search_option)
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
    with ``links_only``, in the order the links are written,
    a link to a need part (``REQ_1.a``) adding the part's need and a link to no need
    skipped.
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
    # ``links_only`` keeps the order the links are written in, and a link to a need
    # part (``ID.part``) reads the part's need
    check_needs = (
        [
            needs[target_id]
            for link in need["links"]
            # a link to no need is skipped (it is reported as a dead link)
            if (target_id := NeedLink.parse_address(link).id) in needs
        ]
        if links_only
        else [needs[need_id] for need_id in sorted(needs)]
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
                log_warning(
                    logger,
                    f"Given filter is not valid. Error: {ex}",
                    "filter",
                    None,
                )

        if reads is not None:
            reads.note_read(check_need, option)
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


def links_from_filter(
    app: Sphinx,
    need: NeedItem | NeedPartItem | None,
    needs: NeedsMutable | NeedsView,
    filter: str,
    include_self: bool = False,
    include_parts: bool = False,
) -> list[NeedLink]:
    """
    Links to every need that passes a :ref:`filter string <filter_string>`.

    .. versionadded:: 9.0.0

    The linked needs come in need-id order, comparing ids as strings
    (so ``REQ_10`` comes before ``REQ_9``); the link list is sorted for the output anyway.
    It is the per-need spelling of a :ref:`derived link type <needs_derive>` of the kind
    ``links``.

    The need that contains the call is not linked, even if it passes the filter, and
    neither are its own parts: set ``include_self=True`` to keep them.
    Only whole needs are candidates: set ``include_parts=True`` to test the parts of
    every need as well, each after its need, in part-id order; a part that passes the
    filter is linked as ``<need id>.<part id>``.
    No need passing the filter gives no links; an empty filter is an error, as it would
    link every need.

    .. syntax-example::

        .. req:: Open requirement
           :id: LFF_REQ_1
           :status: open

           Contains a part: :np:`(p1) open part`

        .. req:: Another open requirement
           :id: LFF_REQ_2
           :status: open

        .. spec:: Collector of open needs
           :id: LFF_SPEC_1
           :status: open
           :links: [[links_from_filter("status == 'open' and id.startswith('LFF_')")]]

           Links to ``LFF_REQ_1`` and ``LFF_REQ_2``, but not to itself.

        .. spec:: Collector of requirements and their parts
           :id: LFF_SPEC_2
           :links: [[links_from_filter("id_parent.startswith('LFF_REQ')", include_parts=True)]]

           Links to ``LFF_REQ_1``, ``LFF_REQ_1.p1`` and ``LFF_REQ_2``.

    ``current_need`` in the filter is the need that contains the call, and
    ``c.this_doc()`` selects the needs in its document: for example,
    ``c.this_doc() and sections == current_need["sections"]`` links to the needs in the
    same chapter of the same file.
    The filter is computed with the link fields, so it must not read a field that is
    computed after them (see :ref:`needs_processing_order`).

    :param filter: :ref:`filter_string`, which a need must pass to be linked.
    :param include_self: If True, the current need and its own parts are linked too, if they pass the filter.
    :param include_parts: If True, the parts of every need are candidates as well.
    :return: The links to the needs (and parts) that pass the filter.
    """
    if not isinstance(filter, str) or not filter.strip():
        raise ValueError(
            "links_from_filter needs a non-empty filter, as it would otherwise link every need"
        )
    candidates = _every_need_and_part(needs, include_parts=include_parts)
    location = (need["docname"], need["lineno"]) if need and need["docname"] else None
    found = filter_needs_and_parts(
        candidates,
        NeedsSphinxConfig(app.config),
        filter,
        need,
        location=location,
        origin_docname=need["docname"] if need else None,
    )
    return _links_to(found, need, include_self=include_self)


def _every_need_and_part(
    needs: NeedsMutable | NeedsView, *, include_parts: bool
) -> list[NeedItem | NeedPartItem]:
    """Every need in need-id order, with its parts after it in part-id order if asked."""
    candidates: list[NeedItem | NeedPartItem] = []
    for need_id in sorted(needs):
        candidate = needs[need_id]
        candidates.append(candidate)
        if include_parts:
            candidates.extend(
                sorted(candidate.iter_part_items(), key=lambda part: part["id"])
            )
    return candidates


def _links_to(
    found: Iterable[NeedItem | NeedPartItem],
    reader: NeedItem | NeedPartItem | None,
    *,
    include_self: bool,
) -> list[NeedLink]:
    """The links to the needs and parts found, in their order, each once.

    The reader and its own parts are left out unless ``include_self``.
    """
    reader_id = None if reader is None else reader["id_complete"]
    links: list[NeedLink] = []
    for result in found:
        if (
            not include_self
            and reader_id is not None
            and (
                result["id_complete"] == reader_id
                or (result["is_part"] and result["id_parent"] == reader_id)
            )
        ):
            continue
        link = (
            NeedLink(id=result["id_parent"], part=result["id"])
            if result["is_part"]
            else NeedLink(id=result["id"])
        )
        if link not in links:
            links.append(link)
    return links


# -- the derived fields: a rule's value for one need ---------------------------------
#
# ``resolve_functions`` gives every derived field of a need from the project's sources
# its rule (a ``DeriveCall``) and computes it like a ``[[…]]`` of the kind's stratum;
# ``execute_rule`` is that computation. The reads it makes are noted for the check of
# the order, as the built-in functions note theirs.


def execute_rule(
    app: Sphinx,
    need: NeedItem,
    needs: NeedsMutable | NeedsView,
    rule: DeriveRule,
    field_schema: FieldSchema | LinkSchema,
    schema: FieldsSchema,
    *,
    reads: UnresolvedReads | None = None,
    cache: dict[Any, Any] | None = None,
) -> Any:
    """Compute the value of one derived field of one need.

    :param need: The need.
    :param needs: Every need.
    :param rule: The field's rule.
    :param field_schema: The field's schema.
    :param schema: The schema of every field.
    :param reads: The record of the reads, as for a built-in function.
    :param cache: What a ``transitive`` rule computes once per pass, shared by the needs.
    :return: The value: the empty value of the field's type when the rule finds none
        (``None`` for a nullable field), a list of links for a link type.
    :raises ValueError: If the rule cannot be computed on this need: ``from`` names no
        need, or a ``where`` / ``test`` cannot be evaluated on a candidate.
    """
    config = NeedsSphinxConfig(app.config)
    link_fields = frozenset(schema.iter_link_field_names())
    if rule.kind == "links":
        return _rule_links(need, needs, rule, config)
    if rule.kind == "content_links":
        return links_from_content(
            app, need, needs, need_id=rule.from_need, filter=rule.where
        )
    if rule.kind == "hash":
        return _rule_hash(need, rule, link_fields, reads)
    if rule.kind == "copy" and rule.over is None:
        source = need
        if rule.from_need is not None:
            if rule.from_need not in needs:
                raise ValueError(f"'from' names no need: {rule.from_need!r}")
            source = needs[rule.from_need]
        assert rule.field is not None, "copy has a field"
        if reads is not None:
            reads.note_read(source, rule.field)
        return _or_empty(source[rule.field], field_schema)

    if rule.transitive:
        return _rule_transitive(
            need, needs, rule, field_schema, schema, link_fields, config, reads, cache
        )
    assert rule.over is not None, "every other kind has an over"
    candidates = [
        candidate
        for candidate in over_candidates(need, rule.over, needs, link_fields)
        if _passes(candidate, rule.where, config, reads)
    ]
    match rule.kind:
        case "copy":
            return _rule_copy_over(need, candidates, rule, field_schema, reads)
        case "count":
            if rule.field is None:
                return len(candidates)
            return sum(1 for c in candidates if _read(c, rule.field, reads) is not None)
        case "any" | "all":
            if rule.test is not None:
                hits = [_passes(c, rule.test, config, reads) for c in candidates]
            else:
                assert rule.field is not None, "any and all have a field or a test"
                hits = [_read(c, rule.field, reads) is True for c in candidates]
            return any(hits) if rule.kind == "any" else all(hits)
        case "sum":
            assert rule.field is not None, "sum has a field"
            return _sum(
                [_read(c, rule.field, reads) for c in candidates],
                integer=_type_of(schema, rule.field) == "integer",
            )
        case "min" | "max":
            assert rule.field is not None, "min and max have a field"
            values = [_read(c, rule.field, reads) for c in candidates]
            return _or_empty(
                _extremum(rule.kind, values, _order_of(schema, rule.field)),
                field_schema,
            )
        case "collect":
            assert rule.field is not None, "collect has a field"
            collected: list[Any] = []
            for candidate in candidates:
                for value in _items(_read(candidate, rule.field, reads)):
                    if value not in collected:
                        collected.append(value)
            return collected
    raise ValueError(f"unknown kind {rule.kind!r}")


def over_candidates(
    need: NeedItem,
    over: str,
    needs: Mapping[str, NeedItem] | NeedsView,
    link_fields: Collection[str],
) -> list[NeedItem]:
    """The needs a rule's ``over`` names on ``need``, in the order a rule reads them.

    For a link type, the needs its links name, in the order written, a need named twice
    read twice; a link to a part reads the part's need, and a link to no need is
    skipped. For ``<link type>_back``, the needs that link to ``need``, in need-id
    order, each once.
    """
    if over.endswith("_back") and over[:-5] in link_fields:
        ids = sorted({NeedLink.parse_address(link).id for link in need[over]})
    else:
        ids = [NeedLink.parse_address(link).id for link in need[over]]
    return [needs[need_id] for need_id in ids if need_id in needs]


def _read(candidate: NeedItem, name: str, reads: UnresolvedReads | None) -> Any:
    if reads is not None:
        reads.note_read(candidate, name)
    return candidate[name]


def _passes(
    candidate: NeedItem | NeedPartItem,
    predicate: str | None,
    config: NeedsSphinxConfig,
    reads: UnresolvedReads | None,
) -> bool:
    """Whether a ``where`` / ``test`` holds on a candidate (no predicate: it does).

    :raises ValueError: If it cannot be evaluated on the candidate.
    """
    if predicate is None:
        return True
    if reads is not None:
        # imported here, as the order module imports this one
        from sphinx_needs.functions.order import filter_names

        for name in filter_names(predicate).names:
            if name in candidate:
                reads.note_read(candidate, name)
    try:
        return filter_single_need(candidate, config, predicate)
    except NeedsInvalidFilter as err:
        raise ValueError(f"on need {candidate['id']!r}: {err}") from err


def _or_empty(value: Any, field_schema: FieldSchema | LinkSchema) -> Any:
    """``value``, or the field's empty value for ``None``."""
    if value is not None:
        return value
    # imported here, as the order module imports this one
    from sphinx_needs.functions.order import typed_empty

    return typed_empty(field_schema)


def _items(value: Any) -> list[Any]:
    """A value's items: a list's, else the value itself (none for ``None``)."""
    if value is None:
        return []
    if isinstance(value, list | tuple):
        return [item for item in value if item is not None]
    return [value]


def _type_of(schema: FieldsSchema, name: str) -> str | None:
    """The schema type of the field ``name`` reads, if it is a field."""
    field = schema.get_extra_field(name) or schema.get_core_field(name)
    return None if field is None else field.type


def _order_of(schema: FieldsSchema, name: str) -> Callable[[Any], Any] | None:
    """How ``min`` / ``max`` order the values of a field: numbers by value, an enum by
    its declared order; ``None`` for a value outside the order."""
    field = schema.get_extra_field(name) or schema.get_core_field(name)
    if field is not None and field.type == "string":
        enum = list(field.schema.get("enum", ()))
        return lambda value: enum.index(value) if value in enum else None
    return lambda value: (
        value
        if isinstance(value, int | float) and not isinstance(value, bool)
        else None
    )


def _extremum(
    kind: str, values: Iterable[Any], order: Callable[[Any], Any] | None
) -> Any:
    """The least (``min``) or greatest (``max``) value, skipping unset ones."""
    best: Any = None
    best_key: Any = None
    for value in values:
        key = None if order is None or value is None else order(value)
        if key is None:
            continue
        if best_key is None or (key < best_key if kind == "min" else key > best_key):
            best, best_key = value, key
    return best


def _sum(values: Iterable[Any], *, integer: bool) -> int | float:
    """The total of the numbers, in the order given; unset and non-numbers skipped."""
    total: int | float = 0 if integer else 0.0
    for value in values:
        if isinstance(value, bool) or not isinstance(value, int | float):
            continue
        total += value if integer else float(value)
    return total


def _rule_copy_over(
    need: NeedItem,
    targets: list[NeedItem],
    rule: DeriveRule,
    field_schema: FieldSchema | LinkSchema,
    reads: UnresolvedReads | None,
) -> Any:
    """``copy`` over a link type: the lowest-id target that sets the field, or every value."""
    assert rule.field is not None, "copy has a field"
    if rule.select == "list":
        values: list[Any] = []
        for target in targets:
            values.extend(_items(_read(target, rule.field, reads)))
        return values
    setting = sorted(
        {t["id"]: t for t in targets if _read(t, rule.field, reads) is not None}.items()
    )
    if not setting:
        return _or_empty(None, field_schema)
    if rule.select == "unique" and len(setting) > 1:
        log_warning(
            logger,
            f"derive rule 'copy' for option {field_schema.name!r} found "
            f"{len(setting)} needs setting {rule.field!r} "
            f"({', '.join(need_id for need_id, _ in setting)}); "
            f"the lowest id, {setting[0][0]!r}, is copied",
            "derive_unique",
            location=(need["docname"], need["lineno"]) if need["docname"] else None,
        )
    return setting[0][1][rule.field]


def _rule_hash(
    need: NeedItem,
    rule: DeriveRule,
    link_fields: Collection[str],
    reads: UnresolvedReads | None,
) -> str:
    """The lowercase hex SHA-256 of the listed fields, as one compact JSON array.

    Each value as ``needs.json`` writes it: a link list sorted and without duplicates;
    no whitespace in the JSON, non-ASCII characters not escaped, numbers as Python
    writes them (``3.0``, ``1e+16``).
    """
    values: list[Any] = []
    for name in rule.fields:
        if name in link_fields:
            if reads is not None:
                reads.note_read(need, name)
            links = sorted(
                set(need.get_links(name, as_str=False)), key=_link_natural_sort_key
            )
            values.append([link.to_filter_string() for link in links])
        else:
            value = _read(need, name, reads)
            values.append(list(value) if isinstance(value, tuple) else value)
    text = json.dumps(values, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _rule_links(
    need: NeedItem,
    needs: NeedsMutable | NeedsView,
    rule: DeriveRule,
    config: NeedsSphinxConfig,
) -> list[NeedLink]:
    """``links``: every need (and part) passing ``where``, in need-id order."""
    assert rule.where is not None, "links has a where"
    found = [
        candidate
        for candidate in _every_need_and_part(needs, include_parts=rule.include_parts)
        if _passes(candidate, rule.where, config, None)
    ]
    return _links_to(found, need, include_self=rule.include_self)


def _rule_transitive(
    need: NeedItem,
    needs: NeedsMutable | NeedsView,
    rule: DeriveRule,
    field_schema: FieldSchema | LinkSchema,
    schema: FieldsSchema,
    link_fields: Collection[str],
    config: NeedsSphinxConfig,
    reads: UnresolvedReads | None,
    cache: dict[Any, Any] | None,
) -> Any:
    """``min`` / ``max`` closed over ``over``: every need reachable from ``need``.

    The needs are grouped into strongly connected components once per pass and link
    type: a need on a cycle reaches itself, so every member of a component reaches the
    same needs and shares the value. ``include_self`` adds the need's own value.
    """
    assert rule.over is not None and rule.field is not None, "a roll-up"
    field = rule.field
    if cache is None:
        cache = {}
    graph_key = ("graph", rule.over)
    if (graph := cache.get(graph_key)) is None:
        graph = cache[graph_key] = _Reach(needs, rule.over, link_fields)
    order = _order_of(schema, field)
    best_key = ("best", rule.kind, rule.over, field, rule.where)
    best: dict[int, Any] = cache.setdefault(best_key, {})

    def value_of(need_id: str) -> Any:
        candidate = needs[need_id]
        if not _passes(candidate, rule.where, config, reads):
            return None
        return _read(candidate, field, reads)

    reached = graph.best(graph.component[need.id], rule.kind, order, value_of, best)
    own = value_of(need.id) if rule.include_self else None
    return _or_empty(_extremum(rule.kind, [reached, own], order), field_schema)


class _Reach:
    """The needs reachable through one link type, by strongly connected component."""

    def __init__(
        self,
        needs: NeedsMutable | NeedsView,
        over: str,
        link_fields: Collection[str],
    ) -> None:
        # imported here, as the order module imports this one
        from sphinx_needs.functions.order import strongly_connected

        ids = sorted(needs)
        index = {need_id: i for i, need_id in enumerate(ids)}
        edges: list[list[int] | None] = [
            [
                index[target["id"]]
                for target in over_candidates(needs[need_id], over, needs, link_fields)
            ]
            or None
            for need_id in ids
        ]
        components = strongly_connected(edges)
        self.ids = ids
        self.component: dict[str, int] = {}
        for number, members in enumerate(components):
            for member in members:
                self.component[ids[member]] = number
        self.members: list[list[str]] = [
            sorted(ids[m] for m in members) for members in components
        ]
        #: per component, whether its members reach themselves (a cycle)
        self.cyclic: list[bool] = [
            len(members) > 1 or members[0] in (edges[members[0]] or ())
            for members in components
        ]
        #: per component, the components its members link to, besides itself
        self.successors: list[list[int]] = [
            sorted(
                {
                    self.component[ids[target]]
                    for member in members
                    for target in edges[member] or ()
                }
                - {number}
            )
            for number, members in enumerate(components)
        ]

    def best(
        self,
        start: int,
        kind: str,
        order: Callable[[Any], Any] | None,
        value_of: Callable[[str], Any],
        memo: dict[int, Any],
    ) -> Any:
        """The extremum over the needs the members of ``start`` reach, memoised.

        Computed bottom-up from ``start`` only: the values read are those of the needs
        reached, which the order has computed before this need.
        """
        stack = [start]
        while stack:
            number = stack[-1]
            if number in memo:
                stack.pop()
                continue
            pending = [s for s in self.successors[number] if s not in memo]
            if pending:
                stack.extend(pending)
                continue
            stack.pop()
            values = [
                value
                for successor in self.successors[number]
                for value in (
                    memo[successor],
                    *(value_of(m) for m in self.members[successor]),
                )
            ]
            if self.cyclic[number]:
                values.extend(value_of(m) for m in self.members[number])
            memo[number] = _extremum(kind, values, order)
        return memo[start]
