from collections import deque
from dataclasses import MISSING, dataclass, field, fields
from enum import Enum
from pathlib import Path
from typing import Any, Literal, TypedDict, cast

from jsonschema import ValidationError, validate
from sphinx.application import Sphinx
from sphinx.config import Config as _SphinxConfig

from sphinx_codelinks.source_discover.config import (
    CommentType,
    SourceDiscoverConfig,
    SourceDiscoverSectionConfigType,
)
from sphinx_codelinks.source_discover.source_discover import SourceDiscover

UNIX_NEWLINE = "\n"


COMMENT_MARKERS = {
    CommentType.cpp: ["//", "/*"],
    CommentType.python: ["#"],
    CommentType.cs: ["//", "/*", "///"],
}
ESCAPE = "\\"


class CommentCategory(str, Enum):
    comment = "comment"
    docstring = "expression_statement"


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
        if _field.metadata and "schema" in _field.metadata:
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
        if _field.metadata and "schema" in _field.metadata:
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
        if _field.metadata:
            return cast(list[str], _field.metadata["required_fields"])
        return None

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


class AnalyseSectionConfigType(TypedDict, total=False):
    """Define typing for loading `analyse` section from the file."""

    get_need_id_refs: bool
    get_oneline_needs: bool
    get_rst: bool
    outdir: str
    need_id_refs: NeedIdRefsConfigType
    marked_rst: MarkedRstConfigType
    oneline_comment_style: OneLineCommentStyleType


class SourceAnalyseConfigType(TypedDict, total=False):
    """Define typing for its API configuration."""

    src_files: list[Path]
    src_dir: Path
    comment_type: CommentType
    get_need_id_refs: bool
    get_oneline_needs: bool
    get_rst: bool
    need_id_refs_config: NeedIdRefsConfig
    marked_rst_config: MarkedRstConfig
    oneline_comment_style: OneLineCommentStyle


class ProjectsAnalyseConfigType(TypedDict, total=False):
    projects_config: dict[str, SourceAnalyseConfigType]


@dataclass
class SourceAnalyseConfig:
    @classmethod
    def field_names(cls) -> set[str]:
        return {item.name for item in fields(cls)}

    src_files: list[Path] = field(
        default_factory=list,
        metadata={"schema": {"type": "array", "items": {"type": "string"}}},
    )
    """A list of source files to be  processed."""
    src_dir: Path = field(
        default_factory=lambda: Path("./"), metadata={"schema": {"type": "string"}}
    )

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
        if _field.metadata and "schema" in _field.metadata:
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


SRC_TRACE_CACHE: str = "src_trace_cache"


class SourceTracingLineHref:
    """Global class for the mapping between source file line numbers and Sphinx documentation links."""

    def __init__(self) -> None:
        self.mappings: dict[str, dict[int, str]] = {}


file_lineno_href = SourceTracingLineHref()


class CodeLinksProjectConfigType(TypedDict, total=False):
    """TypedDict defining the configuration structure for individual SrcTrace projects.

    Contains both user-provided configuration:
    - source_discover
    - remote_url_pattern
    - analyse
    and runtime-generated configuration objects
    - source_discover_config
    - analyse_config
    """

    source_discover: SourceDiscoverSectionConfigType
    remote_url_pattern: str
    analyse: AnalyseSectionConfigType
    source_discover_config: SourceDiscoverConfig
    analyse_config: SourceAnalyseConfig


class CodeLinksConfigType(TypedDict):
    config_from_toml: str | None
    set_local_url: bool
    local_url_field: str
    set_remote_url: bool
    remote_url_field: str
    outdir: Path
    projects: dict[str, CodeLinksProjectConfigType]
    debug_measurement: bool
    debug_filters: bool


