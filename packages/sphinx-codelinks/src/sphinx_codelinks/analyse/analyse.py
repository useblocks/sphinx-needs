import json
import os
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from tree_sitter import Node as TreeSitterNode
from tree_sitter import Parser, Query

from sphinx_codelinks.analyse import multiline_parser, utils
from sphinx_codelinks.analyse.models import (
    MarkedContentType,
    MultilineNeed,
    NeedIdRefs,
    OneLineNeed,
    SourceComment,
    SourceFile,
    SourceMap,
    WarningSubTypeEnum,
)
from sphinx_codelinks.analyse.oneline_parser import (
    OnelineParserInvalidWarning,
    docstring_tag,
    oneline_parser,
)
from sphinx_codelinks.analyse.references import _relative_posix
from sphinx_codelinks.config import (
    UNIX_NEWLINE,
    CommentCategory,
    OneLineCommentStyle,
    SourceAnalyseConfig,
)
from sphinx_codelinks.logger import get_logger
from sphinx_codelinks.source_discover.config import CommentType

logger = get_logger(__name__)

# The last key of the marked content's sort. Two entries can start at one position
# only with overlapping markers (a need-id marker that ends with the one-line start
# sequence), which the configuration check does not refuse. Such a tie is listed
# references, then one-line needs, then multi-line needs: an explicit rank, because
# the type names sort the other way round. Two references from one comment tie on
# every key and keep the marker order of the configuration (the sort is stable).
_KIND_RANK: dict[MarkedContentType, int] = {
    MarkedContentType.need_id_refs: 0,
    MarkedContentType.need: 1,
    MarkedContentType.multiline_need: 2,
}


def _char_column(src: bytes, byte_offset: int) -> int:
    """The column, in characters, of ``byte_offset`` in the UTF-8 ``src``."""
    line_start = src.rfind(b"\n", 0, byte_offset) + 1
    return len(src[line_start:byte_offset].decode("utf-8", errors="replace"))


def _count(n: int, noun: str) -> str:
    """Format ``n noun`` with a naive (append-s) plural for progress summaries."""
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def _row_count(src_comment: SourceComment) -> int:
    """The rows a comment covers: a Rust ``///`` node's text ends with its newline, which
    starts no row of its own."""
    return (src_comment.node.text or b"").rstrip(b"\n").count(b"\n") + 1


def _docstring_contents(
    node: TreeSitterNode, column: int
) -> list[tuple[str, int, int]]:
    """The content of each string of a docstring statement, between its quotes.

    Each with its 0-based row and its column, in characters: the quotes' column plus
    the prefix letters' and the delimiter's length. ``column`` is the statement's.
    """
    raw = node.text or b""
    contents = []
    for string in node.named_children:
        if string.type != "string":
            continue
        kinds = {child.type: child for child in string.children}
        start, end = kinds.get("string_start"), kinds.get("string_end")
        if start is None or end is None:
            continue
        begin = start.end_byte - node.start_byte
        before = raw[:begin]
        row_start = before.rfind(b"\n") + 1
        content_column = len(before[row_start:].decode("utf-8", errors="replace"))
        if row_start == 0:
            content_column += column
        contents.append(
            (
                raw[begin : end.start_byte - node.start_byte].decode(
                    "utf-8", errors="replace"
                ),
                start.end_point.row,
                content_column,
            )
        )
    return contents


