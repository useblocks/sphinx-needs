from dataclasses import MISSING, dataclass, field, fields
from pathlib import Path
from typing import Any, Literal, TypedDict, cast

from jsonschema import ValidationError, validate
from sphinx.application import Sphinx
from sphinx.config import Config as _SphinxConfig

from sphinx_codelinks.source_discovery.config import (
    SourceDiscoveryConfig,
    SourceDiscoveryConfigType,
)
from sphinx_codelinks.virtual_docs.config import (
    SUPPORTED_COMMENT_TYPES,
    OneLineCommentStyle,
    OneLineCommentStyleType,
)

SRC_TRACE_CACHE: str = "src_trace_cache"


class SourceTracingLineHref:
    """Global class for the mapping between source file line numbers and Sphinx documentation links."""

    def __init__(self) -> None:
        self.mappings: dict[str, dict[int, str]] = {}


file_lineno_href = SourceTracingLineHref()


class SrcTraceProjectConfigFileType(TypedDict):
    # only support C/C++ for now
    comment_type: Literal["cpp", "hpp", "c", "h"]
    src_dir: str
    remote_url_pattern: str
    exclude: list[str]
    include: list[str]
    gitignore: bool
    oneline_comment_style: OneLineCommentStyleType


class SrcTraceProjectConfigType(TypedDict):
    # only support C/C++ for now
    comment_type: Literal["cpp", "hpp", "c", "h"]
    src_dir: Path
    remote_url_pattern: str
    exclude: list[str]
    include: list[str]
    gitignore: bool
    oneline_comment_style: OneLineCommentStyle


class SrcTraceConfigType(TypedDict):
    config_from_toml: str | None
    set_local_url: bool
    local_url_field: str
    set_remote_url: bool
    remote_url_field: str
    projects: dict[str, SrcTraceProjectConfigType]
    debug_measurement: bool
    debug_filters: bool


@dataclass
class SrcTraceSphinxConfig:
    def __init__(self, config: _SphinxConfig) -> None:
        super().__setattr__("_config", config)

    def __getattribute__(self, name: str) -> Any:  # type: ignore[explicit-any]
        if name.startswith("__") or name == "_config":
            return super().__getattribute__(name)
        return getattr(super().__getattribute__("_config"), f"src_trace_{name}")

    def __setattr__(self, name: str, value: Any) -> None:  # type: ignore[explicit-any]
        if name == "_config" and "src_trace_projects" in value:
            src_trace_projects: dict[str, SrcTraceProjectConfigType] = value[
                "src_trace_projects"
            ]
            for _config in src_trace_projects.values():
                # overwrite the config into different types on purpose
                # covert dict to OneLineCommentStyle class
                oneline_comment_style: OneLineCommentStyleType | None = cast(
                    OneLineCommentStyleType, _config.get("oneline_comment_style")
                )
                if not oneline_comment_style:
                    raise Exception("OneLineCommentStyle is not given")

                _config["oneline_comment_style"] = OneLineCommentStyle(
                    **oneline_comment_style
                )
        if name.startswith("__") or name == "_config":
            return super().__setattr__(name, value)

        return setattr(super().__getattribute__("_config"), f"src_trace_{name}", value)

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
        if _field.metadata is not MISSING and "schema" in _field.metadata:
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

    projects: dict[str, SrcTraceProjectConfigType] = field(
        default_factory=dict,
        metadata={
            "rebuild": "env",
            "types": (),
            "schema": {
                "type": "object",
                "additionalProperties": {
                    "type": "object",
                    "properties": {
                        "comment_type": {},
                        "src_dir": {},
                        "remote_url_pattern": {},
                        "exclude": {},
                        "include": {},
                        "gitignore": {},
                        "oneline_comment_style": {},
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


def check_schema(config: SrcTraceSphinxConfig) -> list[str]:
    errors = []
    for _field_name in SrcTraceSphinxConfig.field_names():
        schema = SrcTraceSphinxConfig.get_schema(_field_name)
        value = getattr(config, _field_name)
        if not schema:
            continue
        try:
            validate(instance=value, schema=schema)
        except ValidationError as e:
            errors.append(
                f"Schema validation error in filed '{_field_name}': {e.message}"
            )
    return errors


def check_project_configuration(config: SrcTraceSphinxConfig) -> list[str]:
    errors = []

    for project_name, project_config in config.projects.items():
        project_errors: list[str] = []
        oneline_errors = validate_oneline_comment_style(project_config)
        src_discovery_dict = build_src_discovery_dict(project_config)
        src_discovery_errors = []
        if src_discovery_dict is not None:
            src_discovery_config = SourceDiscoveryConfig(**src_discovery_dict)
            src_discovery_errors.extend(src_discovery_config.check_schema())

        if config.set_remote_url and "remote_url_pattern" not in project_config:
            project_errors.append(
                "remote_url_pattern must be given, as set_remote_url is enabled"
            )

        if "remote_url_pattern" in project_config and not isinstance(
            project_config["remote_url_pattern"], str
        ):
            project_errors.append("remote_url_pattern must be a string")

        if oneline_errors or src_discovery_errors or project_errors:
            errors.append(f"Project '{project_name}' has the following errors:")
            errors.extend(oneline_errors)
            errors.extend(src_discovery_errors)
            errors.extend(project_errors)

    return errors


def check_configuration(config: SrcTraceSphinxConfig) -> list[str]:
    errors = []
    errors.extend(check_schema(config))
    errors.extend(check_project_configuration(config))
    return errors


def validate_oneline_comment_style(
    project_config: SrcTraceProjectConfigType,
) -> list[str]:
    if "oneline_comment_style" in project_config:
        style = project_config["oneline_comment_style"]
        if isinstance(style, OneLineCommentStyle):
            return style.check_fields_configuration()
    return []


def build_src_discovery_dict(
    project_config: SrcTraceProjectConfigType,
) -> SourceDiscoveryConfigType | None:
    src_discovery_dict = cast(SourceDiscoveryConfigType, {})
    # adapt the configs between source tracing and source discovery
    if "comment_type" in project_config:
        # comment type error will be taken care by SourceDiscovery class later
        src_discovery_dict["file_types"] = (
            list(SUPPORTED_COMMENT_TYPES)
            if project_config["comment_type"] in SUPPORTED_COMMENT_TYPES
            else [project_config["comment_type"]]
        )
    for key in ("exclude", "include", "gitignore", "src_dir"):
        if key in project_config:
            src_discovery_dict[key] = project_config[key]

    return src_discovery_dict


def adpat_src_discovery_config(project_config: SrcTraceProjectConfigType) -> None:
    src_discovery_dict = build_src_discovery_dict(project_config)
    if src_discovery_dict:
        src_discovery_config = SourceDiscoveryConfig(**src_discovery_dict)
    else:
        src_discovery_config = SourceDiscoveryConfig()

    for _field in fields(src_discovery_config):
        key = "comment_type" if _field.name == "file_types" else _field.name

        if key == "comment_type":
            file_types = getattr(src_discovery_config, _field.name)
            if set(file_types) == SUPPORTED_COMMENT_TYPES:
                comment_type = "cpp"
            else:
                comment_type = file_types[0]
            project_config[key] = comment_type  # type: ignore[literal-required]  # dynamically assign
            continue

        project_config[key] = getattr(src_discovery_config, _field.name)  # type: ignore[literal-required]  # dynamically assign
