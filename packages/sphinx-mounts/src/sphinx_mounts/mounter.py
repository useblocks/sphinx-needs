"""Core mounting logic.

This module intentionally writes to ``sphinx.project.Project._docname_to_path``
and ``_path_to_docname``. Those attributes are private (single-underscore) in
Sphinx; we depend on the following observable contract from
``sphinx/project.py``:

* ``Project.doc2path(docname, absolute=True)`` returns
  ``self.srcdir / self._docname_to_path[docname]``.
* ``pathlib.Path("/srcdir") / Path("/abs/external")`` returns
  ``Path("/abs/external")`` because the right operand is absolute.

So storing an absolute external path in ``_docname_to_path`` causes Sphinx
to read from that external location transparently. This is the entire trick.
"""

from __future__ import annotations

import os
from pathlib import Path, PurePath
from typing import TYPE_CHECKING, Any, NamedTuple

from ignore import Walk, WalkBuilder
from ignore.overrides import OverrideBuilder
from sphinx import version_info as _sphinx_version_info
from sphinx.errors import ExtensionError
from sphinx.project import Project
from sphinx.util import logging

from sphinx_mounts.config import MountConfig, mount_label
from sphinx_mounts.logging import log_warning

if TYPE_CHECKING:
    from collections.abc import Iterable

logger = logging.getLogger(__name__)


class DocRoot(NamedTuple):
    """What the path-confinement check needs to know about one mounted doc.

    :param roots: The directories the doc's file references must stay inside.
        A directory mount contributes exactly one (its ``dir``); a file-list
        mount contributes the parent directory of every listed file, and a
        reference is in-bundle if it is under **any** of them. All are
        already resolved — see :func:`_dir_root` and :func:`_listed_roots`.
    :param path_check: The owning mount's ``path_check`` mode.
    :param label: The owning mount's :func:`mount_label`, so a message about
        an escape can name the mount that has to be fixed rather than
        speaking of "the bundle root" in the abstract.
    """

    roots: tuple[Path, ...]
    path_check: str
    label: str


def _dir_root(mount_dir: Path) -> tuple[Path, ...]:
    """The confinement root set of a directory mount: just ``dir`` itself."""
    return (mount_dir.resolve(),)


def _listed_roots(files: Iterable[Path]) -> tuple[Path, ...]:
    """The confinement root set of a file-list mount.

    Every listed file contributes its own parent directory, and a reference is
    in-bundle if it lives under **any** of them. Duplicates are collapsed
    (several files in one directory contribute one root) and order is
    preserved, so diagnostics list the roots in ``files`` order.

    This is the *union* of the directories the user actually named. Two
    alternatives were tried and are both wrong:

    * one root per *document* — each listed file confined to its own parent —
      made the verdict depend on how deep a file happened to sit. A reference
      from ``index.rst`` down into ``notes/`` passed while the mirror-image
      reference from ``notes/2026-q1.rst`` up to a shared ``../shared.txt``
      was rejected, in the same mount and the same tree.
    * the *common ancestor* of the listed parents. That fixes the asymmetry
      but is unbounded in the other direction: the user's ``files`` list
      drives the root arbitrarily wide. Two files in sibling subtrees make
      their shared parent the root, and two files on genuinely disjoint
      branches make it the filesystem root — at which point ``path_check``
      silently permits every file on the machine, with no diagnostic, even
      at ``"error"``.

    The union has neither problem. It is a strict superset of the per-document
    rule, so the asymmetry stays fixed, and a strict subset of the common
    ancestor, so it can never admit a directory the user did not name.
    """
    return tuple(dict.fromkeys(f.parent.resolve() for f in files))


def _is_within_any(roots: Iterable[Path], candidate: Path) -> bool:
    """Whether ``candidate`` is inside (or equal to) at least one root."""
    return any(_is_within(root, candidate) for root in roots)


