from collections import deque
from dataclasses import MISSING, dataclass, field, fields
from enum import Enum
from pathlib import Path
from typing import Any, Literal, TypedDict, cast

from jsonschema import ValidationError, validate

UNIX_NEWLINE = "\n"


class CommentType(str, Enum):
    python = "python"
    cpp = "cpp"


COMMENT_FILETYPE = {"cpp": ["c", "cpp", "h", "hpp"], "python": ["py"]}
COMMENT_MARKERS = {CommentType.cpp: ["//", "/*"], CommentType.python: ["#"]}
ESCAPE = "\\"
SUPPORTED_COMMENT_TYPES = {"c", "h", "cpp", "hpp", "py"}


class CommentCategory(str, Enum):
    comment = "comment"
    docstring = "expression_statement"


class SrcDiscoverConfigType4Analyse(TypedDict, total=False):
    src_dir: str
    exclude: list[str]
    include: list[str]
    gitignore: bool
    comment_type: list[CommentType]


class NeedIdRefsConfigType(TypedDict):
    markers: list[str]


@dataclass
class NeedIdRefsConfig:
    @classmethod
    def field_names(cls) -> set[str]:
        return {item.name for item in fields(cls)}

    markers: list[str] = field(
        default_factory=lambda: ["@need-ids:"],
        metadata={"schema": {"type": "array", "items": {"type": "string"}}},
    )
    """The markers to extract need ids from"""

    @classmethod
    def get_schema(cls, name: str) -> dict[str, Any] | None:  # type: ignore[explicit-any]
        _field = next(_field for _field in fields(cls) if _field.name is name)
        if _field.metadata is not MISSING and "schema" in _field.metadata:
            return cast(dict[str, Any], _field.metadata["schema"])  # type: ignore[explicit-any]
        return None

    def check_schema(self) -> list[str]:
        errors = []
        for _field_name in self.field_names():
            schema = self.get_schema(_field_name)
            value = getattr(self, _field_name)
            try:
                validate(instance=value, schema=schema)  # type: ignore[arg-type]  # validate has no type
            except ValidationError as e:
                errors.append(
                    f"Schema validation error in field '{_field_name}': {e.message}"
                )
        return errors


class MarkedRstConfigType(TypedDict):
    start_sequence: str
    end_sequence: str


@dataclass
class MarkedRstConfig:
    @classmethod
    def field_names(cls) -> set[str]:
        return {item.name for item in fields(cls)}

    start_sequence: str = field(default="@rst", metadata={"schema": {"type": "string"}})
    """Chars sequence to indicate the start of the rst text."""
    end_sequence: str = field(
        default="@endrst", metadata={"schema": {"type": "string"}}
    )
    """Chars sequence to indicate the end of the rst text."""

    @classmethod
    def get_schema(cls, name: str) -> dict[str, Any] | None:  # type: ignore[explicit-any]
        _field = next(_field for _field in fields(cls) if _field.name is name)
        if _field.metadata is not MISSING and "schema" in _field.metadata:
            return cast(dict[str, Any], _field.metadata["schema"])  # type: ignore[explicit-any]
        return None

    def check_schema(self) -> list[str]:
        errors = []
        for _field_name in self.field_names():
            schema = self.get_schema(_field_name)
            value = getattr(self, _field_name)
            try:
                validate(instance=value, schema=schema)  # type: ignore[arg-type]  # validate has no type
            except ValidationError as e:
                errors.append(
                    f"Schema validation error in field '{_field_name}': {e.message}"
                )
        return errors

    def check_sequence_mutually_exclusive(self) -> list[str]:
        errors = []
        if self.start_sequence == self.end_sequence:
            errors.append("start_sequence and end_sequence cannot be the same.")
        return errors

    def check_fields_configuration(self) -> list[str]:
        return self.check_schema() + self.check_sequence_mutually_exclusive()


class FieldConfig(TypedDict, total=False):
    name: str
    type: Literal["str", "list[str]"]
    default: str | list[str] | None


class OneLineCommentStyleType(TypedDict):
    start_sequence: str
    end_sequence: str
    field_split_char: str
    needs_fields: list[FieldConfig]


