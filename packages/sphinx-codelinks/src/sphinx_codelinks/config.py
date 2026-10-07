from collections import deque
from dataclasses import MISSING, dataclass, field, fields, replace
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
from ub_project import anchor, load_toml, select_table

UNIX_NEWLINE = "\n"


COMMENT_MARKERS = {
    # @Support C and C++ style comments, IMPL_C_1, impl, [FE_C_SUPPORT, FE_CPP]
    CommentType.cpp: ["//", "/*"],
    # @Support Python style comments, IMPL_PY_1, impl, [FE_PY]
    CommentType.python: ["#"],
    CommentType.cs: ["//", "/*", "///"],
    # @Support Go style comments, IMPL_GO_2, impl, [FE_GO]
    CommentType.go: ["//", "/*"],
}
ESCAPE = "\\"

# Default C/C++ standard for the standalone/defines parse path when no
# compile_commands.json entry supplies one.
DEFAULT_CPP_STD = "c++17"


class CommentCategory(str, Enum):  # noqa: UP042  # StrEnum changes str(member), which reaches CLI warnings and error messages
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
    def get_schema(cls, name: str) -> dict[str, Any] | None:
        _field = next(_field for _field in fields(cls) if _field.name is name)
        if _field.metadata and "schema" in _field.metadata:
            return cast(dict[str, Any], _field.metadata["schema"])
        return None

    def check_schema(self) -> list[str]:
        errors = []
        for _field_name in self.field_names():
            schema = self.get_schema(_field_name)
            value = getattr(self, _field_name)
            try:
                # jsonschema's stubs type `schema` as `bool | Mapping`, but
                # `get_schema` returns an optional dict
                validate(
                    instance=value,
                    schema=schema,  # ty: ignore[invalid-argument-type]
                )
            except ValidationError as e:
                errors.append(
                    f"Schema validation error in field '{_field_name}': {e.message}"
                )
        return errors


class MultilineNeedsConfigType(TypedDict, total=False):
    start_sequence: str
    end_sequence: str
    default_markup: str
    markups: dict[str, str]


DEFAULT_MARKUPS: dict[str, str] = {"rst": ".rst", "md": ".md"}
"""The default ``markups`` table: markup tag -> the ``doctype`` suffix of the need."""


@dataclass
class MultilineNeedsConfig:
    """The markers and markups of multi-line needs (``[analyse.multiline_needs]``)."""

    @classmethod
    def field_names(cls) -> set[str]:
        return {item.name for item in fields(cls)}

    start_sequence: str = field(
        default="@need", metadata={"schema": {"type": "string", "minLength": 1}}
    )
    """The word that opens a multi-line need, at the start of its line."""
    end_sequence: str = field(
        default="@endneed", metadata={"schema": {"type": "string", "minLength": 1}}
    )
    """The word that closes a multi-line need, alone on its line."""
    default_markup: str = field(
        default="rst", metadata={"schema": {"type": "string", "minLength": 1}}
    )
    """The markup tag of a block whose open line names none; a key of ``markups``."""
    markups: dict[str, str] = field(
        default_factory=lambda: dict(DEFAULT_MARKUPS),
        metadata={
            "schema": {
                "type": "object",
                "additionalProperties": {"type": "string"},
                "minProperties": 1,
            }
        },
    )
    """Markup tag -> the ``doctype`` suffix the need's content is parsed with. Not
    checked against any parser: the consumer decides what it can parse."""

    @classmethod
    def get_schema(cls, name: str) -> dict[str, Any] | None:
        _field = next(_field for _field in fields(cls) if _field.name is name)
        if _field.metadata and "schema" in _field.metadata:
            return cast(dict[str, Any], _field.metadata["schema"])
        return None

    def check_schema(self) -> list[str]:
        errors = []
        for _field_name in self.field_names():
            schema = self.get_schema(_field_name)
            value = getattr(self, _field_name)
            try:
                # jsonschema's stubs type `schema` as `bool | Mapping`, but
                # `get_schema` returns an optional dict
                validate(
                    instance=value,
                    schema=schema,  # ty: ignore[invalid-argument-type]
                )
            except ValidationError as e:
                errors.append(
                    f"Schema validation error in field '{_field_name}': {e.message}"
                )
        return errors

    def check_fields_configuration(self) -> list[str]:
        errors = self.check_schema()
        if self.start_sequence == self.end_sequence:
            errors.append("start_sequence and end_sequence cannot be the same.")
        if isinstance(self.markups, dict) and self.default_markup not in self.markups:
            errors.append(
                f"default_markup {self.default_markup!r} is not a key of markups "
                f"({', '.join(repr(tag) for tag in sorted(self.markups))})."
            )
        return errors


