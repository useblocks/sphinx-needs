import json
from pathlib import Path
from typing import cast


class MultipleMarkerError(Exception):
    """Custom exception for multiple markers in a comment."""


class UBTComment:
    """Wrap Comment object from comment_parser."""

    def __init__(
        self,
        text: str,
        start_line: int,
        resolved_marker: dict[str, str | list[str]],
        marker_type: str = "oneline",
    ):
        self.text = text
        # start and end columns are not supported by comment_parser
        # start_line and end_line are the line number of the comment by default.
        # If the marked text exists, they will be line numbers of that.
        self.start_line = start_line
        # so far only one-line comment is taken. end_line is kept for the future multi-line styles
        self.end_line = (
            self.start_line + self.text.count("\n") - 1
            if self.text.count("\n")
            else self.start_line
        )
        self.resolved_marker: dict[str, str | list[str]] = resolved_marker
        self.marker_type: str = marker_type

    def __eq__(self, value):
        if isinstance(value, UBTComment):
            return self.__dict__ == value.__dict__
        return False

    def __hash__(self) -> int:
        return hash(self.__dict__)

    def to_dict(self) -> dict[str, dict[str, str | list[str]] | str | int]:
        return {
            "text": self.text,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "marker_type": self.marker_type,
            "resolved_marker": self.resolved_marker,
        }


class UBTSourceFile:
    def __init__(
        self,
        filepath: Path,
        src_dir: Path,
        comments: list[UBTComment] | None = None,
        output_dir: str = "./",
    ):
        self.filepath: Path = filepath
        self.src_dir: Path = src_dir
        self.comments: list[UBTComment] = []
        if comments:
            self.comments.extend(comments)
        self.output_dir = Path(output_dir)
        self.changed_date = self.filepath.stat().st_mtime

    def __eq__(self, value):
        if isinstance(value, UBTSourceFile):
            return self.__dict__ == value.__dict__
        return False

    def __hash__(self) -> int:
        return hash(self.__dict__)

    def add_comment(self, comment: UBTComment) -> None:
        self.comments.append(comment)

    def add_comments(self, comment: list[UBTComment]) -> None:
        self.comments.extend(comment)

    def to_json(self) -> None:
        comments = [comment.__dict__ for comment in self.comments]
        output_path = self.output_dir / self.filepath.with_suffix(".json").relative_to(
            self.src_dir
        )
        if not output_path.parent.exists():
            output_path.parent.mkdir(parents=True)
        with output_path.open("w") as f:
            json.dump(comments, f)


class UBTCache:
    def __init__(
        self,
        cache_path: str = "./ubt_cache.json",
        uncached_files: list[UBTSourceFile] | None = None,
    ):
        if uncached_files is None:
            uncached_files = []
        self.cache_path = Path(cache_path)
        self.uncached_files = uncached_files
        self.cached_files = self.load_cache()

    def load_cache(self) -> dict[str, float]:
        if not self.cache_path.exists():
            return {}
        with self.cache_path.open("r") as f:
            cached_files = cast(dict[str, float], json.load(f))
            return cached_files

    def add_uncached_files(self, uncached_files: list[UBTSourceFile]) -> None:
        self.uncached_files.extend(uncached_files)
        for uncached_file in uncached_files:
            if str(uncached_file.filepath) in self.cached_files:
                self.cached_files.pop(str(uncached_file.filepath))

    def update_cache(self) -> None:
        for src_file in self.uncached_files:
            if (
                str(src_file.filepath) in self.cached_files
                and src_file.changed_date == self.cached_files[str(src_file.filepath)]
            ):
                continue
            self.cached_files[str(src_file.filepath)] = src_file.changed_date
        # remove cached files from uncached_files
        self.uncached_files = []
        if not self.cache_path.parent.exists():
            self.cache_path.parent.mkdir(parents=True)
        with self.cache_path.open("w") as f:
            json.dump(self.cached_files, f)