def _is_within(root: Path, candidate: Path) -> bool:
    """Whether ``candidate`` is ``root`` itself or lives underneath it.

    Both sides pass through :func:`os.path.normcase` first.
    :meth:`pathlib.Path.resolve` normalises symlinks but **not** case, so on
    Windows — case-insensitive but case-preserving — a bundle configured with
    a directory spelled ``Bundle`` that is really ``bundle`` on disk, or an
    ``include:: SUB/x.txt`` where the directory is ``sub``, would otherwise
    compare unequal component by component, and a perfectly legitimate
    in-bundle reference would be reported as an escape.

    ``normcase`` folds on **Windows only**: on POSIX it is
    :func:`os.fspath`, the identity function, macOS included. So this
    comparison is case-sensitive on macOS even though the default filesystem
    (APFS/HFS+) is not, and a reference whose written case differs from the
    root's own spelling is reported as an escape there. That is the position
    ``design/mapping-contract.md`` §9 records; folding on macOS too would
    take a fold this function does not perform.

    ``PurePath`` is used for the comparison rather than the concrete
    ``Path``, because after ``normcase`` the strings are no longer required
    to name anything on disk — no filesystem access should happen here.
    """
    root_key = PurePath(os.path.normcase(str(root)))
    candidate_key = PurePath(os.path.normcase(str(candidate)))
    return candidate_key.is_relative_to(root_key)


#: Type to store paths as in ``Project._docname_to_path``/``_path_to_docname``.
#:
#: Must match what the running Sphinx stores itself, because both directions of
#: the mapping are read by core code that assumes its own type:
#:
#: * Sphinx <8.0 stores ``str`` and ``Project.doc2path`` returns the stored
#:   value *verbatim*, so a ``Path`` leaks out to callers that treat it as a
#:   string -- the HTML builder slices it to recover the source suffix and
#:   raises ``TypeError: 'PosixPath' object is not subscriptable``.
#: * Sphinx >=8.0 stores ``Path``, keys ``_path_to_docname`` by ``Path``, and
#:   ``Project.path2doc`` normalises its argument with ``Path(filename)``
#:   before the lookup -- so a ``str`` key never matches and ``path2doc``
#:   silently falls through to returning the absolute path minus its suffix
#:   instead of the docname.
_PathKey = str if _sphinx_version_info < (8, 0) else Path


def _join_mount(mount_at: str | None, tail: str) -> str:
    """Compose a docname from a mount prefix and a relative tail.

    When ``mount_at`` is ``None`` the bundle is mounted at the host
    project root, so the tail is returned unchanged. Otherwise the
    prefix is joined with a single slash.
    """
    return tail if mount_at is None else f"{mount_at}/{tail}"


