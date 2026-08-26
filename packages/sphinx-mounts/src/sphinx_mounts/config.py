"""Configuration models for sphinx-mounts.

Validation is hand-rolled: a frozen :class:`dataclasses.dataclass` plus a
``from_dict`` classmethod is enough for the small surface area of this
extension, and avoids the runtime weight of a full schema library.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields
from pathlib import Path
import tomllib
from typing import Any

from sphinx.errors import ExtensionError
from sphinx.util import logging

from sphinx_mounts.logging import log_warning

logger = logging.getLogger(__name__)


class TomlConfigError(ExtensionError):
    """Raised when the TOML config file cannot be parsed or is malformed.

    Subclasses :class:`sphinx.errors.ExtensionError`, so Sphinx aborts the
    build rather than continuing with a configuration it cannot read. Config
    errors are deliberately *not* suppressible: sphinx-mounts cannot proceed
    at all when the configuration is unreadable.

    Passing ``modname`` is what makes the report's first line read
    ``Extension error (sphinx_mounts)!`` rather than a bare ``Extension
    error!``, which is the only part of the presentation this extension
    controls. How much surrounds that line is up to the running Sphinx: 7.x
    prints the message and nothing else, while from 8.2 on
    ``sphinx/_cli/util/errors.py`` prints Versions / Last Messages / Loaded
    Extensions / Traceback blocks and an invitation to open an issue against
    Sphinx for *every* ``SphinxError``. Naming the module is therefore the
    difference between a user filing the report in the right place and the
    wrong one.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message, modname="sphinx_mounts")