@dataclass
class PreprocessorConfig:
    """Opt-in libclang engine config. Presence => libclang engine for C/C++."""

    compile_commands: Path | None = field(
        default=None, metadata={"schema": {"type": ["string", "null"]}}
    )
    """Explicit path to compile_commands.json. If None, walk-up auto-discovery."""

    defines: list[str] = field(
        default_factory=list,
        metadata={"schema": {"type": "array", "items": {"type": "string"}}},
    )
    """Fallback -D defines applied globally when no compile_commands.json applies."""

    includes: list[Path] = field(
        default_factory=list,
        metadata={"schema": {"type": "array", "items": {"type": "string"}}},
    )
    """Fallback -I include dirs for the defines path."""

    std: str = field(
        default=DEFAULT_CPP_STD,
        metadata={"schema": {"type": "string"}},
    )
    """C/C++ standard for the standalone/defines parse path (e.g. ``c++17``,
    ``c++20``, ``c11``); libclang pins ``-x`` to match it. Files resolved from a
    ``compile_commands.json`` entry use that entry's own ``-std`` instead."""


def anchor_preproc_paths(preproc: PreprocessorConfig, base: Path) -> PreprocessorConfig:
    """Resolve a preprocessor config's ``compile_commands`` and ``includes``
    against ``base`` (the config file's directory), so a relative path resolves
    against the TOML file rather than the process CWD — matching ``src_dir`` /
    ``git_root``. An absolute path is not anchored, but it is resolved too
    (symlinks followed, ``..`` folded), like every other path here.
    """
    return replace(
        preproc,
        compile_commands=(
            anchor(preproc.compile_commands, base).resolve()
            if preproc.compile_commands is not None
            else None
        ),
        includes=[anchor(inc, base).resolve() for inc in preproc.includes],
    )


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
    def __setattr__(self, name: str, value: Any) -> None:
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
                    _field[_default] = field_default[
                        _default
                    ]  # dynamically assign keys

    @classmethod
    def get_required_fields(cls, name: str) -> list[str] | None:
        _field = next(_field for _field in fields(cls) if _field.name is name)
        if _field.metadata:
            return cast(list[str], _field.metadata["required_fields"])
        return None

    @classmethod
    def get_schema(cls, name: str) -> dict[str, Any] | None:
        _field = next(_field for _field in fields(cls) if _field.name is name)
        if _field.metadata and "schema" in _field.metadata:
            return cast(dict[str, Any], _field.metadata["schema"])
        return None

    def check_schema(self) -> list[str]:
        errors = []
        for _field_name in self.field_names():
            schema = self.get_schema(_field_name)
            value = getattr(self, _field_name)
            try:
                validate(
                    instance=value,
                    schema=schema,  # ty: ignore[invalid-argument-type]
                )  # validate has no type specified
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

    def check_fields_default_order(self) -> list[str]:
        errors = []
        seen_default = False
        first_default_field = ""
        for _field in self.needs_fields:
            has_default = _field.get("default") is not None
            if has_default and not seen_default:
                seen_default = True
                first_default_field = _field["name"]
            elif not has_default and seen_default:
                errors.append(
                    f"Field '{_field['name']}' without a default follows "
                    f"field '{first_default_field}' which has a default. "
                    f"Fields without defaults must be defined before fields with defaults."
                )
        return errors

    def check_fields_configuration(self) -> list[str]:
        return (
            self.check_schema()
            + self.check_required_fields()
            + self.check_fields_mutually_exclusive()
            + self.check_fields_default_order()
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
    get_multiline_needs: bool
    outdir: str
    git_root: str
    need_id_refs: NeedIdRefsConfigType
    multiline_needs: MultilineNeedsConfigType
    oneline_comment_style: OneLineCommentStyleType
    preprocessor: dict[str, object]


class SourceAnalyseConfigType(TypedDict, total=False):
    """Define typing for its API configuration."""

    src_files: list[Path]
    src_dir: Path
    comment_type: CommentType
    get_need_id_refs: bool
    get_oneline_needs: bool
    get_multiline_needs: bool
    git_root: Path | None
    need_id_refs_config: NeedIdRefsConfig
    multiline_needs_config: MultilineNeedsConfig
    oneline_comment_style: OneLineCommentStyle
    preprocessor: PreprocessorConfig | None


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

    get_multiline_needs: bool = field(
        default=False, metadata={"schema": {"type": "boolean"}}
    )
    """Whether to extract multi-line needs (``@need`` … ``@endneed``) from comments"""

    git_root: Path | None = field(
        default=None, metadata={"schema": {"type": ["string", "null"]}}
    )
    """Explicit path to the Git repository root. If not set, it will be auto-detected
    by traversing parent directories. Useful for Bazel builds or deeply nested configs."""

    need_id_refs_config: NeedIdRefsConfig = field(default_factory=NeedIdRefsConfig)
    """Configuration for extracting need id references from comments."""

    multiline_needs_config: MultilineNeedsConfig = field(
        default_factory=MultilineNeedsConfig
    )
    """Configuration for extracting multi-line needs from comments."""

    oneline_comment_style: OneLineCommentStyle = field(
        default_factory=OneLineCommentStyle
    )
    """Configuration for extracting oneline needs from comments."""

    preprocessor: PreprocessorConfig | None = field(default=None)
    """Opt-in libclang preprocessor engine. None => tree-sitter (default).

    No flat ``metadata["schema"]`` here: this is a nested dataclass, like the
    sibling ``need_id_refs_config`` / ``multiline_needs_config`` /
    ``oneline_comment_style`` fields. ``check_schema`` only validates fields that
    declare a flat schema; giving this field one made it validate the constructed
    ``PreprocessorConfig`` instance against JSON type ``object`` and fail at
    ``config-inited``. Its structure is enforced by ``convert_analyse_config``.
    """

    @classmethod
    def get_schema(cls, name: str) -> dict[str, Any] | None:
        _field = next(_field for _field in fields(cls) if _field.name is name)
        if _field.metadata and "schema" in _field.metadata:
            return cast(dict[str, Any], _field.metadata["schema"])
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
                value: list[str] = [
                    str(src_file) for src_file in value
                ]  # only for value adaptation
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
        # equality only: the default one-line start ``@`` is a PREFIX of ``@need``, and
        # what keeps the two apart is that a block's lines are hidden from the one-line
        # parser, not this check
        for marker in (
            self.multiline_needs_config.start_sequence,
            self.multiline_needs_config.end_sequence,
        ):
            if marker in markers:
                errors.add(f"Marker {marker} is defined multiple times")
            else:
                markers.add(marker)

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
        if self.get_multiline_needs:
            multiline_errors = self.multiline_needs_config.check_fields_configuration()
            if multiline_errors:
                errors.appendleft("MultilineNeeds configuration errors:")
                errors.extend(multiline_errors)
        analyse_errors = self.check_markers_mutually_exclusive() + self.check_schema()
        if analyse_errors:
            errors.appendleft("analyse configuration errors:")
            errors.extend(analyse_errors)
        return list(errors)


# Shared ubCode project file, which other useblocks tools (sphinx-needs,
# ubCode checker, ...) read as well, so all tools see the same projects.
DEFAULT_CONFIG_TOML: str = "ubproject.toml"

DEFAULT_REF_URL_FIELD: str = "code_url"
"""The need field ``@need-ids:`` references are attached to, unless a project's
``ref_url_field`` names another (ubCode's key and default; ``""`` disables the attach)."""

#: The table of the TOML file that both readers, the Sphinx extension and the CLI,
#: take their configuration from.
CODELINKS_TABLE: str = "codelinks"


def load_codelinks_table(path: Path) -> dict[str, object] | None:
    """Parse *path* and return its ``[codelinks]`` table, through ub-project.

    The values are returned RAW: relative paths are anchored where they are used
    (the Sphinx extension anchors at ``confdir / Path(config_from_toml).parent``,
    unresolved), never here.

    :param path: The TOML file.
    :return: The table, or ``None`` when the file has no ``codelinks`` key.
    :raises ub_project.ProjectConfigError: If the file cannot be read, is not UTF-8
        or not valid TOML, or if ``codelinks`` is not a table.
    :raises RecursionError: For a pathologically nested file, which ``load_toml``
        does not wrap -- why both callers also catch ``Exception``.
    """
    return select_table(load_toml(path), CODELINKS_TABLE, source=path)


class CodeLinksProjectConfigType(TypedDict, total=False):
    """TypedDict defining the configuration structure for individual SrcTrace projects.

    Contains both user-provided configuration:
    - source_discover
    - remote_url_pattern
    - ref_url_field
    - analyse
    and runtime-generated configuration objects
    - source_discover_config
    - analyse_config
    """

    source_discover: SourceDiscoverSectionConfigType
    remote_url_pattern: str
    ref_url_field: str
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
        src_trace_projects = getattr(sphinx_config, "src_trace_projects", None)
        if isinstance(src_trace_projects, dict):
            generate_project_configs(src_trace_projects)
        super().__setattr__(obj, "_sphinx_config", sphinx_config)
        return obj

    def __getattribute__(self, name: str) -> Any:
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

    def __setattr__(self, name: str, value: Any) -> None:
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
    def get_schema(cls, name: str) -> dict[str, Any] | None:
        """Get the schema for a config item."""
        _field = next(field for field in fields(cls) if field.name is name)
        if _field.metadata and "schema" in _field.metadata:
            return _field.metadata["schema"]
        return None

    config_from_toml: str | None = field(
        default=DEFAULT_CONFIG_TOML,
        metadata={
            "rebuild": "env",
            "types": (str, type(None)),
            "schema": {
                "type": ["string", "null"],
                "examples": [DEFAULT_CONFIG_TOML, None],
            },
        },
    )
    """Path to a TOML file to load configuration from.

    Defaults to ``ubproject.toml`` next to :file:`conf.py`. The default is the
    value ``ubproject.toml`` exactly -- left unset, or written in conf.py as that
    string: missing, or without a ``[codelinks]`` table, it is silently ignored.
    Any other value, ``./ubproject.toml`` included, is an explicit file and warns
    in both cases. A file that exists but cannot be read or parsed warns
    (``codelinks.config``) either way, as any configured file did at 1.4.0.
    """

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
                        "ref_url_field": {},
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

        ref_url_field = project_config.get("ref_url_field", DEFAULT_REF_URL_FIELD)
        if not isinstance(ref_url_field, str):
            project_errors.append("ref_url_field must be a string")
        elif ref_url_field and ref_url_field in _url_fields(config):
            project_errors.append(
                f"ref_url_field {ref_url_field!r} must differ from local_url_field "
                "and remote_url_field"
            )

        if analyse_errors or src_discover_errors or project_errors:
            errors.append(f"Project '{project_name}' has the following errors:")
            errors.extend(analyse_errors)
            errors.extend(src_discover_errors)
            errors.extend(project_errors)

    return errors


def config_base_dir(confdir: str | Path, config: CodeLinksConfig) -> Path:
    """The directory a project's relative paths are anchored at.

    The configuration file's directory when ``src_trace_config_from_toml`` names one
    (itself anchored at ``confdir``), else ``confdir``: ``src_dir``, ``git_root`` and
    the preprocessor paths all resolve against it.
    """
    base = Path(confdir)
    if config.config_from_toml:
        base = anchor(Path(config.config_from_toml).parent, base)
    return base


def locate_src_dir(
    confdir: str | Path,
    config: CodeLinksConfig,
    discover_config: SourceDiscoverConfig,
) -> Path:
    """A project's source directory, anchored (see :func:`config_base_dir`) and resolved."""
    return anchor(discover_config.src_dir, config_base_dir(confdir, config)).resolve()


def git_root_problem(git_root: Path, src_dir: Path) -> str | None:
    """Why a configured ``git_root`` cannot be a project's git root, or ``None``.

    Every source path is relative to the git root, so it must be ``src_dir`` or a
    directory above it (#2062). Both paths anchored and resolved by the caller: the
    Sphinx extension (``project_analysis.configured_git_root``) and ``codelinks
    analyse`` alike, each treating a value with a problem as unset.
    """
    try:
        if not git_root.exists():
            return f"git_root {git_root.as_posix()} does not exist"
        if not git_root.is_dir():
            return f"git_root {git_root.as_posix()} is not a directory"
    except OSError:
        return f"git_root {git_root.as_posix()} cannot be read"
    if not src_dir.is_relative_to(git_root):
        return (
            f"git_root {git_root.as_posix()} does not contain src_dir "
            f"{src_dir.as_posix()}"
        )
    return None


def git_root_warning(project: str, problem: str) -> str:
    """The one warning text for a project's ignored ``git_root`` (``codelinks.git_root``)."""
    return (
        f"project {project!r}: {problem}; it is ignored, and the repository root is "
        "detected from src_dir instead"
    )


def remote_url_pattern_warnings(config: CodeLinksConfig) -> list[str]:
    """Why a project's remote URL pattern will not render as one link, if it will not.

    The ``remote-url`` value is the pattern filled in, and Sphinx-Needs splits every
    string-linked value on ``,`` and ``;`` before turning the parts into links. A
    pattern containing either -- gitweb's ``?p=repo.git;a=blob;f={path}`` is the
    classic -- therefore renders as several links, none of them right.
    """
    if not config.set_remote_url or not isinstance(config.projects, dict):
        return []
    warnings = []
    for name, project_config in config.projects.items():
        if not isinstance(project_config, dict):
            continue
        pattern = project_config.get("remote_url_pattern")
        if isinstance(pattern, str) and ("," in pattern or ";" in pattern):
            warnings.append(
                f"Project {name!r}: remote_url_pattern {pattern!r} contains ',' or "
                "';'. Sphinx-Needs splits string-linked values on ',' and ';', so this "
                "pattern's links will not render as one link."
            )
    return warnings


def _url_fields(config: CodeLinksConfig) -> set[str]:
    """The names of the URL fields the extension registers (when switched on)."""
    names: set[str] = set()
    if config.set_local_url:
        names.add(config.local_url_field)
    if config.set_remote_url:
        names.add(config.remote_url_field)
    return names


def need_id_refs_field(
    config: CodeLinksConfig, project_config: CodeLinksProjectConfigType
) -> str | None:
    """The field a project's ``@need-ids:`` references are attached to, or ``None``.

    ubCode's gate: URLs are on (local or remote), references are extracted, the project
    has at least one marker, and its ``ref_url_field`` is not ``""``. A field that is not
    a string, or that is one of the URL fields, is a configuration error reported by
    :func:`check_project_configuration`, and attaches nothing.
    """
    if not (config.set_remote_url or config.set_local_url):
        return None
    field_name = project_config.get("ref_url_field", DEFAULT_REF_URL_FIELD)
    if not isinstance(field_name, str) or not field_name:
        return None
    if field_name in _url_fields(config):
        return None
    analyse_config = project_config.get("analyse_config")
    if analyse_config is None or not analyse_config.get_need_id_refs:
        return None
    if not analyse_config.need_id_refs_config.markers:
        return None
    return field_name


def need_id_refs_fields(config: CodeLinksConfig) -> dict[str, str]:
    """Each project whose references are attached, mapped to its field."""
    projects = config.projects
    if not isinstance(projects, dict):
        return {}
    fields_by_project: dict[str, str] = {}
    for name, project_config in projects.items():
        if not isinstance(project_config, dict):
            continue
        field_name = need_id_refs_field(config, project_config)
        if field_name is not None:
            fields_by_project[name] = field_name
    return fields_by_project


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
        src_discover_config = SourceDiscoverConfig(**src_discover_dict)  # ty: ignore[invalid-argument-type]
    else:
        src_discover_config = SourceDiscoverConfig()

    return src_discover_config


def _validate_preprocessor_dict(preproc: dict[str, object]) -> None:
    """Validate the schema-less ``[preprocessor]`` TOML section.

    The section has no ``TypedDict``, so a mistyped scalar would otherwise be
    coerced into garbage instead of reported: e.g. ``defines = "X"`` (a bare
    string) becomes ``list("X") == ["X"]`` — or worse, ``defines = "cpp17"``
    becomes ``["c", "p", "p", "1", "7"]`` → five bogus ``-D`` flags. Fail loud.

    :param preproc: the raw ``[preprocessor]`` mapping from TOML.
    :raises TypeError: if a key has the wrong type.
    """
    for key in ("defines", "includes"):
        value = preproc.get(key)
        if value is not None and (
            not isinstance(value, list) or not all(isinstance(x, str) for x in value)
        ):
            raise TypeError(
                f"[preprocessor] {key} must be a list of strings, "
                f"got {type(value).__name__}: {value!r}"
            )
    for key in ("compile_commands", "std"):
        value = preproc.get(key)
        if value is not None and not isinstance(value, str):
            raise TypeError(
                f"[preprocessor] {key} must be a string, "
                f"got {type(value).__name__}: {value!r}"
            )


REMOVED_ANALYSE_KEYS: dict[str, str] = {
    "get_rst": "get_multiline_needs",
    "marked_rst": "[analyse.multiline_needs]",
}
"""``[analyse]`` keys of the removed marked-rst blocks -> what replaces each."""


def check_removed_analyse_keys(config_dict: AnalyseSectionConfigType) -> None:
    """Refuse the keys of the removed ``@rst`` blocks with one message naming the cure.

    Any other unknown key keeps failing as before, in the dataclass constructor.

    :raises TypeError: through the channel every other configuration error of the
        section takes (``typer.BadParameter`` in the CLI, the ``config-inited`` error of
        a Sphinx build).
    """
    found = [key for key in REMOVED_ANALYSE_KEYS if key in config_dict]
    if not found:
        return
    removed = " and ".join(
        f"'{key}'" if key == "get_rst" else f"'[analyse.{key}]'" for key in found
    )
    replacements = " and ".join(REMOVED_ANALYSE_KEYS[key] for key in found)
    raise TypeError(
        f"analyse: {removed} {'is' if len(found) == 1 else 'are'} no longer supported: "
        "the marked-rst blocks were replaced by multi-line needs (the @need and "
        f"@endneed markers); use {replacements} instead"
    )


def convert_analyse_config(
    config_dict: AnalyseSectionConfigType | None,
    src_discover: SourceDiscover | None = None,
) -> SourceAnalyseConfig:
    analyse_config_dict: SourceAnalyseConfigType = {}
    if config_dict:
        check_removed_analyse_keys(config_dict)
        for k, v in config_dict.items():
            if k not in {
                "online_comment_style",
                "need_id_refs",
                "multiline_needs",
                "preprocessor",
            }:
                # Convert string paths to Path objects
                if k in {"src_dir", "git_root"} and isinstance(v, str):
                    analyse_config_dict[k] = Path(v)
                else:
                    # dynamical assignment
                    analyse_config_dict[k] = v  # ty: ignore[invalid-key]

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

        # Get multiline_needs configuration
        multiline_needs_config_dict: MultilineNeedsConfigType | None = config_dict.get(
            "multiline_needs"
        )
        multiline_needs_config = convert_multiline_needs_config(
            multiline_needs_config_dict
        )

        analyse_config_dict["need_id_refs_config"] = need_id_refs_config
        analyse_config_dict["multiline_needs_config"] = multiline_needs_config
        analyse_config_dict["oneline_comment_style"] = oneline_comment_style

        preprocessor_dict = config_dict.get("preprocessor")
        if preprocessor_dict is not None:
            # The preprocessor section has no TypedDict; its values are dynamic
            # TOML (typed ``object``), so validate the shapes up front -- a mistyped
            # scalar would otherwise coerce into garbage flags.
            _validate_preprocessor_dict(preprocessor_dict)
            analyse_config_dict["preprocessor"] = PreprocessorConfig(
                compile_commands=(
                    Path(str(preprocessor_dict["compile_commands"]))
                    if preprocessor_dict.get("compile_commands")
                    else None
                ),
                defines=list(preprocessor_dict.get("defines", [])),  # ty: ignore[invalid-argument-type]
                includes=[Path(str(p)) for p in preprocessor_dict.get("includes", [])],  # ty: ignore[not-iterable]
                std=str(preprocessor_dict.get("std", DEFAULT_CPP_STD)),
            )

    if src_discover:
        analyse_config_dict["src_files"] = src_discover.source_paths
        analyse_config_dict["src_dir"] = src_discover.src_discover_config.src_dir
        try:
            analyse_config_dict["comment_type"] = CommentType(
                src_discover.src_discover_config.comment_type
            )
        except ValueError:
            # If invalid comment_type, keep the string value
            # Validation will catch this error later
            comment_type_str: str = src_discover.src_discover_config.comment_type
            analyse_config_dict["comment_type"] = comment_type_str  # ty: ignore[invalid-assignment]

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


def convert_multiline_needs_config(
    config_dict: MultilineNeedsConfigType | None,
) -> MultilineNeedsConfig:
    if not config_dict:
        return MultilineNeedsConfig()
    try:
        return MultilineNeedsConfig(**config_dict)
    except TypeError as e:
        raise TypeError(f"Invalid multiline_needs configuration: {e}") from e


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
        # Copy comment_type from source_discover_config to analyse_config
        try:
            analyse_config.comment_type = CommentType(
                source_discover_config.comment_type
            )
        except ValueError:
            # If invalid comment_type, keep the string value
            # Validation will catch this error later
            analyse_config.comment_type = source_discover_config.comment_type  # ty: ignore[invalid-assignment]
        project_config["analyse_config"] = analyse_config
