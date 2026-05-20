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


class TomlConfigError(Exception):
    """Raised when the TOML config file cannot be parsed or is malformed."""


class MountConfigError(ValueError):
    """Raised when a mount configuration entry is invalid."""


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
            number of toctrees present, the build fails loudly.
        entry_doc: Mount-relative docname of the entry document to wire
            into the host toctree. Defaults to ``"index"``. The resulting
            docname is ``f"{mount_at}/{entry_doc}"`` — or just
            ``entry_doc`` when ``mount_at`` is ``None``. This is the
            *only* doc auto-attached; any other docs in the mount must
            be reachable from the entry doc via its own toctree / refs.
        strict_mount_at: When ``True``, fail the build if the host
            project already has a directory at ``<srcdir>/<mount_at>/``.
            Defaults to ``False`` — the existing per-docname collision
            check is the only gate, which lets a mount slot under a
            host-owned staging directory that holds non-source siblings
            (assets, READMEs). Set to ``True`` to treat any host
            directory at ``mount_at`` as a misconfiguration, catching
            the mistake earlier than per-docname collisions would.
            Incompatible with a root mount (``mount_at = None``), since
            the host srcdir always exists; that combination is rejected
            at config validation.
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
    strict_mount_at: bool = False

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
            msg = (
                f"Unknown mount keys: {sorted(unknown)}. "
                f"Allowed keys are {sorted(allowed)}."
            )
            raise MountConfigError(msg)
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
            strict_mount_at=entry.get("strict_mount_at", False),
        )


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


def _validate_relative_docname(field_name: str, value: object) -> None:
    """Validate a relative docname-shaped string field.

    Used by :class:`MountConfig` for ``mount_at``, ``attach_to``, and
    ``entry_doc``. Rejects non-strings, empty strings, leading slashes,
    and ``..`` components. Does *not* normalize — that is the caller's
    responsibility, since each field has a slightly different normalization
    rule (mount_at strips slashes; entry_doc keeps its shape).
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


def parse_mounts(raw: Any, confdir: Path) -> tuple[MountConfig, ...]:
    """Validate and normalize the user-provided ``mounts`` config.

    :param raw: Whatever the user set ``mounts`` to in ``conf.py``, or the
        list extracted from the TOML config file. Expected to be a sequence
        of mappings or :class:`MountConfig` instances.
    :param confdir: Confdir path, used to resolve relative ``dir`` paths.
    :return: Tuple of validated mount configs with absolute ``dir`` paths.
    :raises TypeError: If ``raw`` is not a sequence of mappings.
    :raises MountConfigError: If a mapping fails validation.
    :raises FileNotFoundError: If a ``dir`` directory does not exist.
    """
    if raw is None:
        return ()
    if not isinstance(raw, list | tuple):
        msg = f"`mounts` must be a list of mappings; got {type(raw).__name__}."
        raise TypeError(msg)

    resolved: list[MountConfig] = []
    for index, entry in enumerate(raw):
        mount = _entry_to_mount_config(entry, index)
        resolved_dir = (
            _resolve_dir(mount.dir, confdir, index) if mount.dir is not None else None
        )
        resolved_files = (
            _resolve_files(mount.files, confdir, index)
            if mount.files is not None
            else None
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
                strict_mount_at=mount.strict_mount_at,
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
    raise TypeError(msg)


def _resolve_dir(mount_dir: Path, confdir: Path, index: int) -> Path:
    resolved = (
        (confdir / mount_dir).resolve()
        if not mount_dir.is_absolute()
        else mount_dir.resolve()
    )
    if not resolved.is_dir():
        msg = f"`mounts[{index}].dir` does not exist or is not a directory: {resolved}"
        raise FileNotFoundError(msg)
    return resolved


def _resolve_files(
    files: tuple[Path, ...], confdir: Path, index: int
) -> tuple[Path, ...]:
    file_list: list[Path] = []
    for file_index, raw_file in enumerate(files):
        f = (
            (confdir / raw_file).resolve()
            if not raw_file.is_absolute()
            else raw_file.resolve()
        )
        if not f.is_file():
            msg = (
                f"`mounts[{index}].files[{file_index}]` does not exist or is "
                f"not a file: {f}"
            )
            raise FileNotFoundError(msg)
        file_list.append(f)
    return tuple(file_list)


def load_mounts_from_toml(toml_path: Path) -> list[dict[str, Any]] | None:
    """Load the raw ``mounts`` list from a TOML configuration file.

    The TOML file is expected to declare a top-level ``[[mounts]]`` array of
    tables, one block per mount, with the same keys accepted by
    :class:`MountConfig`:

    .. code-block:: toml

       [[mounts]]
       dir = "/abs/path/to/bundle"
       mount_at = "_generated/api-foo"

       [[mounts]]
       dir = "../other/docs"
       mount_at = "guides/other"
       include = ["**/*.rst"]       # optional allowlist
       exclude = ["**/internal/**", "*.tmp"]
       gitignore = false            # don't honour the sibling repo's .gitignore
       attach_to = "index"          # extend a toctree in index.rst
       toctree_index = 0            # which toctree (0-based)
       entry_doc = "index"          # which file inside the mount

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
        ``toml_path`` does not exist or contains no top-level ``mounts``
        array. Returning ``None`` is not an error — callers fall back to
        the ``mounts`` value from ``conf.py``.
    :raises TomlConfigError: If the file exists but is not valid TOML, or
        if the top-level ``mounts`` key has the wrong shape.
    """
    if not toml_path.is_file():
        return None
    try:
        with toml_path.open("rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        msg = f"sphinx-mounts: failed to parse TOML config {toml_path}: {e}"
        raise TomlConfigError(msg) from e

    raw_mounts = data.get("mounts")
    if raw_mounts is None:
        return None
    if not isinstance(raw_mounts, list):
        msg = (
            f"sphinx-mounts: top-level `mounts` in {toml_path} must be an "
            f"array of tables; got {type(raw_mounts).__name__}."
        )
        raise TomlConfigError(msg)
    for index, entry in enumerate(raw_mounts):
        if not isinstance(entry, dict):
            msg = (
                f"sphinx-mounts: `mounts[{index}]` in {toml_path} must be a "
                f"table; got {type(entry).__name__}."
            )
            raise TomlConfigError(msg)

    _anchor_toml_paths(raw_mounts, toml_path.parent)
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
