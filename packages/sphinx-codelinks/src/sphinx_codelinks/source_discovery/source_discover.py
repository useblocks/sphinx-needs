from collections.abc import Callable
import fnmatch
import os
from pathlib import Path

from gitignore_parser import parse_gitignore  # type: ignore[import-untyped]


class SourceDiscover:
    def __init__(
        self,
        src_dir: Path,
        exclude: list[str] | None = None,
        include: list[str] | None = None,
        gitignore: bool = True,
        file_types: list[str] | None = None,
    ):
        self.root_path = src_dir
        self.exclude = exclude
        self.include = include
        # Only gitignore at source root is considered.
        # TODO: Support nested gitignore files
        gitignore_path = self.root_path / ".gitignore"
        self.gitignore_matcher: Callable[[str], bool] | None = (
            parse_gitignore(gitignore_path)
            if gitignore and gitignore_path.exists()
            else None
        )
        # normalize the file types to lower case with leading dot
        self.file_types = (
            {
                file_type.lower()
                if file_type.startswith(".")
                else f".{file_type}".lower()
                for file_type in file_types
            }
            if file_types
            else None
        )

        self.source_paths = self._discover()

    def _discover(self) -> list[Path]:
        """Discover source files recursively in the given directory."""
        discovered_files = []
        for filepath in self.root_path.rglob("*"):
            if filepath.is_file():
                if self.file_types and filepath.suffix.lower() not in self.file_types:
                    continue
                rel_filepath = str(filepath.relative_to(self.root_path))
                if self.include and self._matches_any(rel_filepath, self.include):
                    # "includes" has the highest priority over "gitignore" and "excludes"
                    discovered_files.append(filepath)
                    continue
                if self.gitignore_matcher and self.gitignore_matcher(
                    str(filepath.absolute())
                ):
                    continue
                if self.exclude and self._matches_any(rel_filepath, self.exclude):
                    continue
                discovered_files.append(filepath)
        sorted_filepaths = sorted(
            discovered_files, key=lambda x: os.path.normcase(os.path.normpath(x))
        )
        return sorted_filepaths

    def _matches_any(self, rel_filepath: str, patterns: list[str]) -> bool:
        """Check if the given file path matches any of the given patterns."""
        return any(fnmatch.fnmatch(rel_filepath, pattern) for pattern in patterns)
