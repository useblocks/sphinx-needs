"""The references of ``@need-ids:`` markers, attached to the needs they name.

The ``src-trace`` directive already analyses its files, ``@need-ids:`` markers included.
It turns each into :class:`~sphinx_codelinks.analyse.references.NeedIdRef` records and
keeps them in the environment under the document that hosts the directive
(:func:`need_id_refs_store`): purged with that document, merged from ``-j N`` workers,
pickled with the environment, so an unchanged rebuild re-reads nothing and still attaches.

Once every need of every document is known, at Sphinx-Needs'
``needs-before-post-processing`` event, :func:`attach_need_id_refs` gives each referenced
need the list of its references' URLs, in the project's ``ref_url_field``. That event
runs before ``needextend`` is applied, so a user's ``needextend`` of the field wins.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, MutableMapping
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any

from sphinx.application import Sphinx
from sphinx.environment import BuildEnvironment
from sphinx.util import logging

from sphinx_codelinks.analyse.references import NeedIdRef
from sphinx_codelinks.config import CodeLinksConfig, need_id_refs_fields

logger = logging.getLogger(__name__)

ENV_ATTRIBUTE = "codelinks_need_id_refs"
"""The environment attribute holding the records, keyed by host document."""


def need_id_refs_store(env: BuildEnvironment) -> dict[str, list[NeedIdRef]]:
    """The records kept in ``env``, by the name of the document hosting the directive."""
    store: dict[str, list[NeedIdRef]] | None = getattr(env, ENV_ATTRIBUTE, None)
    if store is None:
        store = {}
        setattr(env, ENV_ATTRIBUTE, store)
    return store


def purge_doc(_app: Sphinx, env: BuildEnvironment, docname: str) -> None:
    """Drop a document's records before it is read again, or when it is removed."""
    need_id_refs_store(env).pop(docname, None)


def merge_info(
    _app: Sphinx,
    env: BuildEnvironment,
    docnames: Iterable[str],
    other: BuildEnvironment,
) -> None:
    """Take over the records of the documents a ``-j N`` worker read."""
    mine = need_id_refs_store(env)
    theirs = need_id_refs_store(other)
    for docname in docnames:
        if docname in theirs:
            mine[docname] = theirs[docname]


def resolve_need_id(need_id: str, needs: Mapping[str, Any]) -> Any | None:
    """The need a reference names, or ``None``.

    The ONE place a referenced id is looked up: the id is matched as written, ``::`` and
    ``.`` included, so that a path-aware resolver can replace this function alone.
    """
    return needs.get(need_id)


def _local_value(local_url: str | None, docname: str | None) -> str | None:
    """A local URL, relative to the document the need is in (as ``local-url`` is)."""
    if local_url is None:
        return None
    depth = len(PurePosixPath(docname).parents) - 1 if docname else 0
    return "../" * depth + local_url


@dataclass
class AttachResult:
    """What :func:`attach_need_id_refs` did, per project."""

    attached: Counter[str] = field(default_factory=Counter)
    """The number of references attached, per project."""
    unknown: list[NeedIdRef] = field(default_factory=list)
    """The references naming an id no need has."""


def attach_need_id_refs(
    refs: Iterable[NeedIdRef],
    needs: MutableMapping[str, Any],
    *,
    fields: Mapping[str, str],
) -> AttachResult:
    """Give each referenced need the URLs of its references.

    This is the seam a pre-analysed input file will feed: it takes the records and the
    needs, whatever produced the records, and nothing about the analysis or the
    directive. ``fields`` maps a project to its ``ref_url_field``; a record of a project
    not in it is ignored.

    Records are deduplicated on ``(project, path, lineno, need_id)`` -- overlapping
    ``src-trace`` directives analyse the same file twice -- and ordered by
    ``(path, lineno, start_column)``. A need gets one entry per reference: its remote URL,
    else its local one; projects naming the same field share one list. The need is not
    marked as modified, and an unreferenced need is left alone.
    """
    unique: dict[tuple[str, str, int, str], NeedIdRef] = {}
    for ref in refs:
        if ref.project in fields:
            unique.setdefault((ref.project, ref.path, ref.lineno, ref.need_id), ref)
    ordered = sorted(
        unique.values(),
        key=lambda ref: (ref.path, ref.lineno, ref.start_column, ref.project),
    )

    result = AttachResult()
    values: dict[tuple[str, str], tuple[Any, list[str]]] = {}
    for ref in ordered:
        need = resolve_need_id(ref.need_id, needs)
        if need is None:
            result.unknown.append(ref)
            continue
        value = ref.remote_url or _local_value(ref.local_url, need.get("docname"))
        if value is None:
            continue
        _need, urls = values.setdefault((ref.need_id, fields[ref.project]), (need, []))
        if value not in urls:
            urls.append(value)
        result.attached[ref.project] += 1

    for (_need_id, field_name), (need, urls) in values.items():
        need[field_name] = urls
    return result


def attach_on_post_processing(app: Sphinx, needs: MutableMapping[str, Any]) -> None:
    """Attach the stored records (``needs-before-post-processing``), warn about the
    unknown ids, and report per project."""
    fields = need_id_refs_fields(CodeLinksConfig.from_sphinx(app.config))
    if not fields:
        return
    store = need_id_refs_store(app.env)
    refs = [ref for docname in sorted(store) for ref in store[docname]]
    result = attach_need_id_refs(refs, needs, fields=fields)

    for ref in result.unknown:
        logger.warning(
            f"@need-ids reference to unknown need {ref.need_id!r}",
            type="codelinks",
            subtype="need_id_ref",
            location=f"{ref.path}:{ref.lineno}",
        )
    unknown = Counter(ref.project for ref in result.unknown)
    for project in sorted(set(result.attached) | set(unknown)):
        logger.info(
            f"codelinks [{project}]: {result.attached[project]} "
            f"reference{'' if result.attached[project] == 1 else 's'} attached, "
            f"{unknown[project]} unknown"
        )