class _MountAwareProject(Project):
    """A :class:`sphinx.project.Project` that also discovers mounted trees.

    After ``super().discover()`` populates docnames from the host ``srcdir``,
    each configured mount is walked and its files are injected with
    **absolute** filesystem paths in ``_docname_to_path``.
    """

    def __init__(
        self,
        srcdir: str | Path,
        source_suffix: Iterable[str],
        mounts: tuple[MountConfig, ...],
    ) -> None:
        super().__init__(srcdir, source_suffix)
        self._mounts = mounts
        # Maps each mounted docname to the DocRoot the path-confinement check
        # in the extension needs. Rebuilt each discover().
        self._doc_roots: dict[str, DocRoot] = {}
        # Ordered docnames produced by each mount, keyed by its index in
        # ``self._mounts``. Consumed by the extension's ``attach_each``
        # wiring, which attaches every file rather than only the entry doc.
        # Rebuilt each discover().
        self._mount_entry_docnames: dict[int, list[str]] = {}

    def __getstate__(self) -> dict[str, Any]:
        """Keep mount state out of ``environment.pickle``.

        ``BuildEnvironment.__getstate__`` clears only its own unpickleable
        fields, so ``env.project`` — this instance, including its ``_mounts``
        tuple of :class:`~sphinx_mounts.config.MountConfig` dataclasses —
        used to be serialised into every user's ``.doctrees`` cache.

        Nothing ever reads it back. ``env.setup()`` calls
        ``app.project.restore()``, which copies only the three docname/path
        dictionaries onto the fresh project, and ``builder-inited`` then
        installs a new ``_MountAwareProject`` built from the *current* parsed
        mounts, whose ``discover()`` rebuilds all three fields below from
        scratch. So the pickled state was pure cache weight plus a version
        coupling: restoring it imports this module's private class names by
        name, which would turn a rename into a hard failure inside someone
        else's CI rather than a cache miss.

        The three fields are *emptied* rather than removed from the state.
        The unpickled instance is handed to ``Project.restore`` before it is
        discarded, and an emptied field keeps it structurally valid — whereas
        a missing attribute would make any future read a crash instead of a
        harmless empty. Emptying is enough for the goal, because the point is
        to keep this extension's own classes out of the serialised bytes.

        ``env_version`` in :func:`~sphinx_mounts.extension.setup` covers the
        remainder: the class *reference* for this subclass is still pickled,
        so a change to what does get serialised needs a version bump.
        """
        state = dict(self.__dict__)
        state["_mounts"] = ()
        state["_doc_roots"] = {}
        state["_mount_entry_docnames"] = {}
        return state

    def discover(
        self,
        exclude_paths: Iterable[str] = (),
        include_paths: Iterable[str] = ("**",),
    ) -> set[str]:
        """Discover host srcdir docs plus all mounted external trees."""
        docs = super().discover(exclude_paths, include_paths)
        self._doc_roots = {}
        self._mount_entry_docnames = {}
        for index, mount in enumerate(self._mounts):
            if _enforce_strict_mount_at(Path(self.srcdir), mount, index):
                # strict_mount_at violation — the whole mount is skipped,
                # so the host project stays completely untouched.
                self._mount_entry_docnames[index] = []
                continue
            added = _attach_mount(self, mount, index)
            docs.update(added)
            self._mount_entry_docnames[index] = added
        return docs


def _enforce_strict_mount_at(srcdir: Path, mount: MountConfig, index: int) -> bool:
    """Warn (and report "skip") if ``mount.strict_mount_at`` is set and
    the host srcdir already contains a directory at ``mount.mount_at``.

    The check is intentionally a no-op when ``strict_mount_at`` is
    false (the default per-docname collision detector remains the only
    gate) or when ``mount_at`` is ``None`` (rejected at config time so
    this branch is defensive). It does not fire for stray files at the
    path — files are left to the per-docname check, which catches the
    only case Sphinx actually cares about.

    The violation is a ``mounts.mount_at_occupied`` warning and the
    mount is **not mounted at all**: the mount point being occupied
    means the bundle cannot be attached without modifying the host, so
    the only clean reaction is to skip it. Users who want a hard
    failure can escalate with ``sphinx-build -W``.

    :param index: The mount's position in the ``mounts`` config list,
        used in the warning's :func:`mount_label`.
    :return: ``True`` when the mount must be skipped, ``False`` to
        proceed.
    """
    if not mount.strict_mount_at or mount.mount_at is None:
        return False
    candidate = srcdir / mount.mount_at
    if candidate.is_dir():
        msg = (
            f"sphinx-mounts: strict_mount_at violation: host project "
            f"already has a directory at {candidate}, but "
            f"{mount_label(mount, index)} requires the path to be free "
            f"— the whole mount is skipped. Rename or remove the host "
            f"directory, or set strict_mount_at = false to fall back "
            f"to per-docname collision checking."
        )
        log_warning(logger, msg, "mount_at_occupied")
        return True
    return False


