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

from pathlib import Path
from typing import TYPE_CHECKING

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
        # Maps each mounted docname to (bundle_root, path_check) for the
        # path-confinement check in the extension. Rebuilt each discover().
        self._doc_roots: dict[str, tuple[Path, str]] = {}
        # Ordered docnames produced by each mount, keyed by its index in
        # ``self._mounts``. Consumed by the extension's ``attach_each``
        # wiring, which attaches every file rather than only the entry doc.
        # Rebuilt each discover().
        self._mount_entry_docnames: dict[int, list[str]] = {}

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

    entries: list[tuple[str, Path, Path]] = []
    for abs_path, suffix in matched:
        rel_path = abs_path.relative_to(mount_dir)
        # Strip the matched suffix (which may be multi-dot like ".rst.txt").
        docname_tail = rel_path.as_posix()[: -len(suffix)]
        docname = _join_mount(mount.mount_at, docname_tail)
        entries.append((docname, abs_path, mount_dir))
    return _attach_entries(project, mount, entries, index)


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


def _attach_mount_files(
    project: _MountAwareProject, mount: MountConfig, files: Iterable[Path], index: int
) -> list[str]:
    suffixes = tuple(project.source_suffix)
    entries: list[tuple[str, Path, Path]] = []
    for abs_path in files:
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
        docname = _join_mount(mount.mount_at, docname_tail)
        entries.append((docname, abs_path, abs_path.parent))
    return _attach_entries(project, mount, entries, index)


def _attach_entries(
    project: _MountAwareProject,
    mount: MountConfig,
    entries: list[tuple[str, Path, Path]],
    index: int,
) -> list[str]:
    """Register a mount's ``(docname, abs_path, root)`` entries.

    Every docname is checked for collisions **before** anything is
    registered: if any is already provided by the host project or an
    earlier mount, the whole mount is skipped with a single
    ``mounts.docname_conflict`` warning. Skipping the whole mount rather
    than the colliding file is deliberate — a partially mounted bundle
    would leave its sibling files dangling (``toc.not_included``) and
    could wire broken toctrees, i.e. modify the host project despite the
    problem. The first provider of a docname wins, so the outcome is
    deterministic.

    :param project: The Sphinx :class:`Project` to inject into.
    :param mount: The mount these entries belong to.
    :param entries: ``(docname, abs_path, path_check_root)`` triples.
    :param index: The mount's position in the ``mounts`` config list,
        used in the warning's :func:`mount_label`.
    :return: The docnames actually registered (``[]`` when the whole
        mount was skipped).
    """
    for docname, abs_path, _root in entries:
        if docname in project.docnames:
            existing = project._docname_to_path.get(docname)
            msg = (
                f"sphinx-mounts: docname conflict for {docname!r}: "
                f"{mount_label(mount, index)} would supply {abs_path}, "
                f"but {existing} already provides it — the whole mount "
                f"is skipped."
            )
            log_warning(logger, msg, "docname_conflict")
            return []
    added: list[str] = []
    for docname, abs_path, root in entries:
        project.docnames.add(docname)
        path_key = _PathKey(abs_path)
        project._docname_to_path[docname] = path_key
        project._path_to_docname[path_key] = docname
        project._doc_roots[docname] = (root, mount.path_check)
        added.append(docname)
        logger.debug("sphinx-mounts: mounted %s -> %s", docname, abs_path)
    return added


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

    The original docname/path dictionaries are copied across so that any
    state populated by Sphinx between construction and now is preserved.
    """
    new = _MountAwareProject(
        app_project.srcdir,
        app_project.source_suffix,
        mounts,
    )
    new.docnames = set(app_project.docnames)
    new._docname_to_path = dict(app_project._docname_to_path)
    new._path_to_docname = dict(app_project._path_to_docname)
    return new
