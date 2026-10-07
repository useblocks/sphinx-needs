from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, TypedDict

from tree_sitter import Node as TreeSitterNode


class MarkedContentType(str, Enum):  # noqa: UP042  # StrEnum changes str(member), which reaches CLI warnings and error messages
    need = "need"
    need_id_refs = "need-id-refs"
    multiline_need = "multiline-need"


class WarningSubTypeEnum(str, Enum):  # noqa: UP042  # StrEnum changes str(member), which reaches CLI warnings and error messages
    """The kinds of the analyser's warnings, one-line and multi-line alike.

    The values are a contract: the shared extraction corpus snapshots them.
    """

    too_many_fields = "too_many_fields"
    too_few_fields = "too_few_fields"
    missing_square_brackets = "missing_square_brackets"
    not_start_or_end_with_square_brackets = "not_start_or_end_with_square_brackets"
    newline_in_field = "newline_in_field"
    multiline_need_header = "multiline_need_header"
    """The open word starts a line that does not match the open-line grammar."""
    multiline_need_unterminated = "multiline_need_unterminated"
    """The comment run ends before a close line."""
    multiline_need_markup = "multiline_need_markup"
    """The markup tag is not in the project's ``markups`` table."""
    multiline_need_oneline_form = "multiline_need_oneline_form"
    """The open and the close are on one line."""
    multiline_need_duplicate_option = "multiline_need_duplicate_option"
    """An option key is given twice, or names a key the record sets itself."""
    multiline_need_nested_open = "multiline_need_nested_open"
    """The open word starts a line of a block's body."""


class SourceComment:
    def __init__(self, node: TreeSitterNode) -> None:
        self.node: TreeSitterNode = node
        self.source_file: SourceFile | None = None


class SourceFile:
    def __init__(self, filepath: Path) -> None:
        self.filepath: Path = filepath
        self.src_comments: list[SourceComment] = []
        self.lines: list[str] | None = None
        """The file's text split into rows (LF-normalised), when an extractor needs the
        rows themselves: multi-line needs read what precedes a comment on its row."""

    def add_comment(self, comment: SourceComment) -> None:
        self.src_comments.append(comment)
        comment.source_file = self

    def add_comments(self, comments: list[SourceComment]) -> None:
        for comment in comments:
            self.add_comment(comment)


class Position(TypedDict):
    row: int
    column: int


class SourceMap(TypedDict):
    start: Position
    end: Position


@dataclass
class Metadata:
    filepath: Path
    remote_url: str | None
    source_map: SourceMap
    source_comment: SourceComment
    tagged_scope: TreeSitterNode | None
    type: MarkedContentType

    def to_dict(self) -> dict[str, str | int | list[str]]:
        obj = self.__dict__.copy()
        obj["filepath"] = str(self.filepath)
        obj["tagged_scope"] = (
            str(self.tagged_scope.text.decode("utf-8"))
            if self.tagged_scope and self.tagged_scope.text
            else None
        )
        obj["type"] = self.type.value
        del obj["source_comment"]
        return obj

    def add_src_comment(self, src_comment: SourceComment) -> None:
        self.source_comment = src_comment


@dataclass
class NeedIdRefs(Metadata):
    need_ids: list[str]
    marker: str
    type: MarkedContentType = field(init=False, default=MarkedContentType.need_id_refs)


@dataclass
class OneLineNeed(Metadata):
    need: dict[str, str | list[str]]
    type: MarkedContentType = field(init=False, default=MarkedContentType.need)


@dataclass
class MultilineNeed(Metadata):
    """One multi-line need: a need written across the lines of a comment run.

    Plain JSON data apart from the ``Metadata`` fields every record shares (the
    tree-sitter scope node and the comment are dropped or flattened by ``to_dict``).
    """

    need: dict[str, str]
    """``type``, ``title`` (may be ``""``), the option keys as written mapped to the
    directive strings, ``content`` and ``doctype``."""
    markup: str
    """The markup tag as resolved (the project default when the open line names none or
    an unknown one), for diagnostics."""
    source: dict[str, Any]
    """Where the need is: ``project``, root-relative POSIX ``path``, ``root``, ``commit``,
    ``start``/``end``/``content_start`` (1-based ``line``, 0-based ``col``),
    ``option_lines`` and ``scope``."""
    type: MarkedContentType = field(
        init=False, default=MarkedContentType.multiline_need
    )