def _attach_mount(
    project: _MountAwareProject, mount: MountConfig, index: int
) -> list[str]:
    """Inject ``mount`` into ``project`` — either a directory or a file list.

    Directory mode (``mount.dir`` set): walk the directory and pick up
    every file whose suffix matches one of the project's configured
    source suffixes. The docname tail is the relative path under
    ``dir``, minus the matched suffix.

    File-list mode (``mount.files`` set): each file's *basename* (minus
    the matched suffix) becomes the docname tail under ``mount.mount_at``.
    Subdirectories in the file paths are ignored; the result is a flat
    namespace under ``mount_at``.

    :param project: The Sphinx :class:`Project` to inject into.
    :param mount: Validated mount configuration.
    :param index: The mount's position in the ``mounts`` config list,
        used in the warning's :func:`mount_label`.
    :return: The docnames added by this mount, in a deterministic order
        (sorted by path for a directory mount, ``files`` order for a
        file-list mount). ``[]`` when the mount was skipped entirely —
        missing paths, unregistered suffixes, and docname conflicts all
        drop the whole mount with a single typed warning (see
        :func:`log_warning`), leaving the host project untouched.
    :raises ExtensionError: If the mount has neither ``dir`` nor ``files``
        — unreachable in practice because :class:`MountConfig` validation
        guarantees exactly one is set.
    """
    if mount.dir is not None:
        return _attach_mount_dir(project, mount, mount.dir, index)
    if mount.files is not None:
        return _attach_mount_files(project, mount, mount.files, index)
    # MountConfig.__post_init__ guarantees exactly one of dir/files is
    # set, so this branch is unreachable in practice.
    msg = f"sphinx-mounts: {mount_label(mount, index)} has neither dir nor files."
    raise ExtensionError(msg)


def _attach_mount_dir(
    project: _MountAwareProject, mount: MountConfig, mount_dir: Path, index: int
) -> list[str]:
    """Walk ``mount_dir`` with the ``ignore-python`` walker (a Rust
    binding to the same crate used by ``sphinx-codelinks`` and ubCode).

    The walker honours ``.gitignore`` and ``.ignore`` files *inside*
    the mounted tree (when ``mount.gitignore`` is true), and exposes
    the mount's ``include`` / ``exclude`` lists as gitignore-style
    allowlist / denylist overrides. Parent ``.gitignore`` files are
    NOT consulted regardless of the setting — otherwise mounting a
    directory whose parent gitignores it (the canonical
    ``bazel-bin/...`` case) would silently produce zero files.

    A missing directory is reported as a ``mounts.missing_path``
    warning and skipped, so a build whose upstream bundle is absent
    can still proceed (see :func:`parse_mounts`).
    """
    if not mount_dir.is_dir():
        msg = (
            f"sphinx-mounts: mount directory does not exist and the whole "
            f"mount is skipped: {mount_dir}"
        )
        log_warning(logger, msg, "missing_path")
        return []
    suffixes = tuple(project.source_suffix)

    walker = _build_walker(
        mount_dir,
        include=mount.include,
        exclude=mount.exclude,
        gitignore=mount.gitignore,
    )

    # Collect first, then process sorted, so docname order is
    # deterministic regardless of filesystem walk order.
    matched: list[tuple[Path, str]] = []
    for entry in walker:
        p = entry.path()
        if not p.is_file():
            continue
        suffix = _match_suffix(p.name, suffixes)
        if suffix is None:
            continue
        matched.append((p, suffix))
    matched.sort(key=lambda pair: pair[0].as_posix())

    entries: list[tuple[str, Path]] = []
    for abs_path, suffix in matched:
        rel_path = abs_path.relative_to(mount_dir)
        # Strip the matched suffix (which may be multi-dot like ".rst.txt").
        docname_tail = rel_path.as_posix()[: -len(suffix)]
        docname = _join_mount(mount.mount_at, docname_tail)
        entries.append((docname, abs_path))
    return _attach_entries(project, mount, entries, _dir_root(mount_dir), index)