class MountConfigError(ExtensionError):
    """Raised when a mount configuration entry is invalid.

    Subclasses :class:`sphinx.errors.ExtensionError` for the same reason as
    :class:`TomlConfigError` — a malformed entry means the build cannot
    proceed, and users must not be able to suppress it away. See that class
    for what ``modname`` does and does not control.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message, modname="sphinx_mounts")


@dataclass(frozen=True, slots=True)
class MountConfig:
    """One mounted external source tree, in one of two modes.

    A mount is either a *directory* (``dir``) or an *explicit list of
    files* (``files``). The two are mutually exclusive: exactly one
    must be set. Both modes share the same ``mount_at`` semantics and
    the same toctree-integration knobs.

    Fields:
        mount_at: The docname prefix at which the mount appears in the
            host project. For example, ``_generated/api-foo`` makes a
            mounted file ``index.rst`` available as docname
            ``_generated/api-foo/index``. Stored without surrounding
            slashes. ``None`` (the default) mounts the bundle at the
            host project's root — a bundle file ``tutorial.rst``
            becomes docname ``tutorial``.
        dir: **Directory mode.** Absolute path (or path relative to
            confdir) of an external directory holding source files.
            Every file under it whose extension matches the project's
            ``source_suffix`` is mounted; the relative-to-``dir`` path
            (minus the suffix) becomes the docname tail. Mutually
            exclusive with ``files``.
        files: **File-list mode.** Tuple of absolute paths (or paths
            relative to confdir) to individual source files. Each file's
            *basename* (minus the matched ``source_suffix``) becomes the
            docname tail under ``mount_at``. Subdirectories in the file
            paths are ignored — the result is a flat namespace. May
            contain a single file. Mutually exclusive with ``dir``.
        include: Tuple of gitignore-style glob patterns evaluated
            relative to ``dir``. If non-empty, *only* files matching
            at least one pattern are walked; everything else is
            filtered out. If empty (the default), no allowlist is
            applied. Only meaningful in directory mode. Aligns with
            sphinx-codelinks' ``source_discover.include``.
        exclude: Tuple of gitignore-style glob patterns evaluated
            relative to ``dir``. Matching files are skipped after
            ``include`` allowlisting. Only meaningful in directory
            mode (in file-list mode the list itself is the filter).
            Aligns with sphinx-codelinks' ``source_discover.exclude``.
        gitignore: Whether to honour ``.gitignore`` / ``.ignore``
            files found *inside* the mounted tree during discovery.
            Defaults to ``True``. Set to ``False`` when mounting a
            sibling repository whose ``.gitignore`` excludes content
            you nevertheless want to publish, or when the bundle is
            served from a generated cache where ``.gitignore`` is not
            meaningful. Aligns with sphinx-codelinks'
            ``source_discover.gitignore``. Parent ``.gitignore``
            files are never consulted regardless of this setting —
            otherwise mounts inside host-gitignored directories like
            ``bazel-bin/`` would silently produce zero files.
        attach_to: Optional host docname whose toctree should receive the
            mount entry. If ``None`` (default), no automatic toctree
            wiring is performed and the host project is responsible for
            referencing the mount.
        toctree_index: 0-based index selecting *which* toctree inside the
            ``attach_to`` document to extend, in document order. Defaults
            to ``0`` (the first toctree). Ignored when ``attach_to`` is
            ``None``. If the document contains no toctree, a new one is
            created and the entry is appended; if the index exceeds the
            number of toctrees present, a ``mounts.toctree_index`` warning
            is emitted and the mount is left unwired.
        entry_doc: Mount-relative docname of the entry document to wire
            into the host toctree. Defaults to ``"index"``. The resulting
            docname is ``f"{mount_at}/{entry_doc}"`` — or just
            ``entry_doc`` when ``mount_at`` is ``None``. This is the
            *only* doc auto-attached; any other docs in the mount must
            be reachable from the entry doc via its own toctree / refs.
        attach_each: File-list mode only. When ``True``, ``attach_to``
            wires *every* listed file into the host toctree (in ``files``
            order) instead of only ``entry_doc`` — so a set of loose files
            can be mounted without an index doc to stitch them together.
            Requires ``attach_to``; mutually exclusive with a non-default
            ``entry_doc``; rejected in directory mode. Defaults to
            ``False``.
        strict_mount_at: When ``True``, emit a ``mounts.mount_at_occupied``
            warning (escalating to a failure under ``sphinx-build -W``) if
            the host project already has a directory at
            ``<srcdir>/<mount_at>/``.
            Defaults to ``False`` — the existing per-docname collision
            check is the only gate, which lets a mount slot under a
            host-owned staging directory that holds non-source siblings
            (assets, READMEs). Set to ``True`` to treat any host
            directory at ``mount_at`` as a misconfiguration, catching
            the mistake earlier than per-docname collisions would (the
            check fires even when no concrete docname collides).
            Incompatible with a root mount (``mount_at = None``), since
            the host srcdir always exists; that combination is rejected
            at config validation.
        path_check: How to react when a directive inside a mounted doc
            references a file outside the bundle root (in directory mode
            that is ``dir``; in file-list mode it is any listed file's
            parent directory). One of ``"warn"`` (the default — log a
            ``mounts.path_escape`` warning, which ``sphinx-build -W``
            escalates to a build failure), ``"error"`` (abort the build
            immediately), or ``"off"`` (disable the check).

            ``"warn"`` is the default because it is what the rest of
            this extension does: every mount-specific problem is a typed,
            suppressible warning that ``-W`` turns into a failure, and
            :mod:`sphinx_mounts.logging` states that as the doctrine. An
            escaping reference is a mount-specific problem like any
            other. It is also not something a hard default could
            actually guarantee: the check runs from
            ``env-check-consistency``, which Sphinx skips entirely on a
            build that reads no document, so ``"error"`` was never a
            standing invariant — only a reaction on the builds that
            happened to read something.

            Set ``"error"`` where a hard stop is wanted without ``-W``.
    """

    mount_at: str | None = None
    dir: Path | None = None
    files: tuple[Path, ...] | None = None
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    gitignore: bool = True
    attach_to: str | None = None
    toctree_index: int = 0
    entry_doc: str = "index"
    attach_each: bool = False
    strict_mount_at: bool = False
    path_check: str = "warn"

    def __post_init__(self) -> None:
        if self.mount_at is not None:
            _validate_relative_docname("mount_at", self.mount_at)
            normalized = self.mount_at.strip("/")
            if normalized != self.mount_at:
                object.__setattr__(self, "mount_at", normalized)

        _validate_dir_or_files(self.dir, self.files)

        # ``bool`` is a subclass of ``int``; here we accept only a true
        # bool, not 1/0, to keep the config schema honest.
        if not isinstance(self.gitignore, bool):
            msg = f"gitignore must be a boolean; got {type(self.gitignore).__name__}."
            raise MountConfigError(msg)

        if self.attach_to is not None:
            _validate_relative_docname("attach_to", self.attach_to)
            normalized_attach = self.attach_to.strip("/")
            if normalized_attach != self.attach_to:
                object.__setattr__(self, "attach_to", normalized_attach)

        # ``bool`` is a subclass of ``int`` — reject explicitly.
        if isinstance(self.toctree_index, bool) or not isinstance(
            self.toctree_index, int
        ):
            msg = (
                f"toctree_index must be a non-negative integer; "
                f"got {type(self.toctree_index).__name__}."
            )
            raise MountConfigError(msg)
        if self.toctree_index < 0:
            msg = f"toctree_index must be non-negative; got {self.toctree_index}."
            raise MountConfigError(msg)

        _validate_relative_docname("entry_doc", self.entry_doc)
        # Same normalisation as mount_at / attach_to above. Without it,
        # ``entry_doc = "index/"`` was accepted and then never matched: the
        # wired docname became ``"<mount_at>/index/"``, which is not among the
        # docnames the mount produced, so the entry-doc gate dropped it and
        # the mount was mounted-but-unwired. The only symptom was a
        # ``toc.not_included`` pointing at the bundle file rather than at the
        # configuration. A leading '/' is already rejected above, so rstrip is
        # equivalent to strip here.
        normalized_entry = self.entry_doc.rstrip("/")
        if normalized_entry != self.entry_doc:
            object.__setattr__(self, "entry_doc", normalized_entry)

        _validate_attach_each(
            self.attach_each, self.files, self.attach_to, self.entry_doc
        )

        if not isinstance(self.strict_mount_at, bool):
            msg = (
                f"strict_mount_at must be a boolean; "
                f"got {type(self.strict_mount_at).__name__}."
            )
            raise MountConfigError(msg)
        if self.strict_mount_at and self.mount_at is None:
            msg = (
                "strict_mount_at = true requires an explicit mount_at — "
                "a root mount has no host-side directory whose existence "
                "could meaningfully fail the check."
            )
            raise MountConfigError(msg)

        if not isinstance(self.path_check, str):
            msg = f"path_check must be a string; got {type(self.path_check).__name__}."
            raise MountConfigError(msg)
        if self.path_check not in {"error", "warn", "off"}:
            msg = (
                f"path_check must be one of 'error', 'warn', 'off'; "
                f"got {self.path_check!r}."
            )
            raise MountConfigError(msg)

    @classmethod
    def from_dict(cls, entry: Mapping[str, Any]) -> MountConfig:
        """Construct a :class:`MountConfig` from a mapping (e.g. TOML table).

        Unknown keys are rejected. Exactly one of ``dir`` / ``files``
        must be present. ``mount_at`` is optional — when omitted, the
        bundle mounts at the host project root. String paths are
        coerced to :class:`pathlib.Path`; lists of patterns are
        coerced to tuples.

        :raises MountConfigError: If the mapping is malformed.
        """
        allowed = {f.name for f in fields(cls)}
        unknown = set(entry) - allowed
        if unknown:
            # Reported, never fatal. A `ubproject.toml` is shared with tools on
            # independent release cadences, so a key this reader does not model
            # is routine rather than a mistake — and aborting on it takes down
            # every build of the project on every older sphinx-mounts,
            # including builds of variants the key would not have changed.
            #
            # The posture is deliberately the same as ubCode's
            # `config.mount_unknown_key`, which is what makes a gating key such
            # as `if` safe to introduce later: a reader that mounts the bundle
            # but ignores the key would publish content the author gated, and
            # the way that window never opens is for the tolerant path to ship
            # no later than the release that makes `[[source.mounts]]`
            # readable. That release is this one.
            #
            # `mapping-contract.md` §4 records the change and the reasoning.
            msg = (
                f"sphinx-mounts: unknown mount key(s) {sorted(unknown)} on "
                f"{_entry_label(entry)}; they are ignored. Supported keys are "
                f"{sorted(allowed)}. A key another tool reads is not an error "
                f"here — but a misspelling is, so check the spelling if you "
                f"expected this key to do something."
            )
            log_warning(logger, msg, "unknown_key")
            entry = {key: value for key, value in entry.items() if key in allowed}
        if "dir" not in entry and "files" not in entry:
            msg = (
                "Mount entry must declare either 'dir' (directory mode) "
                "or 'files' (file-list mode)."
            )
            raise MountConfigError(msg)
        if "dir" in entry and "files" in entry:
            msg = "Mount entry must declare either 'dir' or 'files', not both."
            raise MountConfigError(msg)

        mount_dir = _coerce_path(entry["dir"]) if "dir" in entry else None
        files = _coerce_files(entry["files"]) if "files" in entry else None
        include = _coerce_pattern_list("include", entry.get("include", ()))
        exclude = _coerce_pattern_list("exclude", entry.get("exclude", ()))
        gitignore = entry.get("gitignore", True)

        return cls(
            mount_at=entry.get("mount_at"),
            dir=mount_dir,
            files=files,
            include=include,
            exclude=exclude,
            gitignore=gitignore,
            attach_to=entry.get("attach_to"),
            toctree_index=entry.get("toctree_index", 0),
            entry_doc=entry.get("entry_doc", "index"),
            attach_each=entry.get("attach_each", False),
            strict_mount_at=entry.get("strict_mount_at", False),
            path_check=entry.get("path_check", "warn"),
        )


def _entry_label(entry: Mapping[str, Any]) -> str:
    """Name a raw mount entry by its source, for a message about that entry.

    ``from_dict`` does not know the entry's position in the array, so the
    source path is the only handle a user has on it. Falls back to the whole
    key set when the entry declares neither ``dir`` nor ``files`` — a shape
    that is about to be rejected anyway.
    """
    if "dir" in entry:
        return f"the mount with dir={entry['dir']!r}"
    if "files" in entry:
        return f"the mount with files={entry['files']!r}"
    return f"the mount entry with keys {sorted(entry)}"


def mount_label(mount: MountConfig, index: int) -> str:
    """Human-readable identifier for a mount, used in warning messages.

    Names the mount's position in the ``mounts`` config list plus its
    source path, so a warning is actionable without counting config
    blocks: ``mounts[0] (dir=/abs/path)`` in directory mode, or
    ``mounts[1] (files=/a.rst, /b.rst)`` in file-list mode.
    """
    if mount.dir is not None:
        source = f"dir={mount.dir}"
    else:
        source = f"files={', '.join(map(str, mount.files or ()))}"
    return f"mounts[{index}] ({source})"


def _coerce_path(raw: Any) -> Path:
    """Accept Path or str; reject anything else."""
    if isinstance(raw, Path):
        return raw
    if isinstance(raw, str):
        return Path(raw)
    msg = f"dir must be a string or Path; got {type(raw).__name__}."
    raise MountConfigError(msg)


def _coerce_files(raw: Any) -> tuple[Path, ...]:
    """Accept a non-empty list/tuple of strings/Paths and return a tuple of Paths."""
    if isinstance(raw, str) or not isinstance(raw, list | tuple):
        msg = (
            f"files must be a list or tuple of strings/Paths; got {type(raw).__name__}."
        )
        raise MountConfigError(msg)
    if not raw:
        msg = "files must contain at least one entry."
        raise MountConfigError(msg)
    collected: list[Path] = []
    for item in raw:
        if isinstance(item, Path):
            collected.append(item)
        elif isinstance(item, str):
            collected.append(Path(item))
        else:
            msg = (
                f"each entry in files must be a string or Path; "
                f"got {type(item).__name__} for {item!r}."
            )
            raise MountConfigError(msg)
    return tuple(collected)


def _coerce_pattern_list(field_name: str, raw: Any) -> tuple[str, ...]:
    """Accept a list/tuple of strings (possibly empty) and return a
    tuple. Used for both ``include`` and ``exclude`` glob lists; the
    ``field_name`` argument feeds the error messages."""
    # ``str`` is technically a sequence but never what we want here.
    if isinstance(raw, str) or not isinstance(raw, list | tuple):
        msg = (
            f"{field_name} must be a list or tuple of strings; "
            f"got {type(raw).__name__}."
        )
        raise MountConfigError(msg)
    for item in raw:
        if not isinstance(item, str):
            msg = (
                f"{field_name} entries must be strings; "
                f"got {type(item).__name__} for {item!r}."
            )
            raise MountConfigError(msg)
    return tuple(raw)


def _validate_dir_or_files(dir_: Path | None, files: tuple[Path, ...] | None) -> None:
    """Enforce ``dir`` / ``files`` mutual exclusion and the shape of a
    ``files`` list, raising :class:`MountConfigError` on violation.
    Extracted from ``MountConfig.__post_init__`` to keep that method's
    cyclomatic complexity inside ruff's threshold."""
    if dir_ is None and files is None:
        msg = (
            "Mount must declare either `dir` (directory mode) or "
            "`files` (file-list mode); got neither."
        )
        raise MountConfigError(msg)
    if dir_ is not None and files is not None:
        msg = (
            "Mount must declare either `dir` (directory mode) or "
            "`files` (file-list mode), not both."
        )
        raise MountConfigError(msg)
    if files is None:
        return
    if not isinstance(files, tuple):
        msg = f"files must be a tuple of paths; got {type(files).__name__}."
        raise MountConfigError(msg)
    if not files:
        msg = "files must contain at least one entry."
        raise MountConfigError(msg)
    for f in files:
        if not isinstance(f, Path):
            msg = (
                f"each entry in files must be a Path; got {type(f).__name__} for {f!r}."
            )
            raise MountConfigError(msg)


