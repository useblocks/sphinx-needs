"""The references of ``@need-ids:`` markers, attached to the needs they name.

The ``src-trace`` directive already analyses its files, ``@need-ids:`` markers included.
It turns each into :class:`~sphinx_codelinks.analyse.references.NeedIdRef` records and
keeps them in the environment under the document that hosts the directive
(:func:`need_id_refs_store`): purged with that document, merged from ``-j N`` workers,
pickled with the environment, so an unchanged rebuild re-reads nothing and still attaches.
A project no directive traces has its records made by the configuration pass instead
(``sphinx_extension/rediscovery.py``, which also connects the handlers).

Once every need of every document is known, at Sphinx-Needs'
``needs-before-post-processing`` event, :func:`attach_need_id_refs` gives each referenced
need the list of its references' URLs, in the project's ``ref_url_field``. That event
runs before ``needextend`` is applied, so a user's ``needextend`` of the field wins.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, MutableMapping
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from sphinx.application import Sphinx
from sphinx.environment import BuildEnvironment
from sphinx.util import logging

from sphinx_codelinks.analyse.references import NeedIdRef
from sphinx_codelinks.analyse.utils import find_git_root
from sphinx_codelinks.config import (
    CodeLinksConfig,
    CodeLinksProjectConfigType,
    locate_src_dir,
    need_id_refs_fields,
)
from sphinx_codelinks.sphinx_extension.project_analysis import configured_git_root

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


def project_root(
    confdir: str | Path,
    codelinks_config: CodeLinksConfig,
    project_config: CodeLinksProjectConfigType,
) -> str | None:
    """The directory a project's records' ``path`` is relative to, as POSIX, or ``None``.

    Resolved as the ``src-trace`` directive resolves it: the configured ``git_root``
    (:func:`~sphinx_codelinks.sphinx_extension.project_analysis.configured_git_root`,
    the one function deciding it, so a ``git_root`` the analysis ignores is ignored
    here too), else the git root above the source directory, else the source
    directory. It identifies the FILE behind a record's root-relative ``path`` (two
    repositories may both hold ``src/main.cpp``), so it is configuration of the
    consuming build, never data in the record.
    """
    discover = project_config.get("source_discover_config")
    analyse = project_config.get("analyse_config")
    if discover is None or analyse is None:
        return None
    try:
        src_dir = locate_src_dir(confdir, codelinks_config, discover)
        root = (
            configured_git_root(confdir, codelinks_config, project_config)
            or find_git_root(src_dir)
            or src_dir
        )
    except (OSError, TypeError, ValueError):
        return None
    return root.as_posix()


def project_roots(
    confdir: str | Path, codelinks_config: CodeLinksConfig
) -> dict[str, str]:
    """Each configured project whose root resolves, mapped to it (see :func:`project_root`)."""
    projects = codelinks_config.projects
    if not isinstance(projects, dict):
        return {}
    roots: dict[str, str] = {}
    for name, project_config in projects.items():
        if isinstance(project_config, dict):
            root = project_root(confdir, codelinks_config, project_config)
            if root is not None:
                roots[name] = root
    return roots


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
    ignored_projects: set[str] = field(default_factory=set)
    """The projects of records this build does not attach references for."""


def attach_need_id_refs(
    refs: Iterable[NeedIdRef],
    needs: MutableMapping[str, Any],
    *,
    fields: Mapping[str, str],
    roots: Mapping[str, str] | None = None,
) -> AttachResult:
    """Give each referenced need the URLs of its references.

    This is the seam a pre-analysed input file will feed: it takes the records and the
    needs, whatever produced the records, and nothing about the analysis or the
    directive. ``fields`` maps a project to its ``ref_url_field``; a record of a project
    not in it is ignored, and the project reported in ``ignored_projects``. ``roots``
    maps a project to the directory its records' ``path`` is relative to (configuration,
    like ``fields``); a project without one is a root of its own.

    Records are deduplicated on ``(root, path, lineno, need_id)`` within a field,
    whatever the project -- overlapping ``src-trace`` directives, or two projects whose
    source directories overlap, analyse the same FILE twice; the first project by name
    keeps the reference (and its URL). Files under different roots are different files,
    each kept. Records are ordered by ``(path, lineno, start_column)``. A
    need gets one entry per reference: its remote URL, else its local one; projects
    naming the same field share one list. The need is not marked as modified, and an
    unreferenced need is left alone.
    """
    roots = roots or {}
    unique: dict[tuple[str, str, str, int, str], NeedIdRef] = {}
    ignored_projects: set[str] = set()
    for ref in sorted(refs, key=lambda ref: ref.project):
        if ref.project not in fields:
            ignored_projects.add(ref.project)
            continue
        root = roots.get(ref.project, f"<project {ref.project}>")
        key = (fields[ref.project], root, ref.path, ref.lineno, ref.need_id)
        unique.setdefault(key, ref)
    ordered = sorted(
        unique.values(),
        key=lambda ref: (ref.path, ref.lineno, ref.start_column, ref.project),
    )

    result = AttachResult(ignored_projects=ignored_projects)
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
        urls.append(value)
        result.attached[ref.project] += 1

    for (_need_id, field_name), (need, urls) in values.items():
        need[field_name] = urls
    return result


def attach_and_report(
    app: Sphinx, needs: MutableMapping[str, Any], refs: Iterable[NeedIdRef]
) -> None:
    """Attach ``refs`` to ``needs``, warn about the unknown ids, and report per project."""
    refs = list(refs)
    if not refs:
        return
    codelinks_config = CodeLinksConfig.from_sphinx(app.config)
    fields = need_id_refs_fields(codelinks_config)
    roots = project_roots(app.confdir, codelinks_config)
    result = attach_need_id_refs(refs, needs, fields=fields, roots=roots)

    # one warning per located id, even when two fields cover one file
    warned: set[tuple[str, int, str]] = set()
    for ref in result.unknown:
        if (ref.path, ref.lineno, ref.need_id) in warned:
            continue
        warned.add((ref.path, ref.lineno, ref.need_id))
        logger.warning(
            f"@need-ids reference to unknown need {ref.need_id!r}",
            type="codelinks",
            subtype="need_id_ref",
            location=f"{ref.path}:{ref.lineno}",
        )
    for project in sorted(result.ignored_projects):
        logger.warning(
            f"@need-ids records for project {project!r}, which this build does not "
            "configure, were ignored",
            type="codelinks",
            subtype="need_id_ref",
        )
    unknown = Counter(ref.project for ref in result.unknown)
    for project in sorted(set(result.attached) | set(unknown)):
        logger.info(
            f"codelinks [{project}]: {result.attached[project]} "
            f"reference{'' if result.attached[project] == 1 else 's'} attached, "
            f"{unknown[project]} unknown"
        )
