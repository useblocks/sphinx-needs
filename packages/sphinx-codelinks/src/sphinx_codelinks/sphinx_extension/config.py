from dataclasses import MISSING, dataclass, field, fields
from pathlib import Path
from typing import Any, TypedDict, cast

from jsonschema import ValidationError, validate
from sphinx.application import Sphinx
from sphinx.config import Config as _SphinxConfig

from sphinx_codelinks.analyse.config import (
    AnalyseSectionConfigType,
    MarkedRstConfig,
    MarkedRstConfigType,
    NeedIdRefsConfig,
    NeedIdRefsConfigType,
    OneLineCommentStyle,
    OneLineCommentStyleType,
    SourceAnalyseConfig,
    SourceAnalyseConfigType,
)
from sphinx_codelinks.source_discover.config import (
    SourceDiscoverConfig,
    SourceDiscoverSectionConfigType,
)
from sphinx_codelinks.source_discover.source_discover import SourceDiscover

SRC_TRACE_CACHE: str = "src_trace_cache"


class SourceTracingLineHref:
    """Global class for the mapping between source file line numbers and Sphinx documentation links."""

    def __init__(self) -> None:
        self.mappings: dict[str, dict[int, str]] = {}


file_lineno_href = SourceTracingLineHref()


class SrcTraceProjectConfigType(TypedDict, total=False):
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
            generate_project_configs(src_trace_projects)

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


def check_schema(config: SrcTraceSphinxConfig) -> list[str]:
    """Check only first layer's of schema, so that the nested dict is not validated here."""
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


def check_configuration(config: SrcTraceSphinxConfig) -> list[str]:
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
    project_configs: dict[str, SrcTraceProjectConfigType],
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
