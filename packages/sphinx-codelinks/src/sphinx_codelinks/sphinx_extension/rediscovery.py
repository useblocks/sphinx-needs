"""What an incremental build learns about source files, without parsing them.

Two stores and two handlers, all in the main process.

The SCOPE store (:func:`scope_store`, env attribute ``codelinks_src_trace_scopes``)
records, under the document hosting each ``src-trace`` directive, the directive's scope
and its :func:`fingerprint`: the discovered files with their modification time and
size. Sphinx's ``note_dependency`` already re-reads the document when a KNOWN file is
edited or removed; a file ADDED to the scope is a dependency of nothing (#2040). So at
``env-get-outdated`` :func:`find_outdated_scopes` walks every recorded scope again (one
directory walk per scope, no parsing) and returns the documents whose scope changed.
The store is also how "a project owns a directive" is known.

The CONFIG-ONLY store (:func:`config_only_refs_store`, env attribute
``codelinks_config_only_refs``) holds, per project that no directive traces, the
``@need-ids:`` records of its whole source directory (ubCode's config-only mode). At
``env-updated`` -- after every document is read and the workers' stores are merged, so
directive ownership is exact -- :func:`update_config_only_refs` fingerprints each such
project and analyses it again only when the fingerprint changed. The scan never creates
needs: there is no directive to own them.

Sphinx pickles the environment only when a document was read or ``env-updated``
returned one. So the ``env-updated`` handler also compares the references the attach
will use (:func:`effective_refs`) with those of the previous build, and returns the
documents holding a need whose references changed: Sphinx then writes them (without
reading them again), so their cards are current, and pickles the environment, so a
source-only change is analysed once. When the changed references name no known need,
nothing is returned, the build may not pickle, and the project is scanned again next
build.
"""

from __future__ import annotations

import weakref
from collections import defaultdict
from collections.abc import Iterable, MutableMapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Any, Literal

from sphinx.application import Sphinx
from sphinx.environment import BuildEnvironment
from sphinx.util import logging

from sphinx_codelinks.analyse.analyse import SourceAnalyse
from sphinx_codelinks.analyse.references import NeedIdRef
from sphinx_codelinks.config import (
    CodeLinksConfig,
    CodeLinksProjectConfigType,
    locate_src_dir,
    need_id_refs_fields,
)
from sphinx_codelinks.source_discover.config import SourceDiscoverConfig
from sphinx_codelinks.source_discover.source_discover import SourceDiscover
from sphinx_codelinks.sphinx_extension.need_id_refs import (
    attach_and_report,
    need_id_refs_store,
)
from sphinx_codelinks.sphinx_extension.project_analysis import (
    collect_need_id_refs,
    prepare_analyse_config,
    url_context,
)
from sphinx_needs.data import SphinxNeedsData

logger = logging.getLogger(__name__)

Fingerprint = tuple[tuple[str, int, int], ...]
"""``(path relative to the scanned directory, POSIX; st_mtime_ns; st_size)``, sorted."""

ScopeKind = Literal["file", "directory"]

SCOPES_ATTRIBUTE = "codelinks_src_trace_scopes"
"""The environment attribute holding the directives' scopes, keyed by host document."""

CONFIG_ONLY_ATTRIBUTE = "codelinks_config_only_refs"
"""The environment attribute holding the config-only records, keyed by project."""


# -- discovery and the fingerprint ---------------------------------------------------


def scope_discover_config(
    src_dir: Path, base: SourceDiscoverConfig, directory: str
) -> SourceDiscoverConfig:
    """The discovery configuration of ``directory`` below a project's ``src_dir``: the
    project's rules (``gitignore``, ``include``, ``exclude``, ``follow_links``,
    ``comment_type``) over that directory."""
    return SourceDiscoverConfig(
        src_dir / directory,
        gitignore=base.gitignore,
        include=base.include,
        exclude=base.exclude,
        follow_links=base.follow_links,
        comment_type=base.comment_type,
    )


