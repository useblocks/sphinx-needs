from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, TypedDict

from tree_sitter import Node as TreeSitterNode

from sphinx_codelinks.analyse.entity import CodeScope, CppNames


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
    docstring_tag = "docstring_tag"
    """A Python docstring line holding a field-shaped tag, ``@param a: text``."""
    jsdoc_tag = "jsdoc_tag"
    """A line of a TypeScript or JavaScript JSDoc comment starting with a JSDoc tag."""
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
    def __init__(self, node: TreeSitterNode, column: int = 0) -> None:
        self.node: TreeSitterNode = node
        # The column, in characters, at which the comment's text starts on its
        # first line. A marker on that line is reported at this column plus its
        # offset into the text; a later line of the text starts at column 0.
        self.column: int = column
        self.source_file: SourceFile | None = None

    @property
    def text(self) -> bytes:
        """The comment's text as the file writes it (``SourceFile.node_text``): every
        reader of a comment reads it here, never ``node.text``, which in a C++ tree
        parsed from a prepared copy is the copy's."""
        if self.source_file is None:
            return self.node.text or b""
        return self.source_file.node_text(self.node)


class SourceFile:
    def __init__(self, filepath: Path) -> None:
        self.filepath: Path = filepath
        self.src_comments: list[SourceComment] = []
        self.lines: list[str] | None = None
        """The file's text split into rows (LF-normalised), when an extractor needs the
        rows themselves: multi-line needs read what precedes a comment on its row."""
        self.cpp_names: CppNames | None = None
        """What the whole C++ file decides about the names of its entities, for a C++
        file the analysis parsed (``utils.parse_source``)."""

    def node_text(self, node: TreeSitterNode) -> bytes:
        """The text of ``node`` as the file writes it.

        A C++ tree may be parsed from a prepared copy of the file
        (:mod:`sphinx_codelinks.analyse.cpp_macros`), whose ``node.text`` is the copy's:
        the file as written is read instead.
        """
        if self.cpp_names is not None:
            return self.cpp_names.source[node.start_byte : node.end_byte]
        return node.text or b""

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
    scope: CodeScope | None = field(default=None, kw_only=True)
    """The entity the marker is attached to (``tagged_scope``, named), if any.

    Keyword-only, so that its default does not precede the subclasses' own fields.
    A one-line need and a reference write it as ``scope``, right after
    ``tagged_scope``; a multi-line need carries it in ``source.scope`` instead."""

    def to_dict(self) -> dict[str, Any]:
        obj: dict[str, Any] = {}
        for key, value in self.__dict__.items():
            if key in ("source_comment", "scope"):
                continue
            obj[key] = value
            if key == "tagged_scope":
                written = self.tagged_scope_text()
                obj[key] = written.decode("utf-8") if written else None
                if self.type != MarkedContentType.multiline_need:
                    obj["scope"] = self.scope
        obj["filepath"] = str(self.filepath)
        obj["type"] = self.type.value
        return obj

    def tagged_scope_text(self) -> bytes | None:
        """The text of ``tagged_scope`` as the file writes it (``SourceFile.node_text``),
        ``None`` without one."""
        if self.tagged_scope is None:
            return None
        source_file = self.source_comment.source_file if self.source_comment else None
        if source_file is None:
            return self.tagged_scope.text
        return source_file.node_text(self.tagged_scope)

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