def _validate_attach_each(
    attach_each: bool,
    files: tuple[Path, ...] | None,
    attach_to: str | None,
    entry_doc: str,
) -> None:
    """Enforce the type and constraints on ``attach_each``.

    ``attach_each`` only makes sense for a file-list mount that wires every
    listed file into a host toctree. Extracted from
    ``MountConfig.__post_init__`` to keep its complexity within ruff's
    threshold.
    """
    if not isinstance(attach_each, bool):
        msg = f"attach_each must be a boolean; got {type(attach_each).__name__}."
        raise MountConfigError(msg)
    if not attach_each:
        return
    if files is None:
        msg = (
            "attach_each is only valid in file-list mode (files = [...]); a "
            "directory mount has a single entry doc that toctrees its tree."
        )
        raise MountConfigError(msg)
    if attach_to is None:
        msg = (
            "attach_each requires attach_to — it wires every listed file into "
            "that host doc's toctree."
        )
        raise MountConfigError(msg)
    if entry_doc != "index":
        msg = (
            "attach_each attaches every listed file, so entry_doc is "
            "meaningless; set attach_each or entry_doc, not both."
        )
        raise MountConfigError(msg)


def _validate_relative_docname(field_name: str, value: object) -> None:
    """Validate a relative docname-shaped string field.

    Used by :class:`MountConfig` for ``mount_at``, ``attach_to``, and
    ``entry_doc``. The accepted shape is exactly:

    * a non-empty string;
    * no leading ``/`` — a docname is always relative;
    * no ``..`` component;
    * no *interior* empty segment (``a//b``) and no ``.`` segment
      (``a/./b``, or a bare ``.``);
    * no leading or trailing whitespace, in the value or in any segment.

    Everything outside that is a hard :class:`MountConfigError`, in line with
    the doctrine that a configuration this extension cannot interpret is not
    suppressible. Those shapes used to be accepted verbatim, and a docname is
    matched **literally** rather than resolved as a filesystem path, so each
    of them produced something no host document can ever be:

    * ``a//b`` and ``" a/b "`` gave a docname holding an empty segment or a
      space, leaving the mount silently unreferenceable;
    * ``.`` was worse than unreferenceable. Written to mean "the project
      root", it produced the docname ``./index`` alongside the host's own
      ``index``: two distinct docnames resolving to one output file, so the
      mounted page was overwritten with no diagnostic at all. Omitting
      ``mount_at`` is how a root mount is expressed.

    Being strict here also keeps the accepted shape describable in a few lines
    for a second implementation, which "accepted but never usable" is not.

    Trailing slashes are the one thing normalised rather than rejected
    (``a/b/`` -> ``a/b``), because a docname written with a trailing separator
    is a natural way to write it and means exactly one thing. This function
    does not normalise; the caller does, uniformly for all three fields.
    """
    if not isinstance(value, str):
        msg = f"{field_name} must be a string; got {type(value).__name__}."
        raise MountConfigError(msg)
    if not value:
        msg = f"{field_name} must be a non-empty string."
        raise MountConfigError(msg)
    if value.startswith("/"):
        msg = (
            f"{field_name} must not start with '/'; got {value!r}. "
            "Use a relative docname such as 'index' or '_generated/api-foo'."
        )
        raise MountConfigError(msg)
    if ".." in Path(value).parts:
        msg = f"{field_name} must not contain '..' components; got {value!r}."
        raise MountConfigError(msg)
    if value != value.strip():
        msg = (
            f"{field_name} must not have leading or trailing whitespace; "
            f"got {value!r}. Docnames are matched exactly, so the surrounding "
            f"space would make it unreferenceable."
        )
        raise MountConfigError(msg)
    # Trailing slashes are stripped by the caller, so only interior empties
    # are a problem here. ``"a//b".strip("/").split("/")`` is ``['a', '', 'b']``.
    segments = value.strip("/").split("/")
    if any(segment in ("", ".") for segment in segments):
        msg = (
            f"{field_name} must not contain an empty or '.' path segment; got "
            f"{value!r}. Docnames are matched literally, not resolved as "
            f"filesystem paths, so 'a/./b' is a different docname from 'a/b' "
            f"and '.' is not a way to write the project root — omit "
            f"{field_name} instead."
        )
        raise MountConfigError(msg)
    if any(segment != segment.strip() for segment in segments):
        msg = (
            f"{field_name} must not have whitespace around a path segment; "
            f"got {value!r}."
        )
        raise MountConfigError(msg)


