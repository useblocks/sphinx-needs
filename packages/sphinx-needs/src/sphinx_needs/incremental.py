"""Re-write the pages that show a need which changed, on an incremental build.

Sphinx re-reads the documents whose sources changed, and writes those. A page may also
show needs of other documents -- a needtable lists them, a ``:need:`` role names one,
a need's links show their targets' titles and its back links its sources' -- so when a
need changes, those pages are re-written too (never re-read: their doctrees still hold
the views, which are resolved again from the needs when the page is written).

What changed is decided on the needs as they were READ: the needs of every document
purged are kept aside (:func:`stash_purged_doc`, before ``purge_needs`` drops them) and,
once every document is read, compared with what the documents gave this time
(:func:`get_updated_docs`). The needs cannot be resolved there -- back links, dynamic
functions, ``derive`` rules and ``needextend`` are applied when the pages are written,
after the environment is pickled, which must hold them unresolved -- so the rules below
follow what a resolution reads, and fall back to every need-relevant page where they
cannot tell.

When something changed, the pages re-written are:

- every view: the documents of each :data:`VIEW_CATEGORIES` category, whose filters are
  not evaluated here;
- the pages of the *affected* needs: the needs that changed, the needs a changed
  ``needextend`` names by id, every need computing a value with a dynamic function (its
  arguments may name any need), and every need whose ``derive`` rule reads an affected
  need -- over its links, over its back links, or ``from`` it -- until no more is (a
  rule reading needs it does not name, a ``join`` say, is affected by any change);
- the pages of their link targets, old and new, which show them as back links;
- the pages of the needs linking to them, which show their titles;
- the pages whose need roles name any of those needs.

A changed ``needextend`` with a filter, or a need whose links are computed from other
needs (a dynamic function in a link field, a ``links`` rule), can affect needs that
cannot be named before the needs are resolved: then every need-relevant page is
re-written. Nothing changed -- an edit of prose only -- re-writes nothing more.
Needs from ``needs_external_needs`` are not compared (#353).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from typing import Final

from sphinx.application import Sphinx
from sphinx.environment import BuildEnvironment

from sphinx_needs.data import NeedsExtendType, SphinxNeedsData
from sphinx_needs.derive import Derive, DeriveRule
from sphinx_needs.functions.functions import DynamicFunctionParsed
from sphinx_needs.logging import get_logger
from sphinx_needs.need_item import NeedItem, NeedLink
from sphinx_needs.needs_schema import (
    FieldFunctionArray,
    FieldsSchema,
    LinksFunctionArray,
    LinksLiteralValue,
)

LOGGER = get_logger(__name__)

#: The document categories (``add_doc``) of the views: what they show is computed from
#: the needs when the page is written, from a filter this module does not evaluate, so
#: their pages are re-written on every change.
VIEW_CATEGORIES: Final = (
    "needtable",
    "needlist",
    "needflow",
    "needgantt",
    "needsequence",
    "needpie",
    "needbar",
    "needextract",
    "needuml",
    "needreport",
    "need_count",
    "need_func",
)

#: The derive kinds computing a link list whose targets are not named by the need's
#: own links: every need a ``where`` or a ``join`` selects.
_UNNAMED_LINK_KINDS: Final = frozenset({"links"})

#: The derive kinds reading nothing but the need itself.
_OWN_KINDS: Final = frozenset({"union", "hash", "fingerprint"})


@dataclass(slots=True)
class _Stash:
    """The needs, extends and role references of the documents purged this build."""

    docs: set[str] = field(default_factory=set)
    needs: dict[str, NeedItem] = field(default_factory=dict)
    extends: dict[str, NeedsExtendType] = field(default_factory=dict)
    role_refs: dict[str, set[str]] = field(default_factory=dict)


_STASH_ATTR: Final = "_needs_incremental_stash"


def _stash(app: Sphinx) -> _Stash:
    # kept on the application, not the environment: it is this build's alone, and must
    # neither be pickled nor be sent back by every parallel reader
    stash: _Stash | None = getattr(app, _STASH_ATTR, None)
    if stash is None:
        stash = _Stash()
        setattr(app, _STASH_ATTR, stash)
    return stash


def stash_purged_doc(app: Sphinx, env: BuildEnvironment, docname: str) -> None:
    """Keep aside what a purged document gave, before ``purge_needs`` drops it.

    Connected to ``env-purge-doc``, which Sphinx emits for every document it is about to
    re-read and every removed one, in the main process also on a parallel read.
    """
    data = SphinxNeedsData(env)
    if data.needs_is_post_processed:
        # the needs are resolved already (a second build of one application): there is
        # nothing as read to compare with, and ``purge_needs`` refuses anyway
        return
    stash = _stash(app)
    stash.docs.add(docname)
    for need_id, need in data._env_needs.items():
        if need.is_in_document(docname):
            stash.needs.setdefault(need_id, need)
    for extend_id, extend in data.get_or_create_extends().items():
        if extend["docname"] == docname:
            stash.extends.setdefault(extend_id, extend)
    if (refs := data.get_or_create_role_refs().get(docname)) is not None:
        stash.role_refs.setdefault(docname, refs)


def get_updated_docs(app: Sphinx, env: BuildEnvironment) -> list[str]:
    """The documents to re-write because a need they show changed.

    Connected to ``env-get-updated``, which Sphinx emits once every document is read and
    before the environment is pickled.
    """
    stash: _Stash | None = getattr(app, _STASH_ATTR, None)
    if stash is None:
        return []
    delattr(app, _STASH_ATTR)
    data = SphinxNeedsData(env)
    if data.needs_is_post_processed:
        return []
    docs = _dependents(data, stash)
    if not docs:
        return []
    found = env.all_docs
    updated = sorted(doc for doc in docs if doc in found and doc not in stash.docs)
    LOGGER.debug(f"needs changed: re-writing {len(updated)} document(s)")
    return updated


def _dependents(data: SphinxNeedsData, stash: _Stash) -> set[str]:
    """The documents showing a need that changed; empty when none changed."""
    needs = data._env_needs
    extends = data.get_or_create_extends()
    all_docs = data.get_or_create_docs()
    role_refs = data.get_or_create_role_refs()

    # the needs as read: those of the re-read documents, compared with what they were
    changed = {
        need_id for need_id, old in stash.needs.items() if needs.get(need_id) != old
    }
    changed.update(
        need_id
        for need_id, need in needs.items()
        if need_id not in stash.needs and need["docname"] in stash.docs
    )
    new_extends = {
        key: value for key, value in extends.items() if value["docname"] in stash.docs
    }
    changed_extends = [
        extend
        for key in stash.extends.keys() | new_extends.keys()
        if stash.extends.get(key) != new_extends.get(key)
        for extend in (stash.extends.get(key), new_extends.get(key))
        if extend is not None
    ]
    if not changed and not changed_extends:
        return set()

    everything = set(all_docs.get("all", []))
    if any(not extend["filter_is_id"] for extend in changed_extends):
        # a filter selects needs by their resolved values
        return everything
    if any(_links_unnamed(extend) for extend in extends.values()):
        # an extend linking needs to a computed target
        return everything

    schema = data.get_schema()
    by_type: dict[str, _Reads] = {}
    reads = {need_id: _reads(need, schema, by_type) for need_id, need in needs.items()}
    if any(r is not None and r.unnamed_links for r in reads.values()):
        # links computed to needs that are not known before the needs are resolved
        return everything

    # every version of a need, as it was and as it is: both are shown somewhere
    versions: dict[str, list[NeedItem]] = {}
    for need in (*stash.needs.values(), *needs.values()):
        versions.setdefault(need["id"], []).append(need)
    # the needs an extend by id links its need to, and those every filter links to
    extend_links: dict[str, set[str]] = {}
    filter_links: set[str] = set()
    for extend in extends.values():
        if extend["filter_is_id"]:
            extend_links.setdefault(_target_id(extend), set()).update(
                _extend_link_ids(extend)
            )
        else:
            filter_links.update(_extend_link_ids(extend))

    def link_targets(need_id: str) -> set[str]:
        """The needs an affected need's back links appear on, every version."""
        found = set(extend_links.get(need_id, ()))
        for need in versions.get(need_id, ()):
            found.update(_link_ids(need))
            if (r := reads.get(need_id)) is not None and r.content_links:
                # a ``content_links`` rule links the needs its content names
                found.update(role_refs.get(need["docname"] or "", ()))
                found.update(stash.role_refs.get(need["docname"] or "", ()))
        return found

    # the affected needs: those that changed, those an extend that changed names, and
    # those computing a value from a need affected (until no more is)
    affected = set(changed)
    affected.update(_target_id(extend) for extend in changed_extends)
    affected.update(
        need_id for need_id, r in reads.items() if r is not None and r.always
    )
    targets = set(filter_links)
    for need_id in affected:
        targets.update(link_targets(need_id))
    pending = {
        need_id: r
        for need_id, r in reads.items()
        if r is not None and need_id not in affected
    }
    grown = True
    while grown and pending:
        grown = False
        for need_id, r in list(pending.items()):
            if (
                (r.links and not affected.isdisjoint(_link_ids(needs[need_id])))
                or (r.back and need_id in targets)
                or not affected.isdisjoint(r.needs)
            ):
                del pending[need_id]
                affected.add(need_id)
                targets.update(link_targets(need_id))
                grown = True

    # the needs showing an affected need's title in their links
    linking = {
        need_id
        for need_id, need in needs.items()
        if not affected.isdisjoint(_link_ids(need))
        or (
            (r := reads[need_id]) is not None
            and r.content_links
            and not affected.isdisjoint(role_refs.get(need["docname"] or "", ()))
        )
    }
    for need_id, linked in extend_links.items():
        if not affected.isdisjoint(linked):
            linking.add(need_id)
    if not affected.isdisjoint(filter_links):
        # the needs a filter links to an affected need are not known here
        return everything

    shown = affected | targets | linking
    docs: set[str] = set()
    for category in VIEW_CATEGORIES:
        docs.update(all_docs.get(category, ()))
    for need_id in shown:
        for need in versions.get(need_id, ()):
            if docname := need["docname"]:
                docs.add(docname)
    docs.update(
        docname for docname, refs in role_refs.items() if not shown.isdisjoint(refs)
    )
    return docs