@dataclass
class OneLineCommentStyle:
    def __setattr__(self, name: str, value: Any) -> None:  # type: ignore[explicit-any]
        if name == "needs_fields":
            # apply default to fields
            self.apply_needs_field_default(value)
        return super().__setattr__(name, value)

    @classmethod
    def field_names(cls) -> set[str]:
        return {item.name for item in fields(cls)}

    start_sequence: str = field(default="@", metadata={"schema": {"type": "string"}})
    """Chars sequence to indicate the start of the one-line comment."""

    end_sequence: str = field(
        default=UNIX_NEWLINE, metadata={"schema": {"type": "string"}}
    )
    """Chars sequence to indicate the end of the one-line comment."""

    field_split_char: str = field(default=",", metadata={"schema": {"type": "string"}})
    """Char sequence to split the fields."""

    needs_fields: list[FieldConfig] = field(
        default_factory=lambda: [
            {"name": "title"},
            {"name": "id"},
            {"name": "type", "default": "impl"},
            {"name": "links", "type": "list[str]", "default": []},
        ],
        metadata={
            "required_fields": ["title", "type"],
            "field_default": {
                "type": "str",
            },
            "schema": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "type": {
                            "type": "string",
                            "enum": ["str", "list[str]"],
                            "default": "str",
                        },
                        "default": {
                            "anyOf": [
                                {"type": "string"},
                                {"type": "array", "items": {"type": "string"}},
                            ]
                        },
                    },
                    "required": ["name"],
                    "additionalProperties": False,
                    "allOf": [
                        {
                            "if": {"properties": {"type": {"const": "list[str]"}}},
                            "then": {
                                "properties": {
                                    "default": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    }
                                }
                            },
                        },
                        {
                            "if": {"properties": {"type": {"const": "str"}}},
                            "then": {"properties": {"default": {"type": "string"}}},
                        },
                    ],
                },
            },
        },
    )

    @classmethod
    def apply_needs_field_default(cls, given_fields: list[FieldConfig]) -> None:
        field_default = next(
            _field.metadata["field_default"]
            for _field in fields(cls)
            if _field.name == "needs_fields"
        )

        for _field in given_fields:
            for _default in field_default:
                if _default not in _field:
                    _field[_default] = field_default[_default]  # type: ignore[literal-required]  # dynamically assign keys

    @classmethod
    def get_required_fields(cls, name: str) -> list[str] | None:
        _field = next(_field for _field in fields(cls) if _field.name is name)
        if _field.metadata is not MISSING:
            return cast(list[str], _field.metadata["required_fields"])
        return None

    @classmethod
    def get_schema(cls, name: str) -> dict[str, Any] | None:  # type: ignore[explicit-any]
        _field = next(_field for _field in fields(cls) if _field.name is name)
        if _field.metadata is not MISSING and "schema" in _field.metadata:
            return cast(dict[str, Any], _field.metadata["schema"])  # type: ignore[explicit-any]
        return None

    def check_schema(self) -> list[str]:
        errors = []
        for _field_name in self.field_names():
            schema = self.get_schema(_field_name)
            value = getattr(self, _field_name)
            try:
                validate(instance=value, schema=schema)  # type: ignore[arg-type]  # validate has no type specified
            except ValidationError as e:
                if _field_name == "needs_fields":
                    need_field_name = value[e.path[0]]["name"]
                    errors.append(
                        f"Schema validation error in need_fields '{need_field_name}': {e.message}"
                    )
                else:
                    errors.append(
                        f"Schema validation error in field '{_field_name}': {e.message}"
                    )
        return errors

    def check_required_fields(self) -> list[str]:
        errors = []
        required_fields = self.get_required_fields("needs_fields")
        if required_fields is None:
            errors.append("No required fields specified.")
            return errors
        given_field_names = [_field["name"] for _field in self.needs_fields]
        missing_fields = set(required_fields) - set(given_field_names)
        if len(missing_fields) != 0:
            errors.append(f"Missing required fields: {sorted(missing_fields)}")

        return errors

    def check_fields_mutually_exclusive(self) -> list[str]:
        errors = []
        needs_field_names = set()
        for _field in self.needs_fields:
            if _field["name"] in needs_field_names:
                errors.append(f"Field '{_field['name']}' is defined multiple times.")
            needs_field_names.add(_field["name"])
        return errors

    def check_fields_configuration(self) -> list[str]:
        return (
            self.check_schema()
            + self.check_required_fields()
            + self.check_fields_mutually_exclusive()
        )

    def get_cnt_required_fields(self) -> int:
        cnt_required_fields = 0
        for _field in self.needs_fields:
            if _field.get("default") is None:
                cnt_required_fields += 1
        return cnt_required_fields

    def get_pos_list_str(self) -> list[int]:
        pos_list_str = []
        for idx, _field in enumerate(self.needs_fields):
            if _field["type"] == "list[str]":
                pos_list_str.append(idx + 1)
        return pos_list_str


class SourceAnalyseConfigFileType(TypedDict, total=False):
    src_discover: SrcDiscoverConfigType4Analyse
    get_need_id_refs: bool
    get_oneline_needs: bool
    get_rst: bool
    outdir: str
    need_id_refs: NeedIdRefsConfigType
    marked_rst: MarkedRstConfigType
    oneline_comment_style: OneLineCommentStyleType


class SourceAnalyseConfigType(TypedDict, total=False):
    src_files: list[Path]
    src_dir: Path
    outdir: Path
    comment_type: CommentType
    get_need_id_refs: bool
    get_oneline_needs: bool
    get_rst: bool
    need_id_refs_config: NeedIdRefsConfig
    marked_rst_config: MarkedRstConfig
    oneline_comment_style: OneLineCommentStyle