def _build_walker(
    mount_dir: Path,
    *,
    include: tuple[str, ...],
    exclude: tuple[str, ...],
    gitignore: bool,
) -> Walk:
    """Configure a ``WalkBuilder`` for a single mount and return its
    iterator.

    Behaviour:

    - When ``gitignore`` is ``True``: ``.gitignore`` and ``.ignore``
      files *inside* the walked tree are honoured (the Rust ``ignore``
      crate only activates ``.gitignore`` inside a git repository).
      When ``False``: those files are treated as data, not filters —
      useful for sibling repositories whose ``.gitignore`` excludes
      content you still want to publish.
    - Parent directories are NOT scanned for ignore files, regardless
      of ``gitignore``. Mounts often live under paths that the host
      workspace gitignores (e.g. ``bazel-bin/``); we do not want
      those rules to silently strip the mount.
    - The user's global git config and ``.git/info/exclude`` are NOT
      consulted — keeps builds reproducible across machines.
    - Hidden entries (dotfiles, ``.git/``) are skipped.
    - ``include`` entries are added as positive overrides
      (allowlist); ``exclude`` entries are added as negated overrides
      (``!pattern``). Aligned with sphinx-codelinks'
      ``source_discover`` semantics.
    """
    builder = WalkBuilder(mount_dir)
    builder.ignore(gitignore)
    builder.git_ignore(gitignore)
    builder.parents(False)
    builder.git_global(False)
    builder.git_exclude(False)
    builder.hidden(True)

    if include or exclude:
        ob = OverrideBuilder(mount_dir)
        for pattern in include:
            ob.add(pattern)
        for pattern in exclude:
            ob.add(f"!{pattern}")
        builder.overrides(ob.build())

    return builder.build()


def _warn_ignored_walk_options(mount: MountConfig, index: int) -> None:
    """Warn when a file-list mount sets options only directory mode reads.

    ``include`` and ``exclude`` are gitignore-style patterns handed to the
    directory walker. A file-list mount has no walker — the ``files`` list
    *is* the selection — so the patterns are ignored completely: setting
    ``include = ["one.rst"]`` on a two-file mount still mounts both. Nothing
    said so, which made it the odd one out among this extension's
    cross-key rules; every other contradictory combination
    (``attach_each`` without ``files``, ``strict_mount_at`` on a root mount)
    is rejected at config time.

    It is a warning rather than a hard error because, unlike those, it is not
    ambiguous what the user gets: the mount is well-formed and mounts exactly
    the files they listed. Only their filter is dead.
    """
    ignored = [name for name in ("include", "exclude") if getattr(mount, name, ())]
    if not ignored:
        return
    keys = " and ".join(ignored)
    msg = (
        f"sphinx-mounts: {mount_label(mount, index)} sets {keys}, which only "
        f"directory mounts read — a file-list mount has no walker to filter, "
        f"so the `files` list is the selection and {keys} has no effect. "
        f"Remove it, or switch the mount to `dir` if you meant to filter a "
        f"tree."
    )
    log_warning(logger, msg, "ignored_option")


