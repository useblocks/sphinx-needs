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
from sphinx.project import Project
from sphinx.util import logging

from sphinx_mounts.config import MountConfig

if TYPE_CHECKING:
    from collections.abc import Iterable

logger = logging.getLogger(__name__)


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

    def discover(
        self,
        exclude_paths: Iterable[str] = (),
        include_paths: Iterable[str] = ("**",),
    ) -> set[str]:
        """Discover host srcdir docs plus all mounted external trees."""
        docs = super().discover(exclude_paths, include_paths)
        for mount in self._mounts:
            _enforce_strict_mount_at(Path(self.srcdir), mount)
            docs |= _attach_mount(self, mount)
        return docs


def _enforce_strict_mount_at(srcdir: Path, mount: MountConfig) -> None:
    """Raise if ``mount.strict_mount_at`` is set and the host srcdir
    already contains a directory at ``mount.mount_at``.

    The check is intentionally a no-op when ``strict_mount_at`` is
    false (the default per-docname collision detector remains the only
    gate) or when ``mount_at`` is ``None`` (rejected at config time so
    this branch is defensive). It does not fire for stray files at the
    path — files are left to the per-docname check, which catches the
    only case Sphinx actually cares about.
    """
    if not mount.strict_mount_at or mount.mount_at is None:
        return
    candidate = srcdir / mount.mount_at
    if candidate.is_dir():
        msg = (
            f"sphinx-mounts: strict_mount_at violation: host project "
            f"already has a directory at {candidate}, but mount "
            f"{mount.mount_at!r} requires the path to be free. "
            f"Rename or remove the host directory, or set "
            f"strict_mount_at = false to fall back to per-docname "
            f"collision checking."
        )
        raise ValueError(msg)


def _attach_mount(project: Project, mount: MountConfig) -> set[str]:
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
    :return: The set of docnames added by this mount.
    :raises ValueError: If a constructed docname collides with an existing
        docname already in the project (host shadowing or two mounts
        producing the same docname), or — in file-list mode — if a file's
        suffix is not registered with Sphinx.
    """
    if mount.dir is not None:
        return _attach_mount_dir(project, mount, mount.dir)
    if mount.files is not None:
        return _attach_mount_files(project, mount, mount.files)
    # MountConfig.__post_init__ guarantees exactly one of dir/files is
    # set, so this branch is unreachable in practice.
    mount_label = "<root>" if mount.mount_at is None else repr(mount.mount_at)
    msg = f"sphinx-mounts: mount {mount_label} has neither dir nor files."
    raise ValueError(msg)


def _attach_mount_dir(
    project: Project, mount: MountConfig, mount_dir: Path
) -> set[str]:
    """Walk ``mount_dir`` with the ``ignore-python`` walker (a Rust
    binding to the same crate used by ``sphinx-codelinks`` and ubCode).

    The walker honours ``.gitignore`` and ``.ignore`` files *inside*
    the mounted tree (when ``mount.gitignore`` is true), and exposes
    the mount's ``include`` / ``exclude`` lists as gitignore-style
    allowlist / denylist overrides. Parent ``.gitignore`` files are
    NOT consulted regardless of the setting — otherwise mounting a
    directory whose parent gitignores it (the canonical
    ``bazel-bin/...`` case) would silently produce zero files.
    """
    added: set[str] = set()
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

    for abs_path, suffix in matched:
        rel_path = abs_path.relative_to(mount_dir)
        # Strip the matched suffix (which may be multi-dot like ".rst.txt").
        docname_tail = rel_path.as_posix()[: -len(suffix)]
        docname = _join_mount(mount.mount_at, docname_tail)
        _register(project, docname, abs_path, mount.mount_at)
        added.add(docname)
    return added


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
    project: Project, mount: MountConfig, files: Iterable[Path]
) -> set[str]:
    added: set[str] = set()
    suffixes = tuple(project.source_suffix)

    for abs_path in files:
        suffix = _match_suffix(abs_path.name, suffixes)
        if suffix is None:
            msg = (
                f"sphinx-mounts: file {abs_path} has no extension matching "
                f"the project's source_suffix {list(suffixes)!r}. Add a "
                f"parser extension (e.g. myst_parser for .md) or remove "
                f"the file from the mount's `files` list."
            )
            raise ValueError(msg)
        docname_tail = abs_path.name[: -len(suffix)]
        docname = _join_mount(mount.mount_at, docname_tail)
        _register(project, docname, abs_path, mount.mount_at)
        added.add(docname)
    return added


def _register(
    project: Project, docname: str, abs_path: Path, mount_at: str | None
) -> None:
    """Add a single (docname, abs_path) entry to the project, checking for
    collisions with already-registered docnames."""
    if docname in project.docnames:
        existing = project._docname_to_path.get(docname)
        mount_label = "<root>" if mount_at is None else repr(mount_at)
        msg = (
            f"sphinx-mounts: docname conflict for {docname!r}: "
            f"mount {mount_label} would supply {abs_path}, "
            f"but {existing} already provides it."
        )
        raise ValueError(msg)
    project.docnames.add(docname)
    project._docname_to_path[docname] = abs_path
    project._path_to_docname[abs_path] = docname
    logger.debug("sphinx-mounts: mounted %s -> %s", docname, abs_path)


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