def _target_id(extend: NeedsExtendType) -> str:
    """The id of the need an extend names (``filter_is_id``), without a part."""
    return NeedLink.parse_address(extend["filter"]).id


def _link_ids(need: NeedItem) -> Iterable[str]:
    """The ids of the needs a need links to as read, every link type."""
    for _, links in need.iter_links_items(as_str=False):
        for link in links:
            yield link.id


def _extend_link_ids(extend: NeedsExtendType) -> Iterable[str]:
    """The ids of the needs an extend links to, literally."""
    for _, _, value in extend["list_modifications"]:
        if isinstance(value, LinksLiteralValue):
            yield from (link.id for link in value.value)
        else:
            yield from (item.id for item in value.value if isinstance(item, NeedLink))


def _links_unnamed(extend: NeedsExtendType) -> bool:
    """Whether an extend links to a need it does not name: a dynamic function."""
    return any(
        isinstance(value, LinksFunctionArray)
        and any(isinstance(item, DynamicFunctionParsed) for item in value.value)
        for _, _, value in extend["list_modifications"]
    )


@dataclass(slots=True)
class _Reads:
    """What of other needs a need's computed values read."""

    always: bool = False
    """Needs it does not name: a dynamic function, a ``join``, a ``where`` over
    candidates it does not link, a ``transitive`` rule, a rule over computed links."""
    links: bool = False
    """The needs its links name (``over`` a link type)."""
    back: bool = False
    """The needs linking to it (``over`` a ``<link type>_back``)."""
    needs: set[str] = field(default_factory=set)
    """The needs a ``from`` names."""
    content_links: bool = False
    """It links the needs its content names (``content_links``)."""
    unnamed_links: bool = False
    """It links needs it does not name: a dynamic function in a link field, a
    ``links`` rule, a ``content_links`` rule reading another need's content."""


