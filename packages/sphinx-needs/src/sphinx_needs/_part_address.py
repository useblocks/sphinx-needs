"""Where a need is expected, a part address reads as its need.

The first rule of ``design/parts-contract.md``, for places that are given the id of ONE
need and read that need: the target of ``:need_outgoing:`` and ``:need_incoming:``, the
argument of needuml's ``uml()`` and ``flow()``, a needsequence start, the ``need_id`` of
``copy``, the argument of needextract (and of needextend, which refuses a part), and
needflow's ``root_id``. Two places that read a LINK look its target up through it too,
whole first as they did, then as a link is read: needflow's root walk and a schema's
network rule. :func:`need_at` is the one lookup they share; each place keeps its own
report of an address that does not resolve.
"""

from __future__ import annotations

from collections.abc import Mapping

from sphinx_needs.need_item import NeedItem, NeedLink


def need_at(needs: Mapping[str, NeedItem], address: str, /) -> NeedItem | None:
    """The need *address* names where a need is expected, or ``None``.

    An address naming a need whole is that need, as it always was (a need id holding a
    ``.`` included: what such an id means is not settled, so it is not changed here).
    Any other address is split as a link's address is
    (:meth:`~sphinx_needs.need_item.NeedLink.parse_address`: at its first ``.``, a
    namespace staying with the need's id), and names the need when the need has the
    part. A part the need does not have names nothing, as an id naming no need does:
    the caller reports it as it reports such an id, naming the address as written. No
    condition is taken off: ``REQ_1.p1[cond]`` names the part ``p1[cond]``.

    :param needs: The needs, by id.
    :param address: A need id, or ``<need id>.<part id>``.
    """
    if (need := needs.get(address)) is not None:
        return need
    link = NeedLink.parse_address(address)
    if link.part is None or (need := needs.get(link.id)) is None:
        return None
    return need if need.get_part(link.part) is not None else None