def discover_scope(
    src_dir: Path, base: SourceDiscoverConfig, kind: ScopeKind, target: str
) -> list[Path]:
    """The source files of one scope: the ONE discovery function of the extension.

    A ``file`` scope is that file (as written, resolved below ``src_dir``); a
    ``directory`` scope is what :class:`SourceDiscover` finds under it.
    """
    if kind == "file":
        return [(src_dir / target).resolve()]
    return SourceDiscover(scope_discover_config(src_dir, base, target)).source_paths


def scope_relative_path(path: PurePath, root: PurePath) -> str:
    """``path`` relative to ``root``, POSIX on every platform (the path itself, when it
    lies outside ``root`` -- a followed link)."""
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def files_fingerprint(files: Iterable[Path], root: Path) -> Fingerprint:
    """The fingerprint of discovered ``files``, their paths relative to ``root``.

    :raises OSError: if a file cannot be ``stat``-ed.
    """
    entries = []
    for path in files:
        stat = path.stat()
        entries.append(
            (scope_relative_path(path, root), stat.st_mtime_ns, stat.st_size)
        )
    return tuple(sorted(entries))


def fingerprint(discover_config: SourceDiscoverConfig) -> Fingerprint:
    """What discovery finds under ``discover_config``, with modification times and
    sizes: a pure function of the configuration and the file system, no parsing."""
    root = discover_config.src_dir.resolve()
    return files_fingerprint(SourceDiscover(discover_config).source_paths, root)


def file_fingerprint(src_dir: Path, file: str) -> Fingerprint:
    """The fingerprint of a ``:file:`` scope: that one file, or ``()`` if it is missing."""
    path = (src_dir / file).resolve()
    if not path.is_file():
        return ()
    return files_fingerprint([path], src_dir.resolve())


def scope_fingerprint(
    src_dir: Path, base: SourceDiscoverConfig, kind: ScopeKind, target: str
) -> Fingerprint:
    """The fingerprint of one scope, from :func:`discover_scope`."""
    if kind == "file":
        return file_fingerprint(src_dir, target)
    files = discover_scope(src_dir, base, kind, target)
    return files_fingerprint(files, (src_dir / target).resolve())


# -- the scope store -----------------------------------------------------------------


@dataclass(frozen=True)
class ScopeRecord:
    """One ``src-trace`` directive's scope, as it was when the directive ran."""

    project: str
    kind: ScopeKind
    target: str
    """The ``:file:`` or ``:directory:`` option as written, ``"./"`` when neither."""
    fingerprint: Fingerprint


def scope_store(env: BuildEnvironment) -> dict[str, list[ScopeRecord]]:
    """The directives' scopes kept in ``env``, by the name of the hosting document."""
    store: dict[str, list[ScopeRecord]] | None = getattr(env, SCOPES_ATTRIBUTE, None)
    if store is None:
        store = {}
        setattr(env, SCOPES_ATTRIBUTE, store)
    return store


def directive_owned(env: BuildEnvironment) -> set[str]:
    """The projects at least one ``src-trace`` directive traces."""
    return {scope.project for scopes in scope_store(env).values() for scope in scopes}


def purge_doc(_app: Sphinx, env: BuildEnvironment, docname: str) -> None:
    """Drop a document's records and scopes before it is read again, or when it is
    removed (``env-purge-doc``)."""
    need_id_refs_store(env).pop(docname, None)
    scope_store(env).pop(docname, None)


def merge_info(
    _app: Sphinx,
    env: BuildEnvironment,
    docnames: Iterable[str],
    other: BuildEnvironment,
) -> None:
    """Take over the records and scopes of the documents a ``-j N`` worker read
    (``env-merge-info``)."""
    for store in (need_id_refs_store, scope_store):
        mine: dict[str, Any] = store(env)
        theirs: dict[str, Any] = store(other)
        for docname in docnames:
            if docname in theirs:
                mine[docname] = theirs[docname]


# -- the config-only store -----------------------------------------------------------


@dataclass(frozen=True)
class ConfigOnlyScan:
    """A config-only project's records, and the fingerprint they were made from."""

    fingerprint: Fingerprint
    records: list[NeedIdRef]