def _attach_mount_files(
    project: _MountAwareProject, mount: MountConfig, files: Iterable[Path], index: int
) -> list[str]:
    """Mount an explicit list of files under ``mount.mount_at``.

    Every listed file's basename (minus the matched suffix) becomes a docname
    tail, so the result is a flat namespace. All of them share the mount's
    confinement root *set* — see :func:`_listed_roots`.
    """
    _warn_ignored_walk_options(mount, index)
    suffixes = tuple(project.source_suffix)
    listed = list(files)
    entries: list[tuple[str, Path]] = []
    for abs_path in listed:
        if not abs_path.is_file():
            msg = (
                f"sphinx-mounts: listed file does not exist and the whole "
                f"mount is skipped: {abs_path}"
            )
            log_warning(logger, msg, "missing_path")
            return []
        suffix = _match_suffix(abs_path.name, suffixes)
        if suffix is None:
            msg = (
                f"sphinx-mounts: file {abs_path} has no extension matching "
                f"the project's source_suffix {list(suffixes)!r} — the "
                f"whole mount is skipped. Add a parser extension (e.g. "
                f"myst_parser for .md) or remove the file from the "
                f"mount's `files` list."
            )
            log_warning(logger, msg, "unknown_suffix")
            return []
        docname_tail = abs_path.name[: -len(suffix)]
        if not docname_tail:
            # The whole basename was the suffix, e.g. a file called exactly
            # ``.rst``. The docname would be the bare mount prefix with a
            # trailing slash — or, for a root mount, the empty string, which
            # writes a dotfile ``.html`` at the site root. Directory mode
            # never produces this because its walker skips hidden entries, so
            # rejecting it here also makes the two modes agree.
            msg = (
                f"sphinx-mounts: listed file {abs_path} has no name before "
                f"its {suffix!r} suffix, so it has no docname — the whole "
                f"mount is skipped. Give the file a name (e.g. "
                f"index{suffix}) or remove it from the mount's `files` list."
            )
            log_warning(logger, msg, "empty_docname")
            return []
        entries.append((_join_mount(mount.mount_at, docname_tail), abs_path))

    return _attach_entries(project, mount, entries, _listed_roots(listed), index)


def _attach_entries(
    project: _MountAwareProject,
    mount: MountConfig,
    entries: list[tuple[str, Path]],
    roots: tuple[Path, ...],
    index: int,
) -> list[str]:
    """Register a mount's ``(docname, abs_path)`` entries.

    Every docname is checked for collisions **before** anything is
    registered, against two sets:

    * docnames the host project or an earlier mount already provides —
      the first provider of a docname wins, so the outcome is
      deterministic;
    * docnames *this* mount already produced. Two entries of one mount
      can collide in both modes: two listed files sharing a basename
      (file-list mode flattens the namespace), or two files that differ
      only in registered source suffix, e.g. ``index.rst`` next to
      ``index.md`` (directory mode strips the suffix). Without this
      second check the later registration silently overwrote the
      earlier one, so a document vanished with no diagnostic at all and
      ``_path_to_docname`` stopped being one-to-one — where core Sphinx
      reports ``multiple files found for the document``.

    Either collision skips the whole mount with a single
    ``mounts.docname_conflict`` warning. Skipping the whole mount rather
    than the colliding file is deliberate — a partially mounted bundle
    would leave its sibling files dangling (``toc.not_included``) and
    could wire broken toctrees, i.e. modify the host project despite the
    problem. Because that is a large consequence for one filename, the
    warning states how many files the mount would have provided and
    which knobs resolve it.

    :param project: The Sphinx :class:`Project` to inject into.
    :param mount: The mount these entries belong to.
    :param entries: ``(docname, abs_path)`` pairs, in enumeration order.
    :param roots: The mount's confinement root set, shared by every entry —
        one check for the whole mount rather than one per document.
    :param index: The mount's position in the ``mounts`` config list,
        used in the warning's :func:`mount_label`.
    :return: The docnames actually registered (``[]`` when the whole
        mount was skipped).
    """
    seen: dict[str, Path] = {}
    for docname, abs_path in entries:
        if docname in project.docnames:
            existing = project._docname_to_path.get(docname)
            msg = (
                f"sphinx-mounts: docname conflict for {docname!r}: "
                f"{mount_label(mount, index)} would supply {abs_path}, "
                f"but {existing} already provides it — "
                f"{_skip_consequence(entries)} Mount the bundle under a "
                f"different mount_at, or {_drop_one_file_remedy(mount)}."
            )
            log_warning(logger, msg, "docname_conflict")
            return []
        if docname in seen:
            msg = (
                f"sphinx-mounts: docname conflict for {docname!r}: "
                f"{mount_label(mount, index)} maps two of its own files to "
                f"that docname — {seen[docname]} and {abs_path} — "
                f"{_skip_consequence(entries)} Rename one of the two files, "
                f"or {_drop_one_file_remedy(mount)}; changing mount_at does "
                f"not help, because both files move with it."
            )
            log_warning(logger, msg, "docname_conflict")
            return []
        seen[docname] = abs_path
    added: list[str] = []
    doc_root = DocRoot(roots, mount.path_check, mount_label(mount, index))
    for docname, abs_path in entries:
        project.docnames.add(docname)
        path_key = _PathKey(abs_path)
        project._docname_to_path[docname] = path_key
        project._path_to_docname[path_key] = docname
        project._doc_roots[docname] = doc_root
        added.append(docname)
        logger.debug("sphinx-mounts: mounted %s -> %s", docname, abs_path)
    return added


