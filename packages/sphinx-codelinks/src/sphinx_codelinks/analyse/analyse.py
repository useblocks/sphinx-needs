from collections.abc import Generator
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, TypedDict, cast

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
from sphinx_codelinks.logger import get_logger
from sphinx_codelinks.source_discover.config import CommentType

logger = get_logger(__name__)


def _count(n: int, noun: str) -> str:
    """Format ``n noun`` with a naive (append-s) plural for progress summaries."""
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


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
        *,
        name: str = "",
    ) -> None:
        self.name = name
        self.analyse_config = analyse_config
        self.src_files: list[SourceFile] = []
        self.src_comments: list[SourceComment] = []
        self.need_id_refs: list[NeedIdRefs] = []
        self.oneline_needs: list[OneLineNeed] = []
        self.marked_rst: list[MarkedRst] = []
        self.all_marked_content: list[NeedIdRefs | OneLineNeed | MarkedRst] = []
        # Use explicitly configured git_root if provided, otherwise auto-detect
        if self.analyse_config.git_root is not None:
            self.git_root: Path | None = self.analyse_config.git_root.resolve()
        else:
            self.git_root = utils.locate_git_root(self.analyse_config.src_dir)
        self.git_remote_url: str | None = (
            utils.get_remote_url(self.git_root) if self.git_root else None
        )
        self.git_commit_rev: str | None = (
            utils.get_current_rev(self.git_root) if self.git_root else None
        )
        self.project_path: Path = self.git_root or self.analyse_config.src_dir
        self.oneline_warnings: list[AnalyseWarning] = []
        # Per-run memo of parsed compile_commands.json, keyed by DB path, so the
        # database is read once per run instead of once per source file.
        self._flags_map_cache: dict[Path, dict[Path, list[str]] | None] = {}

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

    def _flags_map_for(self, db_path: Path) -> dict[Path, list[str]] | None:
        """Return the parsed compile_commands.json for ``db_path``, memoized.

        The database is read and parsed once per run instead of once per source
        file (O(files x entries) -> O(entries)). A present-but-malformed or
        unreadable database is warned once and cached as ``None`` so callers fall
        back to the configured defines without re-reading or re-warning per file.
        """
        from sphinx_codelinks.analyse.preproc import compile_db  # noqa: PLC0415

        if db_path in self._flags_map_cache:
            return self._flags_map_cache[db_path]
        try:
            flags = compile_db.load_flags_map(db_path)
        except (OSError, ValueError, TypeError) as exc:
            logger.warning(
                f"codelinks: failed to read {db_path} ({exc}); "
                f"falling back to the configured defines"
            )
            self._flags_map_cache[db_path] = None
            return None
        self._flags_map_cache[db_path] = flags
        return flags

    def _resolve_preproc_args(self, src_path: Path) -> list[str] | None:
        from sphinx_codelinks.analyse.preproc import compile_db  # noqa: PLC0415

        # `run()` calls this (via create_src_objects_libclang) only when
        # `preprocessor is not None`, but keep the guard: it narrows the type for
        # the checker and is a cheap defense (an `assert` would trip bandit S101).
        preproc = self.analyse_config.preprocessor
        if preproc is None:
            return []
        db_path = preproc.compile_commands
        if db_path is None:
            db_path = compile_db.find_compile_db(src_path, self.project_path)
        if db_path is not None and db_path.is_file():
            flags = self._flags_map_for(db_path)
            if flags is None:
                # Present-but-malformed/unreadable DB (warned once in the helper):
                # fall back to the configured defines so extraction still runs.
                return compile_db.defines_to_args(
                    preproc.defines, preproc.includes, preproc.std
                )
            args = flags.get(src_path.absolute().resolve())
            if args is not None:
                return args
            # Absent from the DB. compile_commands.json lists only compiled
            # translation units, never headers — so a header here is parsed
            # standalone with the global defines (one run = one variant). A
            # compiled source absent from the build is skipped (spec §3.3).
            if compile_db.is_translation_unit_source(src_path):
                return None
            return compile_db.defines_to_args(
                preproc.defines, preproc.includes, preproc.std
            )
        # No readable DB. `find_compile_db` only ever returns a real file, so a
        # non-None `db_path` that reaches here is an explicit `compile_commands`
        # path that is not a readable file (typo/missing): warn and fall back
        # rather than skip silently. A genuinely absent DB (db_path is None) just
        # falls back to the manual defines applied globally.
        if db_path is not None:
            logger.warning(
                f"codelinks: compile_commands path {db_path} is not a readable "
                f"file; falling back to the configured defines"
            )
        return compile_db.defines_to_args(
            preproc.defines, preproc.includes, preproc.std
        )

    # @Extract traceability objects with the preprocessor-aware libclang engine, IMPL_PREPROC_1, impl, [FE_PREPROC]
    def create_src_objects_libclang(self) -> None:
        from sphinx_codelinks.analyse.preproc import (  # noqa: PLC0415
            libclang_parser,
            loader,
        )

        # Resolve the exception via the loader (never a direct ``import
        # clang.cindex``) so a missing ``libclang`` extra still surfaces the
        # loader's friendly install hint rather than a bare ImportError.
        translation_unit_load_error = (
            loader.load_clang_cindex().TranslationUnitLoadError
        )

        for src_path in self.analyse_config.src_files:
            if not utils.is_text_file(src_path):
                continue
            args = self._resolve_preproc_args(src_path)
            if args is None:
                logger.debug(
                    f"codelinks: skipping {src_path} — not found in compile_commands.json"
                )
                continue
            try:
                comments = libclang_parser.extract_active_comments(src_path, args)
            except translation_unit_load_error:
                # Last-resort guard. Standalone parses pin ``-x`` to match the
                # ``-std`` (see defines_to_args), so the common case — a ``.h``/
                # ``.c`` header handed a C++ ``-std`` — now parses as C++ and its
                # markers extract. This only fires if libclang still cannot load
                # the file as a translation unit at all; skip it rather than
                # aborting the whole run. Surfaced as a ``warning`` so the silent
                # data-loss (a file's markers dropped) is visible — accepting that
                # this fails ``sphinx-build -W``.
                logger.warning(
                    f"codelinks: skipping {src_path} — libclang could not load it "
                    f"as a translation unit"
                )
                continue
            if not comments:
                continue
            # ``c`` is a LibclangComment duck-typing the tree-sitter Node
            # interface SourceComment reads (``.text`` / ``.start_point.row``);
            # the Node-only path (find_associated_scope) is guarded by
            # ``is_libclang`` so it never runs on these.
            src_comments = [SourceComment(cast("TreeSitterNode", c)) for c in comments]
            src_file = SourceFile(src_path.absolute())
            src_file.add_comments(src_comments)
            self.src_files.append(src_file)
            self.src_comments.extend(src_comments)

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

    # @Extract need ID references from code comments, IMPL_LNK_1, impl, [FE_LNK]
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
                lineno = src_comment.node.start_point.row + row_offset + 1
                warning = AnalyseWarning(
                    str(src_comment.source_file.filepath),
                    lineno,
                    resolved.msg,
                    MarkedContentType.need,
                    resolved.sub_type.value,
                )
                self.oneline_warnings.append(warning)
                row_offset += 1
                continue
            yield resolved, row_offset
            row_offset += 1

    # @Extract one-line traceability needs from comments, IMPL_ONE_1, impl, [FE_DEF, FE_CMT]
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

    # @Extract marked reStructuredText blocks from comments, IMPL_MRST_1, impl, [FE_RST_EXTRACTION]
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
            if getattr(src_comment.node, "is_libclang", False):
                tagged_scope: TreeSitterNode | None = None
            else:
                tagged_scope = utils.find_associated_scope(
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

    def run(self) -> None:
        if (
            self.analyse_config.preprocessor is not None
            and self.analyse_config.comment_type == CommentType.cpp
        ):
            self.create_src_objects_libclang()
        else:
            self.create_src_objects()
        self.extract_marked_content()
        self.merge_marked_content()
        self._log_summary()

    def _log_summary(self) -> None:
        """Emit a per-project marker (default-visible) plus a -v breakdown."""
        label = f"codelinks [{self.name}]" if self.name else "codelinks"
        logger.info(
            f"{label}: {_count(len(self.src_files), 'file')}, "
            f"{_count(len(self.all_marked_content), 'marker')}"
        )
        logger.debug(
            f"{label}: {_count(len(self.src_comments), 'comment')}, "
            f"{_count(len(self.oneline_needs), 'oneline need')}, "
            f"{_count(len(self.need_id_refs), 'id-ref')}, "
            f"{_count(len(self.marked_rst), 'marked-rst block')}"
        )
