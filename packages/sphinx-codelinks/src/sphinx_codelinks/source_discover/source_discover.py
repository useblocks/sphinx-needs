import os
from pathlib import Path

from ignore import WalkBuilder
from ignore.overrides import OverrideBuilder

from sphinx_codelinks.source_discover.config import (
    COMMENT_FILETYPE,
    CommentType,
    SourceDiscoverConfig,
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
    def __init__(self, src_discover_config: SourceDiscoverConfig):
        self.src_discover_config = src_discover_config
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
        has_include = bool(self.src_discover_config.include)
        has_exclude = bool(self.src_discover_config.exclude)

        if not has_include and not has_exclude:
            return None

        ob = OverrideBuilder(self.src_discover_config.src_dir)

        if has_include:
            for pattern in self.src_discover_config.include:
                ob.add(pattern)

        if has_exclude:
            for pattern in self.src_discover_config.exclude:
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
            discovered_files.append(filepath.resolve())

        sorted_filepaths = sorted(
            discovered_files, key=lambda x: os.path.normcase(os.path.normpath(x))
        )
        return sorted_filepaths