def parse_mounts(raw: Any, confdir: Path) -> tuple[MountConfig, ...]:
    """Validate and normalize the user-provided ``mounts`` config.

    :param raw: Whatever the user set ``mounts`` to in ``conf.py``, or the
        list extracted from the TOML config file. Expected to be a sequence
        of mappings or :class:`MountConfig` instances.
    :param confdir: Confdir path, used to resolve relative ``dir`` paths.
    :return: Tuple of validated mount configs with absolute ``dir`` paths.
    :raises MountConfigError: If ``raw`` is not a sequence of mappings, a
        mapping fails validation, or a ``dir``/``files`` path cannot be
        resolved. These are hard, non-suppressible errors — the build
        cannot proceed with an unreadable configuration. A path that
        resolves but does *not exist on disk* is not an error here: it is
        reported as a ``mounts.missing_path`` warning at mount time, so a
        build whose upstream bundle is absent (e.g. CI that has not run the
        Bazel build yet) can still proceed.
    """
    if raw is None:
        return ()
    if not isinstance(raw, list | tuple):
        msg = f"`mounts` must be a list of mappings; got {type(raw).__name__}."
        raise MountConfigError(msg)

    resolved: list[MountConfig] = []
    for index, entry in enumerate(raw):
        mount = _entry_to_mount_config(entry, index)
        resolved_dir = (
            _resolve_dir(mount.dir, confdir) if mount.dir is not None else None
        )
        resolved_files = (
            _resolve_files(mount.files, confdir) if mount.files is not None else None
        )
        resolved.append(
            MountConfig(
                mount_at=mount.mount_at,
                dir=resolved_dir,
                files=resolved_files,
                include=mount.include,
                exclude=mount.exclude,
                gitignore=mount.gitignore,
                attach_to=mount.attach_to,
                toctree_index=mount.toctree_index,
                entry_doc=mount.entry_doc,
                attach_each=mount.attach_each,
                strict_mount_at=mount.strict_mount_at,
                path_check=mount.path_check,
            )
        )
    return tuple(resolved)