def _scanned_texts(
    src_comment: SourceComment, claimed_rows: set[int] | None
) -> list[tuple[str, int, int]]:
    """What the one-line and reference extractors scan of a comment.

    Each text comes with the 0-based row and the column, in characters, at which it
    starts. A docstring is scanned as its content, without the quotes; a block
    comment without its closing ``*/``, and a legacy ``<!-- … -->`` comment without
    its ``-->``, which are not marker text. The rows a multi-line need claims are
    blanked.
    """
    node = src_comment.node
    if getattr(node, "type", None) == CommentCategory.docstring:
        texts = _docstring_contents(node, src_comment.column)
    else:
        text = node.text.decode("utf-8") if node.text else ""
        if text.startswith("/*") and text.endswith("*/"):
            text = text[:-2]
        elif text.startswith("<!--") and text.endswith("-->"):
            text = text[:-3]
        texts = [(text, node.start_point.row, src_comment.column)]
    if claimed_rows:
        # a block's lines are its own: no one-line need and no reference in them
        texts = [
            (multiline_parser.blank_rows(text, row, claimed_rows), row, column)
            for text, row, column in texts
        ]
    return texts


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
        self.multiline_needs: list[MultilineNeed] = []
        self.all_marked_content: list[NeedIdRefs | OneLineNeed | MultilineNeed] = []
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
        self.warnings: list[AnalyseWarning] = []
        """The analysis' warnings, one-line and multi-line alike, in extraction order."""
        # Per-run memo of parsed compile_commands.json, keyed by DB path, so the
        # database is read once per run instead of once per source file.
        self._flags_map_cache: dict[Path, dict[Path, list[str]] | None] = {}

    @property
    def oneline_warnings(self) -> list[AnalyseWarning]:
        """The old name of :attr:`warnings`, kept for one release; read-only."""
        return self.warnings

    def get_src_strings(self) -> Generator[tuple[Path, bytes], Any, None]:
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
        comment_type = self.analyse_config.comment_type
        # One (parser, query) pair per distinct grammar actually needed, built
        # lazily so a parser is never rebuilt per file. Every comment type
        # except TypeScript uses a single grammar for the whole run;
        # TypeScript alone varies its grammar per file (utils.ts_grammar_key)
        # because a legacy TypeScript-only cast parses as JSX under the wrong
        # grammar — see the CommentType.ts branch of utils.init_tree_sitter.
        parser_cache: dict[str, tuple[Parser, Query]] = {}

        for src_path, src_string in self.get_src_strings():
            # `comment_type` is normally a CommentType member, but a few call
            # sites carry it as a plain (possibly invalid) str instead — see
            # SourceAnalyseConfig.comment_type — so key on `str(comment_type)`
            # rather than `.value`, which only the enum has.
            cache_key = (
                utils.ts_grammar_key(src_path)
                if comment_type == CommentType.ts
                else str(comment_type)
            )
            if cache_key not in parser_cache:
                parser_cache[cache_key] = utils.init_tree_sitter(comment_type, src_path)
            parser, query = parser_cache[cache_key]

            comments: list[TreeSitterNode] | None = utils.extract_comments(
                src_string, parser, query
            )
            if not comments:
                continue
            src_comments: list[SourceComment] = [
                SourceComment(node, _char_column(src_string, node.start_byte))
                for node in comments
            ]

            src_file = SourceFile(src_path.absolute())
            src_file.add_comments(src_comments)
            if self.analyse_config.get_multiline_needs:
                src_file.lines = src_string.decode("utf-8").split(UNIX_NEWLINE)
            self.src_files.append(src_file)
            self.src_comments.extend(src_comments)

    def _flags_map_for(self, db_path: Path) -> dict[Path, list[str]] | None:
        """Return the parsed compile_commands.json for ``db_path``, memoized.

        The database is read and parsed once per run instead of once per source
        file (O(files x entries) -> O(entries)). A present-but-malformed or
        unreadable database is warned once and cached as ``None`` so callers fall
        back to the configured defines without re-reading or re-warning per file.
        """
        from sphinx_codelinks.analyse.preproc import compile_db

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
        from sphinx_codelinks.analyse.preproc import compile_db

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
        from sphinx_codelinks.analyse.preproc import (
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
            src_comments = [
                SourceComment(cast("TreeSitterNode", c), c.column) for c in comments
            ]
            src_file = SourceFile(src_path.absolute())
            src_file.add_comments(src_comments)
            if self.analyse_config.get_multiline_needs:
                # multi-line needs read what precedes a comment on its row from
                # the row itself
                text = src_path.read_text(encoding="utf-8", errors="replace")
                text = text.replace("\r\n", "\n").replace("\r", "\n")
                src_file.lines = text.split(UNIX_NEWLINE)
            self.src_files.append(src_file)
            self.src_comments.extend(src_comments)

    def extract_marker(
        self,
        text: str,
    ) -> Generator[tuple[str, list[str], int, int, int], None, None]:
        row_offset = 0
        for line in text.split(UNIX_NEWLINE):
            for marker in self.analyse_config.need_id_refs_config.markers:
                marker_idx = line.find(marker)
                if marker_idx == -1:
                    continue
                after_marker = line[marker_idx + len(marker) :]
                markered_text = after_marker.strip()
                if markered_text.endswith("*/"):
                    # The end of a one-line block comment, not an id.
                    markered_text = markered_text[:-2].rstrip()
                need_ids = markered_text.replace(",", " ").split()
                if not need_ids:
                    continue
                start_column = (
                    marker_idx
                    + len(marker)
                    + len(after_marker)
                    - len(after_marker.lstrip())
                )
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
        first_row: int | None = None,
        first_column: int | None = None,
    ) -> list[NeedIdRefs]:
        """Extract need-ids-refs from a comment.

        ``text`` starts at ``first_row`` and ``first_column`` (by default the
        comment's own row and column).
        """
        if first_row is None:
            first_row = src_comment.node.start_point.row
        if first_column is None:
            first_column = src_comment.column
        anchors: list[NeedIdRefs] = []
        for (
            marker,
            need_ids,
            row_offset,
            start_column,
            end_column,
        ) in self.extract_marker(text):
            lineno = first_row + row_offset + 1
            line_column = first_column if row_offset == 0 else 0
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
                    "column": line_column + start_column,
                },
                "end": {
                    "row": lineno - 1,
                    "column": line_column + end_column,
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

    def _is_need_id_refs_line(self, line: str) -> bool:
        """Whether a comment line is an ``@need-ids:`` reference rather than a need.

        A line whose text, after comment decoration and whitespace, starts with a
        configured need-id-refs marker is a reference, and never a one-line need --
        ubCode's precedence. Without it the default one-line start sequence ``@`` also
        matched ``// @need-ids: A, B`` and made a need titled ``need-ids: A`` with the id
        ``B``. A line with anything alphanumeric before the marker is not a reference
        line here (``// see @need-ids: X`` -- the one-line parser ignores it anyway, and
        the references on it are still extracted), and a line holding a one-line need
        before the marker (``[[…]] @need-ids: X``) keeps its need: only a line that
        STARTS with the marker is withheld from the one-line parser.
        """
        for marker in self.analyse_config.need_id_refs_config.markers:
            marker_idx = line.find(marker)
            if marker_idx != -1 and not any(
                char.isalnum() for char in line[:marker_idx]
            ):
                return True
        return False

    def extract_oneline_need(
        self,
        text: str,
        src_comment: SourceComment,
        oneline_comment_style: OneLineCommentStyle,
        first_row: int | None = None,
    ) -> Generator[tuple[dict[str, str | list[str] | int], int]]:
        if first_row is None:
            first_row = src_comment.node.start_point.row
        # every line counts as terminated, the last one too
        lines = [f"{line}{UNIX_NEWLINE}" for line in text.split(UNIX_NEWLINE)]
        row_offset = 0

        # Only a Python docstring can hold docstring tags; a ``#`` comment never does.
        in_docstring = (
            getattr(src_comment.node, "type", None) == CommentCategory.docstring
        )
        for line in lines:
            if self._is_need_id_refs_line(line):
                row_offset += 1
                continue
            tag = (
                docstring_tag(line, oneline_comment_style.start_sequence)
                if in_docstring
                else None
            )
            if tag is not None:
                if src_comment.source_file:
                    self.warnings.append(
                        AnalyseWarning(
                            str(src_comment.source_file.filepath),
                            first_row + row_offset + 1,
                            f"'{oneline_comment_style.start_sequence}{tag}' is a docstring "
                            "tag, not a one-line need; use a start sequence that "
                            "docstrings do not contain",
                            MarkedContentType.need,
                            WarningSubTypeEnum.docstring_tag.value,
                        )
                    )
                row_offset += 1
                continue
            resolved = oneline_parser(line, oneline_comment_style)
            if not resolved:
                row_offset += 1
                continue
            if isinstance(resolved, OnelineParserInvalidWarning):
                if not src_comment.source_file:
                    row_offset += 1
                    continue
                lineno = first_row + row_offset + 1
                warning = AnalyseWarning(
                    str(src_comment.source_file.filepath),
                    lineno,
                    resolved.msg,
                    MarkedContentType.need,
                    resolved.sub_type.value,
                )
                self.warnings.append(warning)
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
        first_row: int | None = None,
        first_column: int | None = None,
    ) -> list[OneLineNeed]:
        """Extract the one-line needs of a comment.

        ``text`` starts at ``first_row`` and ``first_column`` (by default the
        comment's own row and column).
        """
        if first_row is None:
            first_row = src_comment.node.start_point.row
        if first_column is None:
            first_column = src_comment.column
        row_offset = 0
        oneline_needs = []
        for resolved, row_offset in self.extract_oneline_need(
            text, src_comment, oneline_comment_style, first_row
        ):
            lineno = first_row + row_offset + 1
            line_column = first_column if row_offset == 0 else 0
            start_column = line_column + cast("int", resolved["start_column"])
            end_column = line_column + cast("int", resolved["end_column"])
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
            del resolved["start_column"]
            del resolved["end_column"]
            oneline_needs.append(
                OneLineNeed(
                    filepath,
                    remote_url,
                    source_map,
                    src_comment,
                    tagged_scope,
                    resolved,  # int arguments were deleted  # ty: ignore[invalid-argument-type]
                )
            )
        return oneline_needs

    # @Extract multi-line needs from comment runs, IMPL_MLN_1, impl, [FE_MULTILINE_NEEDS]
    def extract_multiline_needs(self) -> dict[int, set[int]]:
        """Extract the multi-line needs of every file, and the rows their blocks claim.

        Runs before the other extractors: the rows a block claims (and those of a
        refused header, consumed to its close) are hidden from them.

        :return: For each comment holding claimed rows (keyed by ``id()`` of its
            :class:`SourceComment`), those 0-based rows.
        """
        claimed: dict[int, set[int]] = {}
        config = self.analyse_config.multiline_needs_config
        for src_file in self.src_files:
            for run in multiline_parser.form_runs(
                src_file.src_comments, src_file.lines
            ):
                result = multiline_parser.parse_run(
                    run.lines,
                    config,
                    leaderless_block=run.leaderless_block,
                    mixed_leaders=run.mixed_leaders,
                )
                for issue in result.issues:
                    self.warnings.append(
                        AnalyseWarning(
                            str(src_file.filepath),
                            issue.row + 1,
                            issue.msg,
                            MarkedContentType.multiline_need,
                            issue.kind.value,
                        )
                    )
                for block in result.blocks:
                    self.multiline_needs.append(
                        self._multiline_need(block, run, src_file.filepath)
                    )
                if not result.claimed_rows:
                    continue
                for src_comment in run.comments:
                    first = src_comment.node.start_point.row
                    rows = result.claimed_rows.intersection(
                        range(first, first + _row_count(src_comment))
                    )
                    if rows:
                        claimed.setdefault(id(src_comment), set()).update(rows)
        return claimed

    def _multiline_need(
        self,
        block: multiline_parser.ParsedBlock,
        run: multiline_parser.CommentRun,
        filepath: Path,
    ) -> MultilineNeed:
        """The record of one parsed block (see :class:`MultilineNeed`)."""
        src_comment = next(
            (
                comment
                for comment in run.comments
                if comment.node.start_point.row
                <= block.open_row
                < comment.node.start_point.row + _row_count(comment)
            ),
            run.comments[0],
        )
        tagged_scope: TreeSitterNode | None = None
        if not getattr(src_comment.node, "is_libclang", False):
            tagged_scope = utils.find_associated_scope(
                src_comment.node, self.analyse_config.comment_type
            )
        lineno = block.open_row + 1
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
            "start": {"row": block.open_row, "column": block.open_col},
            "end": {"row": block.close_row, "column": block.end_col},
        }
        content_start = (
            {"line": block.content_start[0] + 1, "col": block.content_start[1]}
            if block.content_start is not None
            else None
        )
        scope = (
            {
                "kind": tagged_scope.type,
                "start": tagged_scope.start_point.row + 1,
                "end": tagged_scope.end_point.row + 1,
            }
            if tagged_scope is not None
            else None
        )
        source: dict[str, Any] = {
            "project": self.name,
            "path": _relative_posix(filepath, self.project_path),
            "root": "git" if self.git_root is not None else "src_dir",
            "commit": self.git_commit_rev,
            "start": {"line": lineno, "col": block.open_col},
            "end": {"line": block.close_row + 1, "col": block.end_col},
            "content_start": content_start,
            "option_lines": dict(block.option_rows),
            "scope": scope,
        }
        return MultilineNeed(
            filepath,
            remote_url,
            source_map,
            src_comment,
            tagged_scope,
            block.need,
            block.markup,
            source,
        )

    def extract_marked_content(self) -> None:
        claimed: dict[int, set[int]] = {}
        if self.analyse_config.get_multiline_needs:
            claimed = self.extract_multiline_needs()
        for src_comment in self.src_comments:
            if not src_comment.node.text:
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
            for text, first_row, first_column in _scanned_texts(
                src_comment, claimed.get(id(src_comment))
            ):
                if self.analyse_config.get_need_id_refs:
                    self.need_id_refs.extend(
                        self.extract_anchors(
                            text,
                            filepath,
                            tagged_scope,
                            src_comment,
                            first_row,
                            first_column,
                        )
                    )
                if self.analyse_config.get_oneline_needs:
                    self.oneline_needs.extend(
                        self.extract_oneline_needs(
                            text,
                            filepath,
                            tagged_scope,
                            src_comment,
                            self.analyse_config.oneline_comment_style,
                            first_row,
                            first_column,
                        )
                    )

    def merge_marked_content(self) -> None:
        """List the marked content in source order: by file, row and column (#2150).

        Tree-sitter hands a file's comments over in an order that differs between
        runs, so the column is what keeps two entries of one row in a stable order.
        ``oneline_needs`` is sorted too, by row, then file, then column: ``src-trace``
        creates and renders the needs in its order, so of two markers with one id in
        one file the leftmost is the one created, and on one row the needs of two files
        keep the file order they had before the column was a key -- for a caller that
        passes the files in discovery order, as every production caller does.
        """
        # The file component is the key discovery sorts the files by
        # (``SourceDiscover``), not the ``Path``: a ``Path`` compares by parts, so
        # ``a/b.cpp`` would sort before ``a-c.cpp``, which discovery lists first.
        self.oneline_needs.sort(
            key=lambda x: (
                x.source_map["start"]["row"],
                os.path.normcase(os.path.normpath(x.filepath)),
                x.source_map["start"]["column"],
            )
        )
        self.all_marked_content.extend(self.need_id_refs)
        self.all_marked_content.extend(self.oneline_needs)
        self.all_marked_content.extend(self.multiline_needs)
        self.all_marked_content.sort(
            key=lambda x: (
                x.filepath,
                x.source_map["start"]["row"],
                x.source_map["start"]["column"],
                _KIND_RANK[x.type],
            )
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

    def run(self, *, log_summary: bool = True) -> None:
        """Parse the source files and extract their markers.

        :param log_summary: Whether to print the per-project summary line; a caller
            that prints its own (the configuration pass of the Sphinx extension) passes
            ``False``.
        """
        if (
            self.analyse_config.preprocessor is not None
            and self.analyse_config.comment_type == CommentType.cpp
        ):
            self.create_src_objects_libclang()
        else:
            self.create_src_objects()
        self.extract_marked_content()
        self.merge_marked_content()
        if log_summary:
            self.log_summary()

    def log_summary(self, extra: str = "") -> None:
        """Emit a per-project marker (default-visible) plus a -v breakdown.

        :param extra: Appended to the default-visible line (the ``src-trace``
            directive's count of the one-line needs it did not create).
        """
        label = f"codelinks [{self.name}]" if self.name else "codelinks"
        logger.info(
            f"{label}: {_count(len(self.src_files), 'file')}, "
            f"{_count(len(self.all_marked_content), 'marker')}{extra}"
        )
        logger.debug(
            f"{label}: {_count(len(self.src_comments), 'comment')}, "
            f"{_count(len(self.oneline_needs), 'oneline need')}, "
            f"{_count(len(self.need_id_refs), 'id-ref')}, "
            f"{_count(len(self.multiline_needs), 'multi-line need')}"
        )