def config_only_refs_store(env: BuildEnvironment) -> dict[str, ConfigOnlyScan]:
    """The config-only records kept in ``env``, by project.

    Written in the main process only (at ``env-updated``), so never merged; keyed by
    project, not by document, so never purged. An entry of a project a directive traces
    now is ignored, not deleted: if the directive goes away and the files are unchanged,
    the records are still right.
    """
    store: dict[str, ConfigOnlyScan] | None = getattr(env, CONFIG_ONLY_ATTRIBUTE, None)
    if store is None:
        store = {}
        setattr(env, CONFIG_ONLY_ATTRIBUTE, store)
    return store


def effective_refs(env: BuildEnvironment, config: CodeLinksConfig) -> list[NeedIdRef]:
    """The records the attach uses: every directive's, plus the config-only records of
    each gated project that no directive traces."""
    store = need_id_refs_store(env)
    refs = [ref for docname in sorted(store) for ref in store[docname]]
    gated = need_id_refs_fields(config)
    owned = directive_owned(env)
    config_only = config_only_refs_store(env)
    for project in sorted(config_only):
        if project in gated and project not in owned:
            refs.extend(config_only[project].records)
    return refs


class ConfigOnlyError(Exception):
    """Why a config-only project could not be scanned."""


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def scan_config_only_project(
    app: Sphinx,
    codelinks_config: CodeLinksConfig,
    project: str,
    project_config: CodeLinksProjectConfigType,
    previous: ConfigOnlyScan | None,
) -> ConfigOnlyScan:
    """The records of a project's whole source directory, analysed again only when
    its fingerprint differs from ``previous``'s.

    The analysis is the directive's, through the same preparation and record builder;
    its one-line needs are counted and never created.

    :raises ConfigOnlyError: if the source directory does not exist.
    """
    discover_config = project_config["source_discover_config"]
    src_dir = locate_src_dir(app.confdir, codelinks_config, discover_config)
    if not src_dir.is_dir():
        raise ConfigOnlyError(f"source directory {src_dir.as_posix()} does not exist")
    files = discover_scope(src_dir, discover_config, "directory", "./")
    found = files_fingerprint(files, src_dir)
    if previous is not None and previous.fingerprint == found:
        return previous
    if not files:
        # nothing to parse, so no git lookup and no line either (as ubCode)
        return ConfigOnlyScan(found, [])

    analyse_config = prepare_analyse_config(
        app.confdir,
        codelinks_config,
        project_config["analyse_config"],
        src_dir=src_dir,
        src_files=files,
    )
    src_analyse = SourceAnalyse(analyse_config, name=project)
    src_analyse.run(log_summary=False)
    context = url_context(
        codelinks_config, project_config, src_analyse, src_dir, Path(app.outdir)
    )
    records = collect_need_id_refs(src_analyse, project, context)
    not_created = sum(1 for need in src_analyse.oneline_needs if need.need)
    line = (
        f"codelinks [{project}]: {_plural(len(src_analyse.src_files), 'file')}, "
        f"{_plural(len(records), 'reference')}"
    )
    if not_created:
        line += (
            f", {_plural(not_created, 'one-line need')} not created "
            "(no src-trace directive)"
        )
    logger.info(line)
    return ConfigOnlyScan(found, records)


def update_config_only_refs(
    app: Sphinx, env: BuildEnvironment, codelinks_config: CodeLinksConfig
) -> None:
    """Scan every gated project no directive traces; one warning per failing project,
    and the build goes on (ubCode's rule)."""
    projects = codelinks_config.projects
    if not isinstance(projects, dict):
        return
    store = config_only_refs_store(env)
    owned = directive_owned(env)
    for project in sorted(need_id_refs_fields(codelinks_config)):
        if project in owned:
            continue
        try:
            store[project] = scan_config_only_project(
                app, codelinks_config, project, projects[project], store.get(project)
            )
        except Exception as error:  # discovery or parse: never fatal, always said
            store.pop(project, None)
            logger.warning(
                f"codelinks [{project}]: cannot scan for @need-ids references: {error}",
                type="codelinks",
                subtype="need_id_ref",
            )


# -- the handlers --------------------------------------------------------------------

#: each build's references before its read, from ``env-get-outdated`` to
#: ``env-updated`` -- in memory only, so never pickled
_PREVIOUS_REFS: weakref.WeakKeyDictionary[BuildEnvironment, list[NeedIdRef]] = (
    weakref.WeakKeyDictionary()
)


