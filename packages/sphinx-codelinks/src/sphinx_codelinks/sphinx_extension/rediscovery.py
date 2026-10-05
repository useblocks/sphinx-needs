"""What an incremental build learns about source files, without parsing them.

The SCOPE store (:func:`scope_store`, env attribute ``codelinks_src_trace_scopes``)
records, under the document hosting each ``src-trace`` directive, the directive's scope
and its :func:`fingerprint`: the discovered files with their modification time and
size. Sphinx's ``note_dependency`` already re-reads the document when a KNOWN file is
edited or removed; a file ADDED to the scope is a dependency of nothing (#2040). So at
``env-get-outdated`` :func:`find_outdated_scopes` walks every recorded scope again (one
directory walk per scope, no parsing) and returns the documents whose scope changed.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Any, Literal

from sphinx.application import Sphinx
from sphinx.environment import BuildEnvironment
from sphinx.util import logging

from sphinx_codelinks.config import (
    CodeLinksConfig,
    locate_src_dir,
)
from sphinx_codelinks.source_discover.config import SourceDiscoverConfig
from sphinx_codelinks.source_discover.source_discover import SourceDiscover
from sphinx_codelinks.sphinx_extension.need_id_refs import need_id_refs_store

logger = logging.getLogger(__name__)

Fingerprint = tuple[tuple[str, int, int], ...]
"""``(path relative to the scanned directory, POSIX; st_mtime_ns; st_size)``, sorted."""

ScopeKind = Literal["file", "directory"]

SCOPES_ATTRIBUTE = "codelinks_src_trace_scopes"
"""The environment attribute holding the directives' scopes, keyed by host document."""

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


# -- the handlers --------------------------------------------------------------------


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
    """
    codelinks_config = CodeLinksConfig.from_sphinx(app.config)
    skip = added | changed | removed
    memo: dict[tuple[str, ScopeKind, str], Fingerprint | None] = {}
    return [
        docname
        for docname, scopes in sorted(scope_store(env).items())
        if docname in env.found_docs
        and docname not in skip
        and any(_scope_changed(app, codelinks_config, scope, memo) for scope in scopes)
    ]
