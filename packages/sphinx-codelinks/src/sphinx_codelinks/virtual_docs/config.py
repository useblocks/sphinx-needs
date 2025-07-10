from dataclasses import MISSING, dataclass, field, fields
import logging
import os
from pathlib import Path
from typing import Any, Literal, TypedDict, cast

from jsonschema import ValidationError, validate

# initialize logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
# log to the console
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logger.addHandler(console)

ESCAPE = "\\"
SUPPORTED_COMMENT_TYPES = {"c", "h", "cpp", "hpp"}


class VirtualDocsConfigType(TypedDict):
    src_files: list[Path] | None
    src_dir: Path
    output_dir: Path
    comment_type: str


@dataclass
class VirtualDocsConfig:
    @classmethod
    def field_names(cls) -> set[str]:
        return {item.name for item in fields(cls)}

    src_files: list[Path] = field(
        metadata={"schema": {"type": "array", "items": {"type": "string"}}},
    )
    """A list of source files to be  processed."""

    src_dir: Path = field(
        default_factory=lambda: Path.cwd(), metadata={"schema": {"type": "string"}}
    )
    """The root of the source directory."""

    output_dir: Path = field(
        default=Path("output"), metadata={"schema": {"type": "string"}}
    )
    """The directory where  the virtual documents and their caches will be stored."""

    comment_type: str = field(default="c", metadata={"schema": {"type": "string"}})
    """The type of comment to be processed."""

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
            if _field_name == "src_files":  # adapt to json schema restriction
                if isinstance(value, list):
                    value: list[str] = [str(src_file) for src_file in value]  # type: ignore[no-redef] # only for value adaptation
            elif isinstance(value, Path):  # adapt to json schema restriction
                value = str(value)

            try:
                validate(instance=value, schema=schema)  # type: ignore[arg-type]  # validate has no type specified
            except ValidationError as e:
                errors.append(
                    f"Schema validation error in field '{_field_name}': {e.message}"
                )
        return errors


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
        default=os.linesep, metadata={"schema": {"type": "string"}}
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