def _scope_changed(
    app: Sphinx,
    codelinks_config: CodeLinksConfig,
    scope: ScopeRecord,
    memo: dict[tuple[str, ScopeKind, str], Fingerprint | None],
) -> bool:
    """Whether ``scope``'s files differ from when it was recorded; a project no longer
    configured, or a scope that cannot be walked, counts as changed (the re-read lets
    the directive report it)."""
    projects = codelinks_config.projects
    project_config = projects.get(scope.project) if isinstance(projects, dict) else None
    if not isinstance(project_config, dict):
        return True
    try:
        discover_config = project_config["source_discover_config"]
        src_dir = locate_src_dir(app.confdir, codelinks_config, discover_config)
    except (KeyError, OSError, TypeError, ValueError):
        return True
    key = (src_dir.as_posix(), scope.kind, scope.target)
    if key not in memo:
        try:
            memo[key] = scope_fingerprint(
                src_dir, discover_config, scope.kind, scope.target
            )
        except OSError:
            memo[key] = None
    return memo[key] is None or memo[key] != scope.fingerprint


def find_outdated_scopes(
    app: Sphinx,
    env: BuildEnvironment,
    added: set[str],
    changed: set[str],
    removed: set[str],
) -> list[str]:
    """The documents whose ``src-trace`` scopes gained, lost or changed a file
    (``env-get-outdated``; Sphinx adds them to ``changed``).

    First, before Sphinx purges the removed documents, it keeps the references the
    previous build attached, for :func:`find_affected_documents`.
    """
    codelinks_config = CodeLinksConfig.from_sphinx(app.config)
    _PREVIOUS_REFS[env] = effective_refs(env, codelinks_config)
    skip = added | changed | removed
    memo: dict[tuple[str, ScopeKind, str], Fingerprint | None] = {}
    return [
        docname
        for docname, scopes in sorted(scope_store(env).items())
        if docname in env.found_docs
        and docname not in skip
        and any(_scope_changed(app, codelinks_config, scope, memo) for scope in scopes)
    ]


def _values_by_need(refs: Iterable[NeedIdRef]) -> dict[str, list[tuple[str, str]]]:
    values: defaultdict[str, list[tuple[str, str]]] = defaultdict(list)
    for ref in refs:
        values[ref.need_id].append((ref.remote_url or "", ref.local_url or ""))
    return {need_id: sorted(urls) for need_id, urls in values.items()}


def changed_need_ids(
    previous: Sequence[NeedIdRef], current: Sequence[NeedIdRef]
) -> set[str]:
    """The ids whose references differ: a moved line, an added or removed reference."""
    before = _values_by_need(previous)
    after = _values_by_need(current)
    return {
        need_id
        for need_id in before.keys() | after.keys()
        if before.get(need_id) != after.get(need_id)
    }


def find_affected_documents(app: Sphinx, env: BuildEnvironment) -> list[str]:
    """Scan the config-only projects, then return the documents holding a need whose
    references changed in this build (``env-updated``; Sphinx writes them, and pickles
    the environment). An id no need has contributes nothing."""
    codelinks_config = CodeLinksConfig.from_sphinx(app.config)
    update_config_only_refs(app, env, codelinks_config)
    previous = _PREVIOUS_REFS.pop(env, [])
    affected = changed_need_ids(previous, effective_refs(env, codelinks_config))
    if not affected:
        return []
    try:
        # the read phase's accessor: it never triggers post-processing
        needs = SphinxNeedsData(env).get_needs_mutable()
    except RuntimeError:  # already post-processed: nothing left to write for
        return []
    docnames: set[str] = set()
    for need_id in affected:
        need = needs.get(need_id)
        docname = need.get("docname") if need is not None else None
        if isinstance(docname, str):
            docnames.add(docname)
    return sorted(docnames & env.found_docs)


def attach_on_post_processing(app: Sphinx, needs: MutableMapping[str, Any]) -> None:
    """Attach :func:`effective_refs` (``needs-before-post-processing``) -- the same
    records the ``env-updated`` comparison saw."""
    codelinks_config = CodeLinksConfig.from_sphinx(app.config)
    attach_and_report(app, needs, effective_refs(app.env, codelinks_config))
