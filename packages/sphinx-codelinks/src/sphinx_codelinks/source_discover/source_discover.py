from collections.abc import Callable
import fnmatch
import os
from pathlib import Path

from gitignore_parser import (  # type: ignore[import-untyped]  # library has no stub
    parse_gitignore,
)

from sphinx_codelinks.source_discover.config import (
    COMMENT_FILETYPE,
    SourceDiscoverConfig,
)


class SourceDiscover:
    def __init__(self, src_discover_config: SourceDiscoverConfig):
        self.src_discover_config = src_discover_config
        # Only gitignore at source root is considered.
        # TODO: Support nested gitignore files
        gitignore_path = self.src_discover_config.src_dir / ".gitignore"
        self.gitignore_matcher: Callable[[str], bool] | None = (
            parse_gitignore(gitignore_path)
            if self.src_discover_config.gitignore and gitignore_path.exists()
            else None
        )
        # normalize the file types to lower case with leading dot
        self.file_types = {
            f".{ext}" for ext in COMMENT_FILETYPE[src_discover_config.comment_type]
        }

        self.source_paths = self._discover()

    def _discover(self) -> list[Path]:
        """Discover source files recursively in the given directory."""
        discovered_files = []
        for filepath in self.src_discover_config.src_dir.rglob("*"):
            if filepath.is_file():
                if self.file_types and filepath.suffix.lower() not in self.file_types:
                    continue
                rel_filepath = str(
                    filepath.relative_to(self.src_discover_config.src_dir)
                )
                if self.src_discover_config.include and self._matches_any(
                    rel_filepath, self.src_discover_config.include
                ):
                    # "includes" has the highest priority over "gitignore" and "excludes"
                    discovered_files.append(filepath)
                    continue
                if self.gitignore_matcher and self.gitignore_matcher(
                    str(filepath.absolute())
                ):
                    continue
                if self.src_discover_config.exclude and self._matches_any(
                    rel_filepath, self.src_discover_config.exclude
                ):
                    continue
                discovered_files.append(filepath)
        sorted_filepaths = sorted(
            discovered_files, key=lambda x: os.path.normcase(os.path.normpath(x))
        )
        return sorted_filepaths

    def _matches_any(self, rel_filepath: str, patterns: list[str]) -> bool:
        """Check if the given file path matches any of the given patterns."""
        return any(fnmatch.fnmatch(rel_filepath, pattern) for pattern in patterns)
