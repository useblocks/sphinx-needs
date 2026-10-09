from dataclasses import dataclass, field, fields
from enum import Enum
from pathlib import Path
from typing import Any, Required, TypedDict, cast

from jsonschema import ValidationError, validate

COMMENT_FILETYPE = {
    "cpp": ["c", "ci", "cpp", "cc", "cxx", "h", "hpp", "hxx", "hh", "ihl"],
    "python": ["py"],
    "cs": ["cs"],
    # ".mts"/".cts" are TypeScript's own ESM/CJS module variants. ".js"/".jsx"/
    # ".mjs"/".cjs" are JavaScript. All of these share the "ts" comment type:
    # comment syntax is identical across the family, and the analyse stage
    # picks the actual tree-sitter grammar per file from the suffix (the plain
    # TypeScript grammar for ".ts"/".mts"/".cts", the TSX grammar for
    # everything else — see utils.ts_grammar_key), so no separate
    # comment_type value is needed here.
    "ts": ["ts", "tsx", "mts", "cts", "js", "jsx", "mjs", "cjs"],
    "yaml": ["yml", "yaml"],
    "rust": ["rs"],
    "go": ["go"],
    "jsonc": ["jsonc", "json"],
    # Bash uses `#` line comments; zsh and ksh share the same comment syntax and
    # are scanned with the bash grammar. Fish is intentionally excluded: it is
    # not POSIX-compatible and no tree-sitter-fish distribution is published on
    # PyPI, so it cannot be wired in here. Track fish separately if a PyPI
    # grammar becomes available.
    "bash": ["sh", "bash", "zsh", "ksh"],
}


# Default ``exclude`` glob patterns applied to ``ts`` (TypeScript/JavaScript
# family) projects when their configuration does not set ``exclude``
# explicitly.
#
# ``src_dir`` defaults to ``"./"`` and the ``ts`` comment type claims ``.js``/
# ``.jsx``/``.mjs``/``.cjs`` in addition to TypeScript's own extensions, so a
# checked-in ``tsc``/bundler output directory (``dist/``, ``build/``, ...) is
# otherwise scanned as source alongside the ``.ts`` it was generated from,
# producing duplicate need ids for the same marker. These directory names are
# common generated-output or dependency locations across the JS/TS ecosystem,
# so excluding them by default avoids that duplication for most projects out
# of the box.
#
# ``**/lib/**`` is deliberately NOT in this list: it is ambiguous even within
# the JS/TS ecosystem, where many packages use ``lib/`` for hand-written
# source rather than as a ``tsc`` ``outDir``. Projects whose ``outDir`` is
# ``lib`` should add ``"**/lib/**"`` to their own ``exclude`` explicitly.
#
# This default is applied only for ``comment_type == "ts"``. Every other
# ``comment_type`` (``cpp``, ``python``, ``rust``, ``go``, ``yaml``, ``jsonc``,
# ``bash``, ``cs``, ...) defaults ``exclude`` to ``[]`` — unchanged from
# before this default existed. ``cpp`` projects in particular very commonly
# keep hand-written library source under ``lib/``, so a directory-name-based
# default that isn't scoped to the language family would silently drop
# markers there.
#
# Setting ``exclude`` explicitly in a project's configuration replaces this
# default outright (it is not merged) — including setting it to ``[]`` to
# scan everything.
TS_DEFAULT_EXCLUDE = [
    "**/node_modules/**",
    "**/dist/**",
    "**/build/**",
    "**/out/**",
    "**/coverage/**",
]


class CommentType(str, Enum):  # noqa: UP042  # StrEnum changes str(member), which reaches CLI warnings and error messages
    python = "python"
    cpp = "cpp"
    cs = "cs"
    # @Support TypeScript style comments, IMPL_TS_1, impl, [FE_TS]
    ts = "ts"
    yaml = "yaml"
    # @Support Rust style comments, IMPL_RUST_1, impl, [FE_RUST]
    rust = "rust"
    # @Support Go style comments, IMPL_GO_1, impl, [FE_GO]
    go = "go"
    # @Support JSONC style comments, IMPL_JSONC_1, impl, [FE_JSONC]
    jsonc = "jsonc"
    # @Support Bash style comments, IMPL_BASH_1, impl, [FE_BASH]
    bash = "bash"


def default_exclude_for_comment_type(comment_type: str) -> list[str]:
    """Resolve the default ``exclude`` patterns for a given ``comment_type``.

    Only the ``ts`` (TypeScript/JavaScript) family gets a non-empty default —
    see ``TS_DEFAULT_EXCLUDE`` for why. Every other ``comment_type`` defaults
    to ``[]``, i.e. no default exclusion at all, matching the behavior before
    a default was ever introduced.
    """
    if comment_type == CommentType.ts:
        return list(TS_DEFAULT_EXCLUDE)
    return []


class SourceDiscoverSectionConfigType(TypedDict, total=False):
    """Define typing for loading configuration from TOML files"""

    src_dir: Required[str]
    exclude: list[str]
    include: list[str]
    gitignore: bool
    follow_links: bool
    comment_type: CommentType


class SourceDiscoverConfigType(TypedDict, total=False):
    """Define typing for its API configuration"""

    src_dir: Required[Path]
    exclude: list[str]
    include: list[str]
    gitignore: bool
    follow_links: bool
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

    exclude: list[str] | None = field(
        default=None,
        metadata={"schema": {"type": "array", "items": {"type": "string"}}},
    )
    """The glob pattern to exclude files.

    Leave unset (``None``) to get the ``comment_type``-derived default
    resolved in ``__post_init__`` (see ``default_exclude_for_comment_type``):
    ``TS_DEFAULT_EXCLUDE`` for ``comment_type == "ts"``, ``[]`` for every
    other ``comment_type``. Set this explicitly — including to ``[]`` — to
    replace that default outright; it is never merged with it.
    """

    include: list[str] = field(
        default_factory=list,
        metadata={"schema": {"type": "array", "items": {"type": "string"}}},
    )
    """The glob pattern to include files."""

    gitignore: bool = field(default=True, metadata={"schema": {"type": "boolean"}})
    """Whether to respect .gitignore to exclude files."""

    follow_links: bool = field(default=False, metadata={"schema": {"type": "boolean"}})
    """Whether to follow symbolic links during file discovery."""

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

    def __post_init__(self) -> None:
        # ``None`` means "the user didn't set exclude" (a dataclass field
        # default can't otherwise be told apart from an explicit ``[]``) —
        # resolve it to the comment_type-derived default. An explicit value,
        # including ``[]``, is left untouched.
        if self.exclude is None:
            self.exclude = default_exclude_for_comment_type(self.comment_type)

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
            if isinstance(value, Path):  # adapt to json schema restriction
                value = str(value)
            try:
                validate(
                    instance=value,
                    schema=schema,  # ty: ignore[invalid-argument-type]
                )  # validate has no type specified
            except ValidationError as e:
                errors.append(
                    f"Schema validation error in field '{_field_name}': {e.message}"
                )
        return errors
