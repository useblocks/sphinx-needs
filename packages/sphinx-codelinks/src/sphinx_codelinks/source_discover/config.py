from dataclasses import dataclass, field, fields
from enum import Enum
from pathlib import Path
from typing import Any, Required, TypedDict, cast

from jsonschema import ValidationError, validate

COMMENT_FILETYPE = {
    "cpp": ["c", "ci", "cpp", "cc", "cxx", "h", "hpp", "hxx", "hh", "ihl"],
    "python": ["py"],
    "cs": ["cs"],
    "yaml": ["yml", "yaml"],
}


class CommentType(str, Enum):
    python = "python"
    cpp = "cpp"
    cs = "cs"
    yaml = "yaml"


class SourceDiscoverSectionConfigType(TypedDict, total=False):
    """Define typing for loading configuration from TOML files"""

    src_dir: Required[str]
    exclude: list[str]
    include: list[str]
    gitignore: bool
    comment_type: CommentType


class SourceDiscoverConfigType(TypedDict, total=False):
    """Define typing for its API configuration"""

    src_dir: Required[Path]
    exclude: list[str]
    include: list[str]
    gitignore: bool
    comment_type: CommentType


@dataclass
class SourceDiscoverConfig:
    @classmethod
    def field_names(cls) -> set[str]:
        return {item.name for item in fields(cls)}

    src_dir: Path = field(
        default_factory=lambda: Path("./"), metadata={"schema": {"type": "string"}}
    )
    """The root of the source directory."""

    exclude: list[str] = field(
        default_factory=list,
        metadata={"schema": {"type": "array", "items": {"type": "string"}}},
    )
    """The glob pattern to exclude files."""

    include: list[str] = field(
        default_factory=list,
        metadata={"schema": {"type": "array", "items": {"type": "string"}}},
    )
    """The glob pattern to include files."""

    gitignore: bool = field(default=True, metadata={"schema": {"type": "boolean"}})
    """Whether to respect .gitignore to exclude files."""

    comment_type: str = field(
        default="cpp",
        metadata={
            "schema": {
                "type": "string",
                "enum": sorted(COMMENT_FILETYPE),
            }
        },
    )
    """The file types to discover."""

    @classmethod
    def get_schema(cls, name: str) -> dict[str, Any] | None:  # type: ignore[explicit-any]
        _field = next(_field for _field in fields(cls) if _field.name is name)
        if _field.metadata and "schema" in _field.metadata:
            return cast(dict[str, Any], _field.metadata["schema"])  # type: ignore[explicit-any]
        return None

    def check_schema(self) -> list[str]:
        errors = []
        for _field_name in self.field_names():
            schema = self.get_schema(_field_name)
            value = getattr(self, _field_name)
            if isinstance(value, Path):  # adapt to json schema restriction
                value = str(value)
            try:
                validate(instance=value, schema=schema)  # type: ignore[arg-type]  # validate has no type specified
            except ValidationError as e:
                errors.append(
                    f"Schema validation error in field '{_field_name}': {e.message}"
                )
        return errors
