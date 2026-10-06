"""What an incremental build learns about source files, without parsing them.

Three stores and two handlers, all in the main process.

The SCOPE store (:func:`scope_store`, env attribute ``codelinks_src_trace_scopes``)
records, under the document hosting each ``src-trace`` directive, the directive's scope
and its :func:`fingerprint`: the discovered files with their modification time and
size. Sphinx's ``note_dependency`` already re-reads the document when a KNOWN file is
edited or removed; a file ADDED to the scope is a dependency of nothing (#2040). So at
``env-get-outdated`` :func:`find_outdated_scopes` walks every recorded scope again (one
directory walk per scope, no parsing) and returns the documents whose scope changed.
The store is also how "a project owns a directive" is known, and where a directive
records the one-line needs it skipped because another document already defined them
(``ScopeRecord.deferred``): that document changing or going re-reads the skipping one,
so the need moves rather than vanishes.

The CONFIG-ONLY store (:func:`config_only_refs_store`, env attribute
``codelinks_config_only_refs``) holds, per project that no directive traces, the
``@need-ids:`` records of its whole source directory (ubCode's config-only mode). At
``env-updated`` -- after every document is read and the workers' stores are merged, so
directive ownership is exact -- :func:`update_config_only_refs` fingerprints each such
project and analyses it again only when the fingerprint changed. The scan never creates
needs: there is no directive to own them.

The PAGES store (:func:`source_pages_store`, env attribute ``codelinks_source_pages``)
holds, under the document hosting each ``src-trace`` directive, the
:class:`~sphinx_codelinks.sphinx_extension.project_analysis.SourcePage` of each file its
local URLs name; a config-only project's ride in its ``ConfigOnlyScan``. Every HTML
build copies and pages them all at ``html-collect-pages`` (:func:`effective_pages`), so
the output directory is build state: a cleaned one, a second builder's, or a document a
``-j N`` worker read gets its pages, whether or not the document is read again.

Sphinx pickles the environment only when a document was read or ``env-updated``
returned one. So the ``env-updated`` handler also compares the references the attach
will use (:func:`effective_refs`) with those of the previous build, and returns the
documents holding a need whose references changed: Sphinx then writes them (without
reading them again), so their cards are current, and pickles the environment. A build
that analysed a project again but affects no need's document returns the root document,
so that the new scan is kept: a source-only change is analysed once.
"""

from __future__ import annotations

import os
import weakref
from collections import defaultdict
from collections.abc import Iterable, MutableMapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Any, Literal