def _reads(
    need: NeedItem, schema: FieldsSchema, by_type: dict[str, _Reads]
) -> _Reads | None:
    """What of other needs a need's computed values read; ``None`` for nothing.

    :param by_type: What the ``derive`` rules of each need type read, filled as the
        types are met.
    """
    reads = _Reads()
    if not (need["is_import"] or need["is_external"]):
        # no rule runs on an imported or external need
        need_type = need["type"]
        if (of_type := by_type.get(need_type)) is None:
            of_type = by_type[need_type] = _Reads()
            for derived in (*schema.iter_extra_fields(), *schema.iter_link_fields()):
                if derived.derived:
                    _read_rule(derived.rule_for(need_type), schema, of_type)
        reads = replace(of_type, needs=set(of_type.needs))
    for name, value in _dynamic_fields(need).items():
        if not any(isinstance(item, DynamicFunctionParsed) for item in value.value):
            continue
        if isinstance(value, LinksFunctionArray) or schema.get_link_field(name):
            reads.unnamed_links = True
        else:
            reads.always = True
    if reads == _Reads():
        return None
    return reads


def _read_rule(rule: Derive | None, schema: FieldsSchema, reads: _Reads) -> None:
    """Add what a ``derive`` rule reads of other needs to ``reads``."""
    if not isinstance(rule, DeriveRule) or rule.kind in _OWN_KINDS:
        return
    if rule.kind in _UNNAMED_LINK_KINDS or (
        rule.kind == "content_links" and rule.from_need is not None
    ):
        reads.unnamed_links = True
        return
    if rule.kind == "content_links":
        reads.content_links = True
        if rule.where is not None:
            # the needs its content names, read by the filter: a role's target
            reads.always = True
        return
    if rule.from_need is not None:
        reads.needs.add(NeedLink.parse_address(rule.from_need).id)
    if rule.join is not None or rule.transitive:
        reads.always = True
    if rule.over is not None:
        link_type = rule.over.removesuffix("_back")
        link = schema.get_link_field(link_type)
        if link is None or link.derived:
            # links computed when the needs are resolved
            reads.always = True
        elif rule.over.endswith("_back"):
            reads.back = True
        else:
            reads.links = True


def _dynamic_fields(
    need: NeedItem,
) -> Mapping[str, FieldFunctionArray | LinksFunctionArray]:
    return need._dynamic_fields