@dataclass
class CodeLinksConfig:
    @classmethod
    def from_sphinx(cls, sphinx_config: _SphinxConfig) -> "CodeLinksConfig":
        obj = cls()
        super().__setattr__(obj, "_sphinx_config", sphinx_config)
        return obj

    def __getattribute__(self, name: str) -> Any:  # type: ignore[explicit-any]
        if name.startswith("__") or name == "_sphinx_config":
            return super().__getattribute__(name)
        sphinx_config = (
            object.__getattribute__(self, "_sphinx_config")
            if "_sphinx_config" in self.__dict__
            else None
        )
        if sphinx_config:
            return getattr(
                super().__getattribute__("_sphinx_config"), f"src_trace_{name}"
            )

        return object.__getattribute__(self, name)

    def __setattr__(self, name: str, value: Any) -> None:  # type: ignore[explicit-any]
        if name == "_sphinx_config" and "src_trace_projects" in value:
            src_trace_projects: dict[str, CodeLinksProjectConfigType] = value[
                "src_trace_projects"
            ]
            generate_project_configs(src_trace_projects)

        if name.startswith("__") or name == "_sphinx_config":
            return super().__setattr__(name, value)

        sphinx_config = (
            object.__getattribute__(self, "_sphinx_config")
            if "_sphinx_config" in self.__dict__
            else None
        )

        if sphinx_config:
            setattr(
                super().__getattribute__("_sphinx_config"), f"src_trace_{name}", value
            )

        if name == "outdir" and isinstance(value, str):
            # Ensure outdir is a Path object
            value = Path(value)
        return object.__setattr__(self, name, value)

    @classmethod
    def add_config_values(cls, app: Sphinx) -> None:
        """Add all config values to Sphinx application"""
        for item in fields(cls):
            if item.default_factory is not MISSING:
                default = item.default_factory()
            elif item.default is not MISSING:
                default = item.default
            else:
                raise Exception(f"Field {item.name} has no default value or factory")

            name = item.name
            app.add_config_value(
                f"src_trace_{name}",
                default,
                item.metadata["rebuild"],
                types=item.metadata["types"],
            )

    @classmethod
    def field_names(cls) -> set[str]:
        return {item.name for item in fields(cls)}

    @classmethod
    def get_schema(cls, name: str) -> dict[str, Any] | None:  # type: ignore[explicit-any]
        """Get the schema for a config item."""
        _field = next(field for field in fields(cls) if field.name is name)
        if _field.metadata and "schema" in _field.metadata:
            return _field.metadata["schema"]  # type: ignore[no-any-return]
        return None

    config_from_toml: str | None = field(
        default=None,
        metadata={
            "rebuild": "env",
            "types": (str, type(None)),
            "schema": {
                "type": ["string", "null"],
                "examples": ["config.toml", None],
            },
        },
    )
    """Path to a TOML file to load configuration from."""

    set_local_url: bool = field(
        default=False,
        metadata={
            "rebuild": "env",
            "types": (bool,),
            "schema": {
                "type": "boolean",
            },
        },
    )
    """Set the file URL in the extracted need."""

    local_url_field: str = field(
        default="local-url",
        metadata={
            "rebuild": "env",
            "types": (str,),
            "schema": {
                "type": "string",
            },
        },
    )
    """The field name for the file URL in the extracted need."""

    set_remote_url: bool = field(
        default=False,
        metadata={
            "rebuild": "env",
            "types": (bool,),
            "schema": {
                "type": "boolean",
            },
        },
    )
    remote_url_field: str = field(
        default="remote-url",
        metadata={
            "rebuild": "env",
            "types": (str,),
            "schema": {
                "type": "string",
            },
        },
    )
    """The field name for the remote URL in the extracted need."""

    outdir: Path = field(
        default=Path("output"),
        metadata={"rebuild": "env", "types": (str), "schema": {"type": "string"}},
    )
    """The directory where  the generated artifacts and their caches will be stored."""

    projects: dict[str, CodeLinksProjectConfigType] = field(
        default_factory=dict,
        metadata={
            "rebuild": "env",
            "types": (),
            "schema": {
                "type": "object",
                "additionalProperties": {
                    "type": "object",
                    "properties": {
                        "source_discover": {},
                        "analyse": {},
                        "remote_url_pattern": {},
                        "source_discover_config": {},
                        "analyse_config": {},
                    },
                    "additionalProperties": False,
                },
            },
        },
    )
    """The configuration for the source tracing projects."""

    debug_measurement: bool = field(
        default=False, metadata={"rebuild": "html", "types": (bool,)}
    )
    """If True, log runtime information for various functions."""
    debug_filters: bool = field(
        default=False, metadata={"rebuild": "html", "types": (bool,)}
    )
    """If True, log filter processing runtime information."""


def check_schema(config: CodeLinksConfig) -> list[str]:
    """Check only first layer's of schema, so that the nested dict is not validated here."""
    errors = []
    for _field_name in CodeLinksConfig.field_names():
        schema = CodeLinksConfig.get_schema(_field_name)
        if not schema:
            continue
        value = getattr(config, _field_name)
        if isinstance(value, Path):  # adapt to json schema restriction
            value = str(value)
        try:
            validate(instance=value, schema=schema)
        except ValidationError as e:
            errors.append(
                f"Schema validation error in filed '{_field_name}': {e.message}"
            )
    return errors


def check_project_configuration(config: CodeLinksConfig) -> list[str]:
    """Check nested project configurations"""
    errors = []

    for project_name, project_config in config.projects.items():
        project_errors: list[str] = []

        # validate source_discover config
        src_discover_config: SourceDiscoverConfig | None = project_config.get(
            "source_discover_config"
        )
        src_discover_errors = []
        if src_discover_config:
            src_discover_errors.extend(src_discover_config.check_schema())

        # validate analyse config
        analyse_config: SourceAnalyseConfig | None = project_config.get(
            "analyse_config"
        )
        analyse_errors = []
        if analyse_config:
            analyse_errors = analyse_config.check_fields_configuration()

        # validate src-trace config
        if config.set_remote_url and "remote_url_pattern" not in project_config:
            project_errors.append(
                "remote_url_pattern must be given, as set_remote_url is enabled"
            )

        if "remote_url_pattern" in project_config and not isinstance(
            project_config["remote_url_pattern"], str
        ):
            project_errors.append("remote_url_pattern must be a string")

        if analyse_errors or src_discover_errors or project_errors:
            errors.append(f"Project '{project_name}' has the following errors:")
            errors.extend(analyse_errors)
            errors.extend(src_discover_errors)
            errors.extend(project_errors)

    return errors