def _skip_consequence(entries: list[tuple[str, Path]]) -> str:
    """Spell out what skipping the whole mount costs, for a warning message.

    One colliding filename removes the *entire* bundle from the build, which
    can be hundreds of documents. Naming the count keeps that consequence
    from hiding behind a single line in a long build log.
    """
    count = len(entries)
    if count == 1:
        return "the whole mount is skipped, dropping the only file it provides."
    return f"the whole mount is skipped, dropping all {count} files it provides."


def _drop_one_file_remedy(mount: MountConfig) -> str:
    """The "leave one of them out" half of a conflict message's remedy.

    It has to be mode-dependent. ``include`` / ``exclude`` are directory-mode
    patterns evaluated relative to ``dir``; on a file-list mount they are
    ignored entirely (see :func:`_warn_ignored_walk_options`), so offering
    them there described an action that would have no effect. And the
    intra-mount basename collision is *principally* a file-list failure —
    that mode is the flat namespace — so the mode where the advice was
    inapplicable was the mode where the message fires most.
    """
    if mount.files is not None:
        return "remove one of the two entries from the mount's `files` list"
    return "use the mount's include / exclude patterns to leave it out"


def _match_suffix(filename: str, suffixes: Iterable[str]) -> str | None:
    """Return the matching source suffix for ``filename``, or None."""
    for suffix in suffixes:
        if filename.endswith(suffix):
            return suffix
    return None


def install_mount_aware_project(
    app_project: Project,
    mounts: tuple[MountConfig, ...],
) -> _MountAwareProject:
    """Build a :class:`_MountAwareProject` carrying state from ``app_project``.

    Every attribute of ``app_project`` travels across, so that state Sphinx
    populated between construction and now is preserved. It is copied
    wholesale rather than field by field on purpose: this is a hand-rolled
    copy-constructor over a class this extension does not own, and a field
    added to :class:`~sphinx.project.Project` by a future Sphinx would
    otherwise be dropped silently — the worst failure mode available, since
    the resulting project would look complete and simply be missing
    something.

    The three fields this subclass owns are excluded (the constructor has
    just set them, and they are per-mount state that has nothing to do with
    the project being replaced), and the three docname/path dictionaries are
    re-copied afterwards so *those* are not shared. Any other attribute is
    carried **by reference**, which is safe only because the replaced project
    is discarded immediately — both ``app.project`` and ``env.project`` are
    repointed at the new one — so nothing can observe the sharing.

    ``vars()`` is read defensively: if a future ``Project`` were to define
    ``__slots__`` it would have no ``__dict__``, and falling back to the
    explicit copy below is better than raising inside someone's build.
    """
    new = _MountAwareProject(
        app_project.srcdir,
        app_project.source_suffix,
        mounts,
    )
    owned = {"_mounts", "_doc_roots", "_mount_entry_docnames"}
    for name, value in getattr(app_project, "__dict__", {}).items():
        if name not in owned:
            setattr(new, name, value)
    new.docnames = set(app_project.docnames)
    new._docname_to_path = dict(app_project._docname_to_path)
    new._path_to_docname = dict(app_project._path_to_docname)
    return new
