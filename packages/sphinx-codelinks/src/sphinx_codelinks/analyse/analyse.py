from collections.abc import Generator
from dataclasses import dataclass
import json
import logging
from pathlib import Path
from typing import Any, TypedDict

from tree_sitter import Node as TreeSitterNode

from sphinx_codelinks.analyse import utils
from sphinx_codelinks.analyse.models import (
    MarkedContentType,
    MarkedRst,
    NeedIdRefs,
    OneLineNeed,
    SourceComment,
    SourceFile,
    SourceMap,
)
from sphinx_codelinks.analyse.oneline_parser import (
    OnelineParserInvalidWarning,
    oneline_parser,
)
from sphinx_codelinks.config import (
    UNIX_NEWLINE,
    OneLineCommentStyle,
    SourceAnalyseConfig,
)

# initialize logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
# log to the console
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logger.addHandler(console)


class AnalyseWarningType(TypedDict):
    file_path: str
    lineno: int
    msg: str
    type: str
    sub_type: str


@dataclass
class AnalyseWarning:
    file_path: str
    lineno: int
    msg: str
    type: str
    sub_type: str


class SourceAnalyse:
    def __init__(
        self,
        analyse_config: SourceAnalyseConfig,
    ) -> None:
        self.analyse_config = analyse_config
        self.src_files: list[SourceFile] = []
        self.src_comments: list[SourceComment] = []
        self.need_id_refs: list[NeedIdRefs] = []
        self.oneline_needs: list[OneLineNeed] = []
        self.marked_rst: list[MarkedRst] = []
        self.all_marked_content: list[NeedIdRefs | OneLineNeed | MarkedRst] = []
        self.git_root: Path | None = utils.locate_git_root(self.analyse_config.src_dir)
        self.git_remote_url: str | None = (
            utils.get_remote_url(self.git_root) if self.git_root else None
        )
        self.git_commit_rev: str | None = (
            utils.get_current_rev(self.git_root) if self.git_root else None
        )
        self.project_path: Path = (
            self.git_root if self.git_root else self.analyse_config.src_dir
        )
        self.oneline_warnings: list[AnalyseWarning] = []

    def get_src_strings(self) -> Generator[tuple[Path, bytes], Any, None]:  # type: ignore[explicit-any]
        """Load source files and extract their content."""
        for src_path in self.analyse_config.src_files:
            if not utils.is_text_file(src_path):
                continue
            with src_path.open("r", encoding="utf-8", newline="") as f:
                # Normalize all line endings to Unix LF
                text = f.read()
            text = text.replace("\r\n", "\n").replace("\r", "\n")
            yield src_path, text.encode("utf-8")

    def create_src_objects(self) -> None:
        parser, query = utils.init_tree_sitter(self.analyse_config.comment_type)

        for src_path, src_string in self.get_src_strings():
            comments: list[TreeSitterNode] | None = utils.extract_comments(
                src_string, parser, query
            )
            if not comments:
                continue
            src_comments: list[SourceComment] = [
                SourceComment(node) for node in comments
            ]

            src_file = SourceFile(src_path.absolute())
            src_file.add_comments(src_comments)
            self.src_files.append(src_file)
            self.src_comments.extend(src_comments)

        logger.info(f"Source files loaded: {len(self.src_files)}")
        logger.info(f"Source comments extracted: {len(self.src_comments)}")

    def extract_marker(
        self,
        text: str,
    ) -> Generator[tuple[str, list[str], int, int, int], None, None]:
        lines = text.splitlines()
        row_offset = 0
        for line in lines:
            for marker in self.analyse_config.need_id_refs_config.markers:
                marker_idx = line.find(marker)
                if marker_idx == -1:
                    continue
                markered_text = line[marker_idx + len(marker) :].strip()
                need_ids = markered_text.replace(",", " ").split()
                start_column = marker_idx + len(marker)
                end_column = start_column + len(markered_text)
                yield marker, need_ids, row_offset, start_column, end_column
            row_offset += 1

    def extract_anchors(
        self,
        text: str,
        filepath: Path,
        tagged_scope: TreeSitterNode | None,
        src_comment: SourceComment,
    ) -> list[NeedIdRefs]:
        """Extract need-ids-refs from a comment."""
        anchors: list[NeedIdRefs] = []
        for (
            marker,
            need_ids,
            row_offset,
            start_column,
            end_column,
        ) in self.extract_marker(text):
            lineno = src_comment.node.start_point.row + row_offset + 1
            remote_url = self.git_remote_url
            if self.git_remote_url and self.git_commit_rev:
                remote_url = utils.form_https_url(
                    self.git_remote_url,
                    self.git_commit_rev,
                    self.project_path,
                    filepath,
                    lineno,
                )
            source_map: SourceMap = {
                "start": {
                    "row": lineno - 1,
                    "column": start_column,
                },
                "end": {
                    "row": lineno - 1,
                    "column": end_column,
                },
            }
            anchors.append(
                NeedIdRefs(
                    filepath,
                    remote_url,
                    source_map,
                    src_comment,
                    tagged_scope,
                    need_ids,
                    marker,
                )
            )
        return anchors

    def extract_oneline_need(
        self,
        text: str,
        src_comment: SourceComment,
        oneline_comment_style: OneLineCommentStyle,
    ) -> Generator[tuple[dict[str, str | list[str] | int], int]]:
        lines = text.splitlines(keepends=True)
        row_offset = 0
        if len(lines) == 1:
            # single line comment has no newline char in the extracted comment
            lines[0] = f"{lines[0]}{UNIX_NEWLINE}"

        for line in lines:
            resolved = oneline_parser(line, oneline_comment_style)
            if not resolved:
                row_offset += 1
                continue
            if isinstance(resolved, OnelineParserInvalidWarning):
                if not src_comment.source_file:
                    row_offset += 1
                    continue
                self.oneline_warnings.append(
                    AnalyseWarning(
                        str(src_comment.source_file.filepath),
                        src_comment.node.start_point.row + row_offset + 1,
                        resolved.msg,
                        MarkedContentType.need,
                        resolved.sub_type.value,
                    )
                )
                row_offset += 1
                continue
            yield resolved, row_offset
            row_offset += 1

    def extract_oneline_needs(
        self,
        text: str,
        filepath: Path,
        tagged_scope: TreeSitterNode | None,
        src_comment: SourceComment,
        oneline_comment_style: OneLineCommentStyle,
    ) -> list[OneLineNeed]:
        row_offset = 0
        oneline_needs = []
        for resolved, row_offset in self.extract_oneline_need(
            text, src_comment, oneline_comment_style
        ):
            lineno = src_comment.node.start_point.row + row_offset + 1
            remote_url = self.git_remote_url
            if self.git_remote_url and self.git_commit_rev:
                remote_url = utils.form_https_url(
                    self.git_remote_url,
                    self.git_commit_rev,
                    self.project_path,
                    filepath,
                    lineno,
                )
            source_map: SourceMap = {
                "start": {
                    "row": lineno - 1,
                    "column": resolved["start_column"],  # type: ignore[typeddict-item]  # dynamic keys
                },
                "end": {
                    "row": lineno - 1,
                    "column": resolved["end_column"],  # type: ignore[typeddict-item]  # dynamic keys
                },
            }
            del resolved["start_column"]
            del resolved["end_column"]
            oneline_needs.append(
                OneLineNeed(
                    filepath,
                    remote_url,
                    source_map,
                    src_comment,
                    tagged_scope,
                    resolved,  # type: ignore[arg-type] # int arguments were deleted
                )
            )
        return oneline_needs

    def extract_marked_rst(
        self,
        text: str,
        filepath: Path,
        tagged_scope: TreeSitterNode | None,
        src_comment: SourceComment,
    ) -> MarkedRst | None:
        """Extract marked rst from a comment.

        Presumably, only one marked rst text in a comment.
        """
        extracted_rst = utils.extract_rst(
            text,
            self.analyse_config.marked_rst_config.start_sequence,
            self.analyse_config.marked_rst_config.end_sequence,
        )
        if not extracted_rst:
            return None
        if UNIX_NEWLINE in extracted_rst["rst_text"]:
            rst_text = utils.remove_leading_sequences(extracted_rst["rst_text"], ["*"])
        else:
            rst_text = extracted_rst["rst_text"]
        lineno = src_comment.node.start_point.row + extracted_rst["row_offset"] + 1
        remote_url = self.git_remote_url
        if self.git_remote_url and self.git_commit_rev:
            remote_url = utils.form_https_url(
                self.git_remote_url,
                self.git_commit_rev,
                self.project_path,
                filepath,
                lineno,
            )
        source_map: SourceMap = {
            "start": {
                "row": lineno - 1,
                "column": extracted_rst["start_idx"],
            },
            "end": {
                "row": lineno - 1,
                "column": extracted_rst["end_idx"],
            },
        }
        return MarkedRst(
            filepath,
            remote_url,
            source_map,
            src_comment,
            tagged_scope,
            rst_text,
        )

    def extract_marked_content(self) -> None:
        for src_comment in self.src_comments:
            text = (
                src_comment.node.text.decode("utf-8") if src_comment.node.text else None
            )
            if not text:
                continue
            filepath = (
                src_comment.source_file.filepath if src_comment.source_file else None
            )
            if not filepath:
                continue
            tagged_scope: TreeSitterNode | None = utils.find_associated_scope(
                src_comment.node, self.analyse_config.comment_type
            )
            if self.analyse_config.get_need_id_refs:
                anchors = self.extract_anchors(
                    text, filepath, tagged_scope, src_comment
                )
                self.need_id_refs.extend(anchors)

            if self.analyse_config.get_oneline_needs:
                oneline_needs = self.extract_oneline_needs(
                    text,
                    filepath,
                    tagged_scope,
                    src_comment,
                    self.analyse_config.oneline_comment_style,
                )
                self.oneline_needs.extend(oneline_needs)
            if self.analyse_config.get_rst:
                marked_rst = self.extract_marked_rst(
                    text, filepath, tagged_scope, src_comment
                )
                if marked_rst:
                    self.marked_rst.append(marked_rst)

        if self.analyse_config.get_need_id_refs:
            logger.info(f"Need-id-refs extracted: {len(self.need_id_refs)}")
        if self.analyse_config.get_oneline_needs:
            logger.info(f"Oneline needs extracted: {len(self.oneline_needs)}")
        if self.analyse_config.get_rst:
            logger.info(f"Marked rst extracted: {len(self.marked_rst)}")

    def merge_marked_content(self) -> None:
        self.all_marked_content.extend(self.need_id_refs)
        self.oneline_needs.sort(key=lambda x: x.source_map["start"]["row"])
        self.all_marked_content.extend(self.oneline_needs)
        self.all_marked_content.extend(self.marked_rst)
        self.all_marked_content.sort(
            key=lambda x: (x.filepath, x.source_map["start"]["row"])
        )

    def dump_marked_content(self, outdir: Path) -> None:
        output_path = outdir / "marked_content.json"
        if not output_path.parent.exists():
            output_path.parent.mkdir(parents=True)
        to_dump = [
            marked_content.to_dict() for marked_content in self.all_marked_content
        ]
        with output_path.open("w") as f:
            json.dump(to_dump, f)
        logger.info(f"Marked content dumped to {output_path}")

    def run(self) -> None:
        self.create_src_objects()
        self.extract_marked_content()
        self.merge_marked_content()