from sphinx.application import Sphinx
from sphinx.environment import CONFIG_OK, BuildEnvironment
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
from sphinx_codelinks.source_discover.source_discover import (
    SourceDiscover,
    lies_within,
    warn_outside_src_dir,
)
from sphinx_codelinks.sphinx_extension.need_id_refs import (
    attach_and_report,
    need_id_refs_store,
)
from sphinx_codelinks.sphinx_extension.project_analysis import (
    SourcePage,
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

SOURCE_PAGES_ATTRIBUTE = "codelinks_source_pages"
"""The environment attribute holding the directives' source pages, keyed by host
document."""


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


def build_output_dirs(app: Sphinx) -> tuple[Path, ...]:
    """The directories discovery never traces: the build's output and doctree
    directories, and each one's parent when that parent lies strictly inside the
    documentation source directory -- the build directory, ``_build/`` in the Makefile
    layout (``_build/<builder>`` beside ``_build/doctrees``), so one builder never
    traces another builder's copies. A parent outside the source directory (``-d
    /tmp/x``), or the source directory itself, is not excluded."""
    srcdir = Path(app.srcdir).resolve()
    dirs = [Path(app.outdir).resolve(), Path(app.doctreedir).resolve()]
    for directory in list(dirs):
        parent = directory.parent
        if parent != srcdir and parent.is_relative_to(srcdir) and parent not in dirs:
            dirs.append(parent)
    return tuple(dirs)


def _outside(files: Iterable[Path], exclude: Sequence[Path]) -> list[Path]:
    """``files`` (resolved) that lie under none of ``exclude``."""
    # strings, not ``Path.is_relative_to``: that costs as much as the walk itself over
    # thousands of files; ``normcase`` keeps case-insensitive platforms honest
    prefixes = tuple(
        os.path.join(os.path.normcase(str(directory.resolve())), "")
        for directory in exclude
    )
    if not prefixes:
        return list(files)
    return [
        path for path in files if not os.path.normcase(str(path)).startswith(prefixes)
    ]


def discover_scope(
    src_dir: Path,
    base: SourceDiscoverConfig,
    kind: ScopeKind,
    target: str,
    *,
    exclude: Sequence[Path],
    warn: bool = True,
) -> list[Path]:
    """The source files of one scope: the ONE discovery function of the extension.

    A ``file`` scope is that file (as written, resolved below ``src_dir``); a
    ``directory`` scope is what :class:`SourceDiscover` finds under it, less every file
    under ``exclude`` -- the build's output and doctree directories
    (:func:`build_output_dirs`): a source directory that contains them would otherwise
    trace the extension's own copies of the sources.

    Either way a file that resolves to outside ``src_dir`` (resolved) is not a source
    of the scope, and a warning names its path as written unless ``warn`` is false
    (#2062): an existing ``:file:`` target there gives an empty scope. A ``:file:``
    target that is no file gives one too, silently here: the directive says so, at
    its own location (#2069).
    """
    if kind == "file":
        path = (src_dir / target).resolve()
        if not path.is_file():
            return []
        if not lies_within(path, src_dir.resolve()):
            if warn:
                warn_outside_src_dir(src_dir / target, path, src_dir.resolve())
            return []
        return [path]
    found = SourceDiscover(
        scope_discover_config(src_dir, base, target), boundary=src_dir, warn=warn
    ).source_paths
    return _outside(found, exclude)


def scope_relative_path(path: PurePath, root: PurePath) -> str:
    """``path`` relative to ``root``, POSIX on every platform (the path itself, when it
    lies outside ``root``: a file a ``:directory:`` scope reaches through a link to
    elsewhere below ``src_dir`` -- discovery lists no file outside ``src_dir`` itself,
    #2062)."""
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


def fingerprint(
    discover_config: SourceDiscoverConfig, *, exclude: Sequence[Path]
) -> Fingerprint:
    """What discovery finds under ``discover_config`` (less the files under
    ``exclude``), with modification times and sizes: a pure function of the
    configuration and the file system, no parsing."""
    root = discover_config.src_dir.resolve()
    found = _outside(SourceDiscover(discover_config).source_paths, exclude)
    return files_fingerprint(found, root)


def file_fingerprint(src_dir: Path, file: str) -> Fingerprint:
    """The fingerprint of a ``:file:`` scope: that one file, or ``()`` if it is missing
    or lies outside ``src_dir`` (an empty scope, as :func:`discover_scope` has it)."""
    path = (src_dir / file).resolve()
    root = src_dir.resolve()
    if not path.is_file() or not lies_within(path, root):
        return ()
    return files_fingerprint([path], root)


def scope_fingerprint(
    src_dir: Path,
    base: SourceDiscoverConfig,
    kind: ScopeKind,
    target: str,
    *,
    exclude: Sequence[Path],
) -> Fingerprint:
    """The fingerprint of one scope, from :func:`discover_scope` -- which warns
    nothing here: the directive warns when it reads the scope, and this walk is
    followed by that read whenever the scope changed."""
    if kind == "file":
        return file_fingerprint(src_dir, target)
    files = discover_scope(src_dir, base, kind, target, exclude=exclude, warn=False)
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
    deferred: tuple[tuple[str, str], ...] = ()
    """``(need id, owning document)`` of each one-line need the directive did not create
    because another document defines it (``""``: an external need). A default, so that
    a record pickled before the field existed loads and defers nothing."""


def scope_store(env: BuildEnvironment) -> dict[str, list[ScopeRecord]]:
    """The directives' scopes kept in ``env``, by the name of the hosting document."""
    store: dict[str, list[ScopeRecord]] | None = getattr(env, SCOPES_ATTRIBUTE, None)
    if store is None:
        store = {}
        setattr(env, SCOPES_ATTRIBUTE, store)
    return store


def source_pages_store(env: BuildEnvironment) -> dict[str, list[SourcePage]]:
    """The source pages the directives recorded in ``env``, by the name of the hosting
    document."""
    store: dict[str, list[SourcePage]] | None = getattr(
        env, SOURCE_PAGES_ATTRIBUTE, None
    )
    if store is None:
        store = {}
        setattr(env, SOURCE_PAGES_ATTRIBUTE, store)
    return store


def directive_owned(env: BuildEnvironment) -> set[str]:
    """The projects at least one ``src-trace`` directive traces."""
    return {scope.project for scopes in scope_store(env).values() for scope in scopes}


#: the documents a build has yet to read, from ``env-before-read-docs`` on: a document
#: leaves when it is purged, which Sphinx does right before reading it (serial) or for
#: every document before the workers fork (``-j N``). In memory only, so never pickled;
#: a forked worker inherits it
_UNREAD: weakref.WeakKeyDictionary[BuildEnvironment, set[str]] = (
    weakref.WeakKeyDictionary()
)


def note_documents_to_read(env: BuildEnvironment, docnames: Iterable[str]) -> None:
    """Keep the documents this build reads (``env-before-read-docs``)."""
    _UNREAD[env] = set(docnames)


def is_unread(env: BuildEnvironment, docname: str) -> bool:
    """Whether ``docname`` is still to be read in this build: its needs in the store
    are the previous build's, about to be purged."""
    return docname in _UNREAD.get(env, ())


def purge_doc(_app: Sphinx, env: BuildEnvironment, docname: str) -> None:
    """Drop a document's records, scopes and source pages before it is read again, or
    when it is removed (``env-purge-doc``)."""
    need_id_refs_store(env).pop(docname, None)
    scope_store(env).pop(docname, None)
    source_pages_store(env).pop(docname, None)
    _UNREAD.get(env, set()).discard(docname)


def merge_info(
    _app: Sphinx,
    env: BuildEnvironment,
    docnames: Iterable[str],
    other: BuildEnvironment,
) -> None:
    """Take over the records, scopes and source pages of the documents a ``-j N``
    worker read (``env-merge-info``)."""
    for store in (need_id_refs_store, scope_store, source_pages_store):
        mine: dict[str, Any] = store(env)
        theirs: dict[str, Any] = store(other)
        for docname in docnames:
            if docname in theirs:
                mine[docname] = theirs[docname]


# -- the config-only store -----------------------------------------------------------


@dataclass(frozen=True)
class ConfigOnlyScan:
    """A config-only project's records and source pages, and the fingerprint they were
    made from."""

    fingerprint: Fingerprint
    records: list[NeedIdRef]
    pages: tuple[SourcePage, ...] = ()
    """The pages of the files the records' local URLs name. A plain default, so that the
    class attribute exists and a scan pickled before the field existed loads and pages
    nothing (a ``default_factory`` leaves no class attribute)."""


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


def _effective_scans(
    env: BuildEnvironment, config: CodeLinksConfig
) -> list[ConfigOnlyScan]:
    """The config-only scans in use: those of each gated project no directive traces."""
    gated = need_id_refs_fields(config)
    owned = directive_owned(env)
    config_only = config_only_refs_store(env)
    return [
        config_only[project]
        for project in sorted(config_only)
        if project in gated and project not in owned
    ]


def effective_refs(env: BuildEnvironment, config: CodeLinksConfig) -> list[NeedIdRef]:
    """The records the attach uses: every directive's, plus the config-only records of
    each gated project that no directive traces."""
    store = need_id_refs_store(env)
    refs = [ref for docname in sorted(store) for ref in store[docname]]
    for scan in _effective_scans(env, config):
        refs.extend(scan.records)
    return refs


def effective_pages(env: BuildEnvironment, config: CodeLinksConfig) -> list[SourcePage]:
    """The source pages an HTML build writes, one per target, sorted by it: every
    directive's, plus those of the config-only scans :func:`effective_refs` uses. A
    target recorded more than once (two directives tracing one file) is one page with
    every record's anchors; its source is the first record's."""
    store = source_pages_store(env)
    recorded = [page for docname in sorted(store) for page in store[docname]]
    for scan in _effective_scans(env, config):
        recorded.extend(scan.pages)
    merged: dict[str, tuple[str, set[tuple[int, str, str]]]] = {}
    for page in recorded:
        _source, anchors = merged.setdefault(page.target, (page.source, set()))
        anchors.update(page.anchors)
    return [
        SourcePage(source, target, tuple(sorted(anchors)))
        for target, (source, anchors) in sorted(merged.items())
    ]


class ConfigOnlyError(Exception):
    """Why a config-only project could not be scanned."""


#: what discovery and the analysis raise for a project they cannot scan: a missing
#: source directory (``ConfigOnlyError``); a file that cannot be stat-ed, read or
#: copied (``OSError``); an unsupported comment style, an undecodable file
#: (``ValueError``; a ``git_root`` that does not contain ``src_dir`` is ignored since
#: #2062, and a file outside ``src_dir`` is not discovered); libclang absent with a
#: preprocessor configured (``ImportError``); a symlink loop in ``Path.resolve()`` on
#: Python 3.11/3.12 (``RuntimeError``). Anything else is a bug in the extension and
#: fails the build, as it does on the directive path.
_SCAN_ERRORS = (ConfigOnlyError, OSError, ValueError, ImportError, RuntimeError)


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
    files = discover_scope(
        src_dir, discover_config, "directory", "./", exclude=build_output_dirs(app)
    )
    found = files_fingerprint(files, src_dir)
    if previous is not None and previous.fingerprint == found:
        return previous
    if not files:
        # nothing to parse, so no git lookup and no line either (as ubCode)
        return ConfigOnlyScan(found, [])

    analyse_config = prepare_analyse_config(
        app.confdir,
        codelinks_config,
        project_config,
        src_dir=src_dir,
        src_files=files,
    )
    src_analyse = SourceAnalyse(analyse_config, name=project)
    src_analyse.run(log_summary=False)
    context = url_context(
        codelinks_config, project_config, src_analyse, src_dir, Path(app.outdir)
    )
    records, pages = collect_need_id_refs(src_analyse, project, context)
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
    return ConfigOnlyScan(found, records, tuple(pages))


def update_config_only_refs(
    app: Sphinx, env: BuildEnvironment, codelinks_config: CodeLinksConfig
) -> bool:
    """Scan every gated project no directive traces; one warning per failing project,
    and the build goes on (ubCode's rule). A configuration change drops every stored
    entry first.

    :return: Whether a project was analysed again (a new entry stored). A failing scan
        drops its entry and does not count: it will fail again next build.
    """
    projects = codelinks_config.projects
    if not isinstance(projects, dict):
        return False
    store = config_only_refs_store(env)
    if env.config_status != CONFIG_OK:
        # the fingerprint covers the files only, and every confval a record depends on
        # re-reads every document when it changes: start again too (entries of projects
        # a directive owns now included, or one would be reused stale when it goes)
        store.clear()
    owned = directive_owned(env)
    analysed = False
    for project in sorted(need_id_refs_fields(codelinks_config)):
        if project in owned:
            continue
        previous = store.get(project)
        try:
            scan = scan_config_only_project(
                app, codelinks_config, project, projects[project], previous
            )
        except _SCAN_ERRORS as error:
            store.pop(project, None)
            logger.warning(
                f"codelinks [{project}]: cannot scan for @need-ids references: "
                f"{type(error).__name__}: {error}",
                type="codelinks",
                subtype="need_id_ref",
            )
            continue
        analysed = analysed or scan is not previous
        store[project] = scan
    return analysed


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
                src_dir,
                discover_config,
                scope.kind,
                scope.target,
                exclude=build_output_dirs(app),
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
    """The documents whose ``src-trace`` scopes gained, lost or changed a file, and
    those that skipped a one-line need whose owning document is read again or removed
    (``env-get-outdated``; Sphinx adds them to ``changed``).

    First, before Sphinx purges the removed documents, it keeps the references the
    previous build attached, for :func:`find_affected_documents`.
    """
    codelinks_config = CodeLinksConfig.from_sphinx(app.config)
    _PREVIOUS_REFS[env] = effective_refs(env, codelinks_config)
    skip = added | changed | removed
    memo: dict[tuple[str, ScopeKind, str], Fingerprint | None] = {}
    candidates = [
        (docname, scopes)
        for docname, scopes in sorted(scope_store(env).items())
        if docname in env.found_docs and docname not in skip
    ]
    rescoped = {
        docname
        for docname, scopes in candidates
        if any(_scope_changed(app, codelinks_config, scope, memo) for scope in scopes)
    }
    # an owner read again may no longer define the need (its scope narrowed, or the
    # file left it), and a removed one defines nothing: the skipping document must
    # look again. Decided on the previous build's facts -- nothing is purged yet
    moving = changed | removed | rescoped
    return [
        docname
        for docname, scopes in candidates
        if docname in rescoped
        or any(owner in moving for scope in scopes for _id, owner in scope.deferred)
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
    the environment). An id no need has contributes nothing.

    When a project was analysed again but no need's document is affected (an edit that
    moves no known need's reference), the root document is returned instead: one page
    written, so that Sphinx pickles the environment and the next build finds the new
    fingerprint rather than analysing the project again.
    """
    codelinks_config = CodeLinksConfig.from_sphinx(app.config)
    analysed = update_config_only_refs(app, env, codelinks_config)
    root_doc = app.config.root_doc
    keep = [root_doc] if analysed and root_doc in env.found_docs else []
    previous = _PREVIOUS_REFS.pop(env, [])
    affected = changed_need_ids(previous, effective_refs(env, codelinks_config))
    if not affected:
        return keep
    try:
        # the read phase's accessor: it never triggers post-processing
        needs = SphinxNeedsData(env).get_needs_mutable()
    except RuntimeError:
        # another env-updated handler resolved the needs before this one (it is
        # connected early for that reason): their documents cannot be told apart now
        logger.debug("codelinks: needs already post-processed at env-updated")
        return keep
    docnames: set[str] = set()
    for need_id in affected:
        need = needs.get(need_id)
        docname = need.get("docname") if need is not None else None
        if isinstance(docname, str):
            docnames.add(docname)
    return sorted(docnames & env.found_docs) or keep


def attach_on_post_processing(app: Sphinx, needs: MutableMapping[str, Any]) -> None:
    """Attach :func:`effective_refs` (``needs-before-post-processing``) -- the same
    records the ``env-updated`` comparison saw."""
    codelinks_config = CodeLinksConfig.from_sphinx(app.config)
    attach_and_report(app, needs, effective_refs(app.env, codelinks_config))
