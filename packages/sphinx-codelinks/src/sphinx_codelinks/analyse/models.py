from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TypedDict

from tree_sitter import Node as TreeSitterNode


class MarkedContentType(str, Enum):
    need = "need"
    need_id_refs = "need-id-refs"
    rst = "rst"


class SourceComment:
    def __init__(self, node: TreeSitterNode) -> None:
        self.node: TreeSitterNode = node
        self.source_file: SourceFile | None = None


class SourceFile:
    def __init__(self, filepath: Path) -> None:
        self.filepath: Path = filepath
        self.src_comments: list[SourceComment] = []

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
class MarkedRst(Metadata):
    rst: str
    type: MarkedContentType = field(init=False, default=MarkedContentType.rst)
