from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path

from comment_parser.parsers.c_parser import (  # type: ignore[import-untyped]
    extract_comments,
)
from comment_parser.parsers.common import Comment  # type: ignore[import-untyped]

from sphinx_codelinks.virtual_docs.config import (
    SUPPORTED_COMMENT_TYPES,
    OneLineCommentStyle,
)
from sphinx_codelinks.virtual_docs.ubt_models import UBTCache, UBTComment, UBTSourceFile
from sphinx_codelinks.virtual_docs.utils import (
    OnelineParserInvalidWarning,
    oneline_parser,
)

# initialize logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
# log to the console
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logger.addHandler(console)


@dataclass
class VirtualDocsOneLineWarning:
    file_path: str
    lineno: int
    msg: str
    type: str
    sub_type: str


class VirtualDocs:
    warning_filepath: Path = Path("cached_warnings") / "vdocs_warnings.json"

    def __init__(
        self,
        src_files: list[Path],
        src_dir: str,
        output_dir: str,
        oneline_comment_style: OneLineCommentStyle,
        comment_type: str = "c",
    ) -> None:
        self.src_files = src_files
        self.src_dir = Path(src_dir)
        self.output_dir = Path(output_dir)
        self.comment_type = comment_type
        self.cache = UBTCache(str(self.output_dir / "ubt_cache.json"))
        self.cache.add_uncached_files(self._uncached_files())
        self.virtual_docs: list[UBTSourceFile] = []
        self.oneline_comment_style = oneline_comment_style
        self.oneline_warnings: list[VirtualDocsOneLineWarning] = []
        self.warnings_path = self.output_dir / VirtualDocs.warning_filepath

    def collect(self) -> None:
        # import C parser to avoid `python-magic` dependency
        # https://github.com/jeanralphaviles/comment_parser?tab=readme-ov-file#osx-and-windows
        if self.comment_type not in SUPPORTED_COMMENT_TYPES:
            raise Exception(
                f"Unsupported comment type: {self.comment_type}. Supported types are: {SUPPORTED_COMMENT_TYPES}."
            )

        virtual_docs = []
        self.load_virtual_docs()
        # parse all uncached files
        for src_file in self.cache.uncached_files:
            ml_comments: list[Comment] = []
            oneline_comments: list[Comment] = []
            with src_file.filepath.open("r", encoding="utf-8") as code:
                comments = extract_comments(code.read())

            # separate one-line and multi-line comments
            for comment in comments:
                if comment.is_multiline():
                    ml_comments.append(comment)
                else:
                    oneline_comments.append(comment)

            # break all multi-line comments to single-line comments
            for comment in ml_comments:
                single_lines = comment.text().splitlines()
                for idx, line in enumerate(single_lines):
                    oneline_comments.append(Comment(line, comment.line_number() + idx))

            ubt_comments: list[UBTComment] = []

            for comment in oneline_comments:
                resolved = oneline_parser(
                    f"{comment.text()}{os.linesep}", self.oneline_comment_style
                )

                if isinstance(resolved, OnelineParserInvalidWarning):
                    self.oneline_warnings.append(
                        VirtualDocsOneLineWarning(
                            str(src_file.filepath),
                            comment.line_number(),
                            resolved.msg,
                            type="oneline",
                            sub_type=resolved.sub_type.value,
                        )
                    )
                    continue

                if resolved:
                    ubt_comments.append(
                        UBTComment(
                            f"{comment.text()}{os.linesep}",
                            start_line=comment.line_number(),
                            resolved_marker=resolved,
                        )
                    )

            ubt_comments.sort(key=lambda x: x.start_line)
            src_file.add_comments(ubt_comments)
            virtual_docs.append(src_file)

        self.virtual_docs.extend(virtual_docs)
        self.update_warnings()

    def _uncached_files(self) -> list[UBTSourceFile]:
        uncached_files = []
        for src_file in self.src_files:
            ubt_src_file = UBTSourceFile(
                src_file, self.src_dir, output_dir=str(self.output_dir)
            )
            # check cached virtual documents
            if (
                str(src_file) in self.cache.cached_files
                and (
                    self.output_dir
                    / (src_file.with_suffix(".json").relative_to(self.src_dir))
                ).exists()
                and self.cache.cached_files.get(str(ubt_src_file.filepath))
                == ubt_src_file.changed_date
            ):
                continue
            uncached_files.append(ubt_src_file)
        return uncached_files

    def dump_virtual_docs(self) -> None:
        for src_file in self.virtual_docs:
            src_file.to_json()

    @classmethod
    def load_warnings(
        cls, warnings_dir: Path
    ) -> list[VirtualDocsOneLineWarning] | None:
        """Load warnings from the given path.

        It mainly used for other apps or users to load warnings files directly.
        """
        warnings_path = warnings_dir / cls.warning_filepath
        if not warnings_path.exists():
            return None
        with warnings_path.open("r") as f:
            # load the json file and convert to VirtualDocsOneLineWarning]
            warnings = json.load(f)
            loaded_warnings = [
                VirtualDocsOneLineWarning(**warning) for warning in warnings
            ]
        return loaded_warnings

    def _load_warnings(self) -> list[VirtualDocsOneLineWarning] | None:
        if not self.warnings_path.exists():
            return None
        with self.warnings_path.open("r") as f:
            # load the json file and convert to VirtualDocsOneLineWarning]
            warnings = json.load(f)
            loaded_warnings = [
                VirtualDocsOneLineWarning(**warning) for warning in warnings
            ]
        return loaded_warnings

    def update_warnings(self) -> None:
        loaded_warnings = self._load_warnings()
        current_warnings = [_warning.__dict__ for _warning in self.oneline_warnings]
        if loaded_warnings:
            _warnings = [_warning.__dict__ for _warning in loaded_warnings]
            cached_warnings = [
                _warning
                for _warning in _warnings
                if not (
                    _warning["file_path"]
                    in [str(src_file) for src_file in self.src_files]
                    and _warning["file_path"]
                    in [
                        str(ubt_src_file.filepath)
                        for ubt_src_file in self.cache.uncached_files
                    ]
                )
            ]
            total_warning = cached_warnings + current_warnings
        else:
            total_warning = current_warnings
        if not self.warnings_path.parent.exists():
            self.warnings_path.parent.mkdir(parents=True)
        with self.warnings_path.open("w") as f:
            json.dump(
                total_warning,
                f,
            )

    def load_virtual_docs(self) -> None:
        # only load cached files that are in the self.src_files
        src_files = [
            src_file
            for src_file in self.cache.cached_files
            if src_file in [str(file_path) for file_path in self.src_files]
        ]
        for src_file in src_files:
            src_path = Path(src_file)
            virt_doc_path = self.output_dir / (
                src_path.with_suffix(".json").relative_to(self.src_dir)
            )
            if virt_doc_path.exists():
                ubt_src_file = UBTSourceFile(
                    src_path, self.src_dir, output_dir=str(self.output_dir)
                )
                comments = json.load(virt_doc_path.open("r"))
                ubt_src_file.add_comments(
                    [
                        UBTComment(
                            text=comment["text"],
                            start_line=comment["start_line"],
                            resolved_marker=comment["resolved_marker"],
                            marker_type=comment["marker_type"],
                        )
                        for comment in comments
                    ]
                )
                self.virtual_docs.append(ubt_src_file)