def check_configuration(config: CodeLinksConfig) -> list[str]:
    errors = []
    errors.extend(check_schema(config))
    errors.extend(check_project_configuration(config))
    return errors


def convert_src_discovery_config(
    config_dict: SourceDiscoverSectionConfigType | None,
) -> SourceDiscoverConfig:
    if config_dict:
        src_discover_dict = {
            key: (Path(value) if key == "src_dir" and isinstance(value, str) else value)
            for key, value in config_dict.items()
        }
        src_discover_config = SourceDiscoverConfig(**src_discover_dict)  # type: ignore[arg-type] # mypy is confused by dynamic assignment
    else:
        src_discover_config = SourceDiscoverConfig()

    return src_discover_config


def convert_analyse_config(
    config_dict: AnalyseSectionConfigType | None,
    src_discover: SourceDiscover | None = None,
) -> SourceAnalyseConfig:
    analyse_config_dict: SourceAnalyseConfigType = {}
    if config_dict:
        for k, v in config_dict.items():
            if k not in {"online_comment_style", "need_id_refs", "marked_rst"}:
                analyse_config_dict[k] = (  # type: ignore[literal-required]  # dynamical assignment
                    Path(v) if k == "src_dic" and isinstance(v, str) else v
                )

        # Get oneline_comment_style configuration
        oneline_comment_style_dict: OneLineCommentStyleType | None = config_dict.get(
            "oneline_comment_style"
        )
        oneline_comment_style: OneLineCommentStyle = (
            convert_oneline_comment_style_config(oneline_comment_style_dict)
        )

        # Get need_id_refs configuration
        need_id_refs_config_dict: NeedIdRefsConfigType | None = config_dict.get(
            "need_id_refs"
        )
        need_id_refs_config = convert_need_id_refs_config(need_id_refs_config_dict)

        # Get marked_rst configuration
        marked_rst_config_dict: MarkedRstConfigType | None = config_dict.get(
            "marked_rst"
        )
        marked_rst_config = convert_marked_rst_config(marked_rst_config_dict)

        analyse_config_dict["need_id_refs_config"] = need_id_refs_config
        analyse_config_dict["marked_rst_config"] = marked_rst_config
        analyse_config_dict["oneline_comment_style"] = oneline_comment_style

    if src_discover:
        analyse_config_dict["src_files"] = src_discover.source_paths
        analyse_config_dict["src_dir"] = src_discover.src_discover_config.src_dir

    return SourceAnalyseConfig(**analyse_config_dict)


def convert_oneline_comment_style_config(
    config_dict: OneLineCommentStyleType | None,
) -> OneLineCommentStyle:
    if config_dict is None:
        oneline_comment_style = OneLineCommentStyle()
    else:
        try:
            oneline_comment_style = OneLineCommentStyle(**config_dict)
        except TypeError as e:
            raise TypeError(f"Invalid oneline comment style configuration: {e}") from e
    return oneline_comment_style


def convert_need_id_refs_config(
    config_dict: NeedIdRefsConfigType | None,
) -> NeedIdRefsConfig:
    if not config_dict:
        need_id_refs_config = NeedIdRefsConfig()
    else:
        try:
            need_id_refs_config = NeedIdRefsConfig(**config_dict)
        except TypeError as e:
            raise TypeError(f"Invalid oneline comment style configuration: {e}") from e
    return need_id_refs_config


def convert_marked_rst_config(
    config_dict: MarkedRstConfigType | None,
) -> MarkedRstConfig:
    if not config_dict:
        marked_rst_config = MarkedRstConfig()
    else:
        try:
            marked_rst_config = MarkedRstConfig(**config_dict)
        except TypeError as e:
            raise TypeError(f"Invalid oneline comment style configuration: {e}") from e
    return marked_rst_config


def generate_project_configs(
    project_configs: dict[str, CodeLinksProjectConfigType],
) -> None:
    """Generate configs of source discover and analyse from their classes dynamically."""
    for project_config in project_configs.values():
        # overwrite the config into different types on purpose
        # covert dicts to their own classes
        src_discover_section: SourceDiscoverSectionConfigType | None = cast(
            SourceDiscoverSectionConfigType,
            project_config.get("source_discover"),
        )
        source_discover_config = convert_src_discovery_config(src_discover_section)
        project_config["source_discover_config"] = source_discover_config

        analyse_section_config: AnalyseSectionConfigType | None = cast(
            AnalyseSectionConfigType, project_config.get("analyse")
        )
        analyse_config = convert_analyse_config(analyse_section_config)
        analyse_config.get_oneline_needs = True  # force to get oneline_need
        project_config["analyse_config"] = analyse_config