def _entry_to_mount_config(entry: Any, index: int) -> MountConfig:
    if isinstance(entry, MountConfig):
        return entry
    if isinstance(entry, Mapping):
        return MountConfig.from_dict(entry)
    msg = (
        f"`mounts[{index}]` must be a mapping or MountConfig; "
        f"got {type(entry).__name__}."
    )
    raise MountConfigError(msg)


def _resolve_dir(mount_dir: Path, confdir: Path) -> Path:
    # Existence is checked at mount time (warn + skip), so a missing
    # directory does not fail the whole build here.
    return (
        (confdir / mount_dir).resolve()
        if not mount_dir.is_absolute()
        else mount_dir.resolve()
    )


def _resolve_files(files: tuple[Path, ...], confdir: Path) -> tuple[Path, ...]:
    # Existence is checked per file at mount time (warn + skip).
    return tuple(
        (confdir / raw_file).resolve()
        if not raw_file.is_absolute()
        else raw_file.resolve()
        for raw_file in files
    )


#: Spelling recommended for new projects: ``[source]`` is the table that owns
#: source *discovery* in the shared ``ubproject.toml`` vocabulary, which is
#: where a mount belongs, and namespacing keeps the file's root from becoming
#: a flat bag of keys.
NAMESPACED_MOUNTS_LOCATION = "[[source.mounts]]"

#: The original spelling. Still fully supported — projects that use it do not
#: need to change anything — but new projects should prefer
#: :data:`NAMESPACED_MOUNTS_LOCATION`.
TOP_LEVEL_MOUNTS_LOCATION = "[[mounts]]"