@dataclass
class SourceAnalyseConfig:
    @classmethod
    def field_names(cls) -> set[str]:
        return {item.name for item in fields(cls)}

    src_files: list[Path] = field(
        metadata={"schema": {"type": "array", "items": {"type": "string"}}},
    )
    """A list of source files to be  processed."""
    src_dir: Path = field(
        default_factory=lambda: Path("./"), metadata={"schema": {"type": "string"}}
    )

    outdir: Path = field(
        default=Path("output"), metadata={"schema": {"type": "string"}}
    )
    """The directory where  the virtual documents and their caches will be stored."""

    comment_type: CommentType = field(
        default=CommentType.cpp, metadata={"schema": {"type": "string"}}
    )
    """The type of comment to be processed."""

    get_need_id_refs: bool = field(
        default=True, metadata={"schema": {"type": "boolean"}}
    )
    """Whether to extract need id references from comments"""

    get_oneline_needs: bool = field(
        default=False, metadata={"schema": {"type": "boolean"}}
    )
    """Whether to extract oneline needs from comments"""

    get_rst: bool = field(default=False, metadata={"schema": {"type": "boolean"}})
    """Whether to extract rst texts from comments"""

    need_id_refs_config: NeedIdRefsConfig = field(default_factory=NeedIdRefsConfig)
    """Configuration for extracting need id references from comments."""

    marked_rst_config: MarkedRstConfig = field(default_factory=MarkedRstConfig)
    """Configuration for extracting rst texts from comments."""

    oneline_comment_style: OneLineCommentStyle = field(
        default_factory=OneLineCommentStyle
    )
    """Configuration for extracting oneline needs from comments."""

    @classmethod
    def get_schema(cls, name: str) -> dict[str, Any] | None:  # type: ignore[explicit-any]
        _field = next(_field for _field in fields(cls) if _field.name is name)
        if _field.metadata is not MISSING and "schema" in _field.metadata:
            return cast(dict[str, Any], _field.metadata["schema"])  # type: ignore[explicit-any]
        return None

    def check_schema(self) -> list[str]:
        errors = []
        for _field_name in self.field_names():
            schema = self.get_schema(_field_name)
            if not schema:
                continue
            value = getattr(self, _field_name)
            if isinstance(value, Path):  # adapt to json schema restriction
                value = str(value)
            if _field_name == "src_files" and isinstance(
                value, list
            ):  # adapt to json schema restriction
                value: list[str] = [str(src_file) for src_file in value]  # type: ignore[no-redef] # only for value adaptation
            try:
                validate(instance=value, schema=schema)
            except ValidationError as e:
                errors.append(
                    f"Schema validation error in field '{_field_name}': {e.message}"
                )
        return errors

    def check_markers_mutually_exclusive(self) -> list[str]:
        errors = set()
        markers = set()
        markers.add(self.oneline_comment_style.start_sequence)
        markers.add(self.oneline_comment_style.end_sequence)
        if self.marked_rst_config.start_sequence in markers:
            errors.add(
                f"Marker {self.marked_rst_config.start_sequence} is defined multiple times"
            )
        else:
            markers.add(self.marked_rst_config.start_sequence)
        if self.marked_rst_config.end_sequence in markers:
            errors.add(
                f"Marker {self.marked_rst_config.end_sequence} is defined multiple times"
            )
        else:
            markers.add(self.marked_rst_config.end_sequence)

        for marker in self.need_id_refs_config.markers:
            if marker in markers:
                errors.add(f"Marker {marker} is defined multiple times")
            else:
                markers.add(marker)
        return list(errors)

    def check_fields_configuration(self) -> list[str]:
        errors: deque[str] = deque()
        if self.get_need_id_refs:
            need_id_refs_errors = self.need_id_refs_config.check_schema()
            if need_id_refs_errors:
                errors.appendleft("NeedIdRefs configuration errors:")
                errors.extend(need_id_refs_errors)
        if self.get_oneline_needs:
            oneline_needs_errors = (
                self.oneline_comment_style.check_fields_configuration()
            )
            if oneline_needs_errors:
                errors.appendleft("OneLineCommentStyle configuration errors:")
                errors.extend(oneline_needs_errors)
        if self.get_rst:
            marked_rst_errors = self.marked_rst_config.check_fields_configuration()
            if marked_rst_errors:
                errors.appendleft("MarkedRst configuration errors:")
                errors.extend(self.marked_rst_config.check_fields_configuration())
        analyse_errors = self.check_markers_mutually_exclusive() + self.check_schema()
        if analyse_errors:
            errors.appendleft("analyse configuration errors:")
            errors.extend(analyse_errors)
        return list(errors)
