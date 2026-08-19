import os
from pathlib import Path

from ignore import WalkBuilder
from ignore.overrides import OverrideBuilder

from sphinx_codelinks.logger import get_logger
from sphinx_codelinks.source_discover.config import (
    COMMENT_FILETYPE,
    CommentType,
    SourceDiscoverConfig,
)

logger = get_logger(__name__)


def lies_within(path: Path, directory: Path) -> bool:
    """Whether ``path`` lies below ``directory``, both resolved.

    Strings, not ``Path.is_relative_to``, which costs as much as the walk itself over
    thousands of files. ``normcase`` folds case on Windows; on a case-insensitive POSIX
    file system (APFS) a differently-spelled ancestor still counts as outside --
    harmless, the file is traced under its own spelling.
    """
    prefix = os.path.join(os.path.normcase(str(directory)), "")
    return os.path.normcase(str(path)).startswith(prefix)


def warn_outside_src_dir(walked: Path, resolved: Path, src_dir: Path) -> None:
    """Say that ``walked`` -- the path discovery reached, the link -- is not traced:
    it resolves to outside ``src_dir``. POSIX on every platform.

    The walked path leads the message rather than being its location: the CLI prints
    the message alone, and Sphinx reads a location without a ``:`` as a document
    name (``<path>.rst``) -- while a Windows path has one. It is normalised for the
    message only (``src/../x.cpp`` reads ``x.cpp``).
    """
    shown = Path(os.path.normpath(walked)).as_posix()
    logger.warning(
        f"{shown} resolves to {resolved.as_posix()}, outside src_dir "
        f"{src_dir.as_posix()}: not traced (widen src_dir to cover it, or exclude "
        "the link)",
        subtype="outside_src_dir",
    )


def _json_starts_with_comment(filepath: Path, sample_size: int = 256) -> bool:
    """Return True if a ``.json`` file's first non-whitespace content is a comment.

    Used to decide whether a ``.json`` file should be treated as JSONC. Per
    https://jsonc.org/#filename-extension a ``.json`` file should only be treated as
    JSONC when it opens with a comment (e.g. the mode line ``// -*- mode: jsonc -*-``).
    """
    try:
        with filepath.open("rb") as f:
            chunk = f.read(sample_size)
    except OSError:
        return False
    # strip a leading UTF-8 BOM, then leading whitespace
    text = chunk.removeprefix(b"\xef\xbb\xbf").lstrip()
    return text.startswith((b"//", b"/*"))


# @Source code file discovery with gitignore support, IMPL_DISC_1, impl, [FE_DISCOVERY, FE_CLI_DISCOVER]
class SourceDiscover:
    """The source files below ``src_discover_config.src_dir``, as ``source_paths``.

    A file that resolves to outside ``boundary`` -- a symbolic link out of the tree, or
    a file below a followed directory link -- is not listed, and a warning names
    its walked path (``codelinks.outside_src_dir``) unless ``warn`` is false: every
    record and copy is relative to the source directory, which cannot hold it.

    :param src_discover_config: What to walk, and how.
    :param boundary: The directory every listed file lies below; the walked directory
        when ``None``. A ``src-trace`` scope passes its project's ``src_dir``, which
        its ``:directory:`` lies below.
    :param warn: Whether to warn about a file outside ``boundary``.
    """

    def __init__(
        self,
        src_discover_config: SourceDiscoverConfig,
        *,
        boundary: Path | None = None,
        warn: bool = True,
    ):
        self.src_discover_config = src_discover_config
        self.boundary = boundary
        self.warn = warn
        # normalize the file types to lower case with leading dot
        self.file_types = {
            f".{ext}" for ext in COMMENT_FILETYPE[src_discover_config.comment_type]
        }

        self.source_paths = self._discover()

    def _build_overrides(self) -> OverrideBuilder | None:
        """Build an OverrideBuilder for include/exclude patterns.

        Include patterns are added as whitelist globs.
        Exclude patterns are added as negated globs (prefixed with ``!``).
        """
        include = self.src_discover_config.include
        # ``SourceDiscoverConfig.__post_init__`` always resolves ``exclude``
        # to a concrete list (never leaves it ``None``); the ``| None`` on
        # the field itself only exists to detect "not explicitly set".
        exclude = self.src_discover_config.exclude

        if not include and not exclude:
            return None

        ob = OverrideBuilder(self.src_discover_config.src_dir)

        if include:
            for pattern in include:
                ob.add(pattern)

        if exclude:
            for pattern in exclude:
                ob.add(f"!{pattern}")

        return ob

    def _discover(self) -> list[Path]:
        """Discover source files recursively in the given directory."""
        src_dir = self.src_discover_config.src_dir
        if not src_dir.is_dir():
            return []

        gitignore = self.src_discover_config.gitignore

        builder = WalkBuilder(src_dir)
        # Replicate the Rust ignore crate's standard_filters(gitignore)
        # followed by hidden(false), matching ubc_codelinks behaviour.
        builder.ignore(gitignore)
        builder.parents(gitignore)
        builder.git_ignore(gitignore)
        builder.git_global(gitignore)
        builder.git_exclude(gitignore)
        builder.hidden(False)
        builder.follow_links(self.src_discover_config.follow_links)

        override_builder = self._build_overrides()
        if override_builder is not None:
            builder.overrides(override_builder.build())

        boundary = (self.boundary or src_dir).resolve()
        discovered_files = []
        for entry in builder.build():
            filepath = entry.path()
            if not filepath.is_file():
                continue
            if self.file_types and filepath.suffix.lower() not in self.file_types:
                continue
            # @JSONC .json files require a leading comment, IMPL_JSONC_3, impl, [FE_JSONC]
            # A plain ``.json`` file is only treated as JSONC when it opens with a
            # comment; otherwise it is skipped under the ``jsonc`` comment type.
            if (
                self.src_discover_config.comment_type == CommentType.jsonc
                and filepath.suffix.lower() == ".json"
                and not _json_starts_with_comment(filepath)
            ):
                continue
            # resolve() produces canonical absolute paths; follow_links only
            # controls whether the walker descends into symlinked directories
            resolved = filepath.resolve()
            if not lies_within(resolved, boundary):
                # a link out of the tree: no root-relative path, no copy (#2062)
                if self.warn:
                    warn_outside_src_dir(filepath, resolved, boundary)
                continue
            discovered_files.append(resolved)

        # a file reached through a symbolic link inside the tree resolves to a path
        # already found: list each file once, or every caller analyses it once per
        # path to it
        sorted_filepaths = sorted(
            dict.fromkeys(discovered_files),
            key=lambda x: os.path.normcase(os.path.normpath(x)),
        )
        return sorted_filepaths