def load_mounts_from_toml(toml_path: Path) -> list[dict[str, Any]] | None:
    """Load the raw ``mounts`` list from a TOML configuration file.

    The array of tables is declared under ``[source]``:

    .. code-block:: toml

       [[source.mounts]]
       dir = "../other/docs"
       mount_at = "guides/other"
       include = ["**/*.rst"]       # optional allowlist
       exclude = ["**/internal/**", "*.tmp"]
       gitignore = false            # don't honour the sibling repo's .gitignore
       attach_to = "index"          # extend a toctree in index.rst
       toctree_index = 0            # which toctree (0-based)
       entry_doc = "index"          # which file inside the mount

    ``[source]`` is the table that owns source *discovery* in the
    ``ubproject.toml`` vocabulary shared with sibling tooling, and namespacing
    keeps the file's root from becoming a flat bag of keys.

    The original top-level ``[[mounts]]`` spelling is **deprecated**. It is
    still read, with identical meaning in every respect, and reported as
    ``mounts.deprecated_location``. It is deliberately still honoured rather
    than ignored: sibling readers of this same file recognise only
    ``[[source.mounts]]``, so warning-while-honouring is what keeps both
    readers agreeing about the project during a migration.

    Declaring **both** in one file is a hard error rather than a precedence
    puzzle: which one wins is not something a reader should have to know. A
    deprecated declaration is still a declaration.

    The TOML file is the *primary* config target so that non-Python tooling
    (IDE extensions, language servers, build-system integrations) can read
    the same configuration without evaluating ``conf.py``.

    **Path anchoring.** Relative paths in ``dir`` and ``files`` are
    resolved to absolute paths against the **directory containing
    ``toml_path``**, not against the Sphinx ``confdir``. The TOML file
    is self-describing: moving it as a unit keeps its relative paths
    meaningful, and a TOML placed in a subdirectory of ``confdir`` does
    not silently re-anchor. Absolute paths are left untouched.

    :param toml_path: Absolute path to a TOML file. May or may not exist.
    :return: The raw list of mount tables (each a ``dict``), or ``None`` if
        ``toml_path`` does not exist or declares neither spelling. Returning
        ``None`` is not an error — callers fall back to the ``mounts`` value
        from ``conf.py``. Note that an explicitly declared *empty* array is
        not ``None``: it is a deliberate "this project has no mounts" and
        does override ``conf.py``.
    :raises TomlConfigError: If the file exists but is not valid TOML, if it
        declares both spellings, or if the mounts array has the wrong shape.
    """
    if not toml_path.is_file():
        return None
    try:
        with toml_path.open("rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        msg = f"sphinx-mounts: failed to parse TOML config {toml_path}: {e}"
        raise TomlConfigError(msg) from e

    extracted = _extract_toml_mounts(data, toml_path)
    if extracted is None:
        return None
    _anchor_toml_paths(extracted, toml_path.parent)
    return extracted


def _extract_toml_mounts(
    data: Mapping[str, Any], toml_path: Path
) -> list[dict[str, Any]] | None:
    """Pick the mounts array out of parsed TOML data and validate its shape.

    :return: The raw list, or ``None`` when neither spelling is declared.
    :raises TomlConfigError: If both spellings are declared, or the declared
        one is not an array of tables.
    """
    source = data.get("source")
    declared: list[tuple[str, Any]] = []
    if isinstance(source, Mapping) and "mounts" in source:
        declared.append((NAMESPACED_MOUNTS_LOCATION, source["mounts"]))
    if "mounts" in data:
        declared.append((TOP_LEVEL_MOUNTS_LOCATION, data["mounts"]))

    if len(declared) > 1:
        locations = " and ".join(location for location, _ in declared)
        msg = (
            f"sphinx-mounts: {toml_path} declares mounts in two places: "
            f"{locations}. Keep exactly one — merging them silently, or "
            f"picking a winner, would make the effective mount list depend on "
            f"a precedence rule nobody reading the file can see. "
            f"{NAMESPACED_MOUNTS_LOCATION} is the recommended spelling."
        )
        raise TomlConfigError(msg)
    if not declared:
        return None

    location, raw_mounts = declared[0]
    if location == TOP_LEVEL_MOUNTS_LOCATION:
        msg = (
            f"sphinx-mounts: `{TOP_LEVEL_MOUNTS_LOCATION}` in {toml_path} is "
            f"deprecated; rename the table header to "
            f"`{NAMESPACED_MOUNTS_LOCATION}`. Nothing else changes — the keys, "
            f"path anchoring and validation are identical. Suppress with "
            f'suppress_warnings = ["mounts.deprecated_location"] if you cannot '
            f"migrate yet."
        )
        log_warning(logger, msg, "deprecated_location")
    if not isinstance(raw_mounts, list):
        msg = (
            f"sphinx-mounts: `{location}` in {toml_path} must be an "
            f"array of tables; got {type(raw_mounts).__name__}."
        )
        raise TomlConfigError(msg)
    for index, entry in enumerate(raw_mounts):
        if not isinstance(entry, dict):
            msg = (
                f"sphinx-mounts: entry {index} of `{location}` in "
                f"{toml_path} must be a table; got {type(entry).__name__}."
            )
            raise TomlConfigError(msg)
    return raw_mounts


def _anchor_toml_paths(raw_mounts: list[dict[str, Any]], base_dir: Path) -> None:
    """Make every relative ``dir`` / ``files`` path absolute against
    ``base_dir``. Mutates ``raw_mounts`` in place. Non-string values and
    already-absolute paths are left untouched; semantic validation of
    types and shapes happens later in :meth:`MountConfig.from_dict`."""
    for entry in raw_mounts:
        if "dir" in entry:
            entry["dir"] = _anchor_one_path(entry["dir"], base_dir)
        if "files" in entry and isinstance(entry["files"], list):
            entry["files"] = [_anchor_one_path(f, base_dir) for f in entry["files"]]


def _anchor_one_path(value: Any, base_dir: Path) -> Any:
    """Return ``value`` unchanged unless it is a relative path string,
    in which case return its absolute form anchored to ``base_dir``."""
    if not isinstance(value, str):
        return value
    p = Path(value)
    if p.is_absolute():
        return value
    return str((base_dir / p).resolve())


# ---------------------------------------------------------------------------
# `[[source.variant_sources]]` — the variant rule reader
# ---------------------------------------------------------------------------


class VariantRuleError(ExtensionError):
    """Raised when a ``[[source.variant_sources]]`` rule cannot be honoured.

    Subclasses :class:`sphinx.errors.ExtensionError` for the same reason as
    :class:`TomlConfigError`, and for one more that is specific to this key:
    **report-and-drop fails OPEN.** Skipping a rule this reader cannot
    interpret leaves every file the rule named — including the files its
    perfectly valid patterns named — in the build, behind a diagnostic a
    project could suppress. For a key whose only purpose is keeping content out
    of a build, that is the one outcome that must not be possible, so the whole
    configuration is refused instead.

    Every message lists **every** offender at once. Fixing one refused pattern
    only to meet the next on the following build is the behaviour this avoids.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message, modname="sphinx_mounts")


#: The key holding the rule array, nested under ``[source]``.
VARIANT_SOURCES_LOCATION = "[[source.variant_sources]]"

#: Keys a ``variant_sources`` entry may carry. Anything else is reported and
#: ignored, matching the mount-entry posture (see :meth:`MountConfig.from_dict`)
#: and ubCode's ``config.variant_source_unknown_key``.
VARIANT_RULE_KEYS = frozenset({"if", "files"})


@dataclass(frozen=True, slots=True)
class VariantRule:
    """One ``[[source.variant_sources]]`` entry, as authored.

    Fields:
        index: Position in the rule array, for messages that must name a rule.
        condition: The ``if`` expression, exactly as written.
        files: The rule's glob patterns, exactly as written. Kept authored
            rather than translated because a message has to be able to quote
            the spelling the user can edit, and because the two translations
            (:mod:`sphinx_mounts.dialect`) are per-target.
    """

    index: int
    condition: str
    files: tuple[str, ...]

    @property
    def label(self) -> str:
        """Human-readable identifier used in every message about this rule."""
        return f"{VARIANT_SOURCES_LOCATION}[{self.index}] (if = {self.condition!r})"


@dataclass(frozen=True, slots=True)
class VariantSourcesConfig:
    """Everything the variant reader takes out of one TOML file.

    Deliberately only three things, and never a general ``[source]`` bridge:
    the rule array, the source roots the rules anchor at, and the ``[needs]``
    variant-data fallback. ``mapping-contract.md`` §1 rule 5 — nesting under
    ``[source]`` implies no inheritance — still holds for everything else.

    Fields:
        toml_path: The file these values came from.
        source_root: The resolved root a rule glob is anchored at. The layout
            guard compares it against Sphinx's ``srcdir``.
        rules: The declared rules, in array order.
        declared: Whether the ``variant_sources`` key was present at all. An
            empty array is a declaration ("this project has no rules") and is
            distinct from an absent key, exactly as ``mounts = []`` is.
        variant_data: The ``[needs] variant_data`` table, or ``None``.
        variant_data_file: The ``[needs] variant_data_file`` path, anchored at
            the TOML's own directory (the anchor sphinx-needs' own
            ``toml_convert`` applies to the same key).
    """

    toml_path: Path
    source_root: Path
    rules: tuple[VariantRule, ...]
    declared: bool
    variant_data: dict[str, Any] | None
    variant_data_file: Path | None


def load_variant_sources_from_toml(toml_path: Path) -> VariantSourcesConfig | None:
    """Read ``[[source.variant_sources]]`` and its data fallback from a TOML file.

    .. code-block:: toml

       [source]
       dir = "source"                   # optional; the rules' anchor

       [[source.variant_sources]]
       if = "var.edition == 'pro'"
       files = ["reference/pro/**/*.rst"]

       [needs]                          # read only when sphinx-needs is absent
       variant_data_file = "variants.json"

       [needs.variant_data]
       edition = "basic"

    **Only these keys are read.** This is not a general ``[source]`` bridge:
    everything else under ``[source]`` belongs to whichever tool owns it, and
    ``[needs]`` is consulted purely as a fallback for the variant map when
    sphinx-needs is not installed to provide it.

    :param toml_path: Absolute path to a TOML file. May or may not exist.
    :return: The parsed values, or ``None`` when the file does not exist.
    :raises TomlConfigError: If the file is not valid TOML, or the rule array
        or an entry has the wrong shape.
    """
    if not toml_path.is_file():
        return None
    try:
        with toml_path.open("rb") as handle:
            data = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        msg = f"sphinx-mounts: failed to parse TOML config {toml_path}: {exc}"
        raise TomlConfigError(msg) from exc

    source = data.get("source")
    source = source if isinstance(source, Mapping) else {}
    project = data.get("project")
    project = project if isinstance(project, Mapping) else {}
    needs = data.get("needs")
    needs = needs if isinstance(needs, Mapping) else {}

    raw_rules = source.get("variant_sources")
    declared = "variant_sources" in source
    rules = _extract_variant_rules(raw_rules, toml_path) if declared else ()

    return VariantSourcesConfig(
        toml_path=toml_path,
        source_root=_extract_source_root(source, project, toml_path),
        rules=rules,
        declared=declared,
        variant_data=_extract_variant_data(needs.get("variant_data"), toml_path),
        variant_data_file=_extract_variant_data_file(
            needs.get("variant_data_file"), toml_path
        ),
    )


def _extract_source_root(
    source: Mapping[str, Any], project: Mapping[str, Any], toml_path: Path
) -> Path:
    """Resolve the single root a rule glob is anchored at.

    ubCode's precedence, reproduced: ``[source] dir`` wins; the deprecated
    ``[project] srcdir`` stands when ``dir`` is unset; otherwise the root is
    the TOML file's own directory. Reading only the first of those was a
    fail-open hole — a project on the legacy key anchored its rules at the TOML
    directory here and at ``<toml dir>/<srcdir>`` in ubCode, and the layout
    guard passed on the wrong root with nothing said.

    **``dir`` is a STRING, not an array.** ubCode declares it as one
    (``Field<PathBuf>``, ``"type": "string"`` in its published schema), so an
    array is a hard deserialization failure there. Accepting one here would be
    a divergence of its own, and — worse — the layout refusal used to *advise*
    the array form, which would have left the project unreadable by the other
    tool. Both are fixed together.

    An empty string means unset, matching ubCode's documented ``""`` ≡ unset
    sentinel.

    Anchored at the TOML's own directory and then resolved, exactly as a
    mount's ``dir`` is (``mapping-contract.md`` §3), so the two cannot drift.
    """
    raw = source.get("dir")
    key = "[source] dir"
    if raw is None or raw == "":
        raw = project.get("srcdir")
        key = "[project] srcdir"
    if raw is None or raw == "":
        return toml_path.parent.resolve()
    if not isinstance(raw, str):
        shape = "an array" if isinstance(raw, list) else type(raw).__name__
        msg = (
            f"sphinx-mounts: `{key}` in {toml_path} must be a string; got "
            f"{shape}. It names ONE source root — sibling tools that read this "
            f"same file declare it as a string and reject any other shape, so "
            f'a project writing `dir = ["source"]` becomes unreadable to them. '
            f'Write `dir = "source"`.'
        )
        raise TomlConfigError(msg)
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate.resolve()
    return (toml_path.parent / candidate).resolve()


def _extract_variant_rules(raw: Any, toml_path: Path) -> tuple[VariantRule, ...]:
    """Validate the rule array's shape and turn it into :class:`VariantRule` s.

    Shape problems are hard :class:`TomlConfigError` s, matching
    :func:`_extract_toml_mounts`: a rule array this reader cannot even parse
    says nothing about which files the variant contains, and guessing is how a
    gating key fails open. Unknown *keys* are the exception — reported and
    ignored, per :data:`VARIANT_RULE_KEYS`.
    """
    if not isinstance(raw, list):
        msg = (
            f"sphinx-mounts: `{VARIANT_SOURCES_LOCATION}` in {toml_path} must "
            f"be an array of tables; got {type(raw).__name__}."
        )
        raise TomlConfigError(msg)
    rules: list[VariantRule] = []
    for index, entry in enumerate(raw):
        rules.append(_extract_variant_rule(entry, index, toml_path))
    return tuple(rules)


def _extract_variant_rule(entry: Any, index: int, toml_path: Path) -> VariantRule:
    """Validate one rule entry."""
    where = f"entry {index} of `{VARIANT_SOURCES_LOCATION}` in {toml_path}"
    if not isinstance(entry, Mapping):
        msg = f"sphinx-mounts: {where} must be a table; got {type(entry).__name__}."
        raise TomlConfigError(msg)
    unknown = sorted(set(entry) - VARIANT_RULE_KEYS)
    if unknown:
        msg = (
            f"sphinx-mounts: unknown `variant_sources` key(s) {unknown} on "
            f"{where}; they are ignored. Supported keys are "
            f"{sorted(VARIANT_RULE_KEYS)}."
        )
        log_warning(logger, msg, "unknown_key")
    condition = entry.get("if")
    if not isinstance(condition, str):
        msg = (
            f"sphinx-mounts: {where} must declare `if` as a string condition; "
            f"got {type(condition).__name__}."
        )
        raise TomlConfigError(msg)
    files = entry.get("files")
    if not isinstance(files, list) or not all(isinstance(item, str) for item in files):
        msg = (
            f"sphinx-mounts: {where} must declare `files` as an array of glob "
            f"strings; got {type(files).__name__}."
        )
        raise TomlConfigError(msg)
    return VariantRule(index=index, condition=condition, files=tuple(files))


def _extract_variant_data(raw: Any, toml_path: Path) -> dict[str, Any] | None:
    """Pick ``[needs] variant_data`` out of the file, checking only its type."""
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        msg = (
            f"sphinx-mounts: `[needs] variant_data` in {toml_path} must be a "
            f"table; got {type(raw).__name__}."
        )
        raise TomlConfigError(msg)
    return dict(raw)


def _extract_variant_data_file(raw: Any, toml_path: Path) -> Path | None:
    """Anchor ``[needs] variant_data_file`` at the TOML's own directory.

    This is the first of the **two anchors** a reader of this key has to
    reproduce. sphinx-needs absolutises a TOML-declared ``variant_data_file``
    against the TOML file's directory (its ``toml_convert`` metadata), and
    leaves a ``conf.py``- or ``-D``-declared one to be absolutised against
    ``confdir``. Reading only one of the two anchors means reading the wrong
    file for one of the two routes.
    """
    if raw is None:
        return None
    if not isinstance(raw, str):
        msg = (
            f"sphinx-mounts: `[needs] variant_data_file` in {toml_path} must "
            f"be a string; got {type(raw).__name__}."
        )
        raise TomlConfigError(msg)
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate.resolve()
    return (toml_path.parent / candidate).resolve()
