from collections import deque
from collections.abc import Callable
from enum import Enum
from os import linesep
from pathlib import Path
import tomllib
from typing import Annotated, cast

import typer

from sphinx_codelinks.analyse.analyse import SourceAnalyse
from sphinx_codelinks.analyse.config import (
    COMMENT_FILETYPE,
    CommentType,
    MarkedRstConfig,
    MarkedRstConfigType,
    NeedIdRefsConfig,
    NeedIdRefsConfigType,
    OneLineCommentStyle,
    OneLineCommentStyleType,
    SourceAnalyseConfig,
    SourceAnalyseConfigFileType,
    SourceAnalyseConfigType,
    SrcDiscoverConfigType4Analyse,
)
from sphinx_codelinks.source_discover.config import (
    SourceDiscoverConfig,
    SourceDiscoverConfigType,
)
from sphinx_codelinks.source_discover.source_discover import SourceDiscover
from sphinx_codelinks.sphinx_extension.config import SrcTraceProjectConfigFileType

app = typer.Typer(
    no_args_is_help=True, context_settings={"help_option_names": ["-h", "--help"]}
)


@app.command(no_args_is_help=True)
def analyse(
    config: Annotated[
        Path,
        typer.Argument(
            help="The toml config file",
            show_default=False,
            dir_okay=False,
            file_okay=True,
            exists=True,
        ),
    ],
    outdir: Annotated[
        Path | None,
        typer.Option(
            "--outdir",
            "-o",
            help="The output directory. When given, this overwrites the config's outdir",
            show_default=True,
            dir_okay=True,
            file_okay=False,
            exists=True,
        ),
    ] = None,
) -> None:
    """Analyse marked content in source code."""
    data = load_src_analyse_config_from_toml(config)

    errors: deque[str] = deque()

    # Get source_discover configuration
    src_discover_4_analyse_dict = cast(
        SrcDiscoverConfigType4Analyse | None, data.get("source_discover")
    )
    src_discover_config = cast(
        SourceDiscoverConfig,
        convert_dict_2_config(src_discover_4_analyse_dict, ConfigType.SourceDiscover),
    )

    src_discover_errors = src_discover_config.check_schema()

    if src_discover_errors:
        errors.appendleft("Invalid source discovery configuration:")
        errors.extend(src_discover_errors)
    if errors:
        raise typer.BadParameter(f"{linesep.join(errors)}")

    # src dir shall be relevant to the config file's location
    src_discover_config.src_dir = (
        config.parent / src_discover_config.src_dir
    ).resolve()

    src_discover = SourceDiscover(src_discover_config)
    # Get oneline_comment_style configuration
    oneline_comment_style_dict: OneLineCommentStyleType | None = data.get(
        "oneline_comment_style"
    )
    oneline_comment_style: OneLineCommentStyle = cast(
        OneLineCommentStyle,
        convert_dict_2_config(
            oneline_comment_style_dict, ConfigType.OneLineCommentStyle
        ),
    )

    oneline_errors = oneline_comment_style.check_fields_configuration()
    if oneline_errors:
        errors.appendleft("Invalid oneline comment style configuration:")
        errors.extend(oneline_errors)

    # Get need_id_refs configuration
    need_id_refs_config_dict: NeedIdRefsConfigType | None = data.get("need_id_refs")
    need_id_refs_config = cast(
        NeedIdRefsConfig,
        convert_dict_2_config(need_id_refs_config_dict, ConfigType.NeedIdRefsConfig),
    )

    # Get marked_rst configuration
    marked_rst_config_dict: MarkedRstConfigType | None = data.get("marked_rst")
    marked_rst_config = cast(
        MarkedRstConfig,
        convert_dict_2_config(marked_rst_config_dict, ConfigType.MarkedRstCofig),
    )

    non_root_configs = {
        "source_discover",
        "oneline_comment_style",
        "need_id_refs",
        "marked_rst",
    }

    # Get root config
    src_analyse_dict: SourceAnalyseConfigType = cast(
        SourceAnalyseConfigType,
        {key: value for key, value in data.items() if key not in non_root_configs},
    )
    src_analyse_dict["src_files"] = src_discover.source_paths
    src_analyse_dict["src_dir"] = Path(src_discover.src_discover_config.src_dir)
    src_analyse_dict["need_id_refs_config"] = need_id_refs_config
    src_analyse_dict["marked_rst_config"] = marked_rst_config
    src_analyse_dict["oneline_comment_style"] = oneline_comment_style
    if outdir:
        src_analyse_dict["outdir"] = outdir

    src_analyse_config = SourceAnalyseConfig(**src_analyse_dict)

    analyse_errors = src_analyse_config.check_fields_configuration()
    errors.extend(analyse_errors)
    if errors:
        raise typer.BadParameter(f"{linesep.join(errors)}")

    src_analyse = SourceAnalyse(src_analyse_config)
    src_analyse.run()


@app.command(no_args_is_help=True)
def discover(
    src_dir: Annotated[
        Path,
        typer.Argument(
            ...,
            help="Root directory for discovery",
            show_default=False,
            dir_okay=True,
            file_okay=False,
            exists=True,
            resolve_path=True,
        ),
    ],
    exclude: Annotated[
        list[str],
        typer.Option(
            "--excludes",
            "-e",
            help="Glob patterns to be excluded.",
        ),
    ] = [],  # noqa: B006   # to show the default value on CLI
    include: Annotated[
        list[str],
        typer.Option(
            "--includes",
            "-i",
            help="Glob patterns to be included.",
        ),
    ] = [],  # noqa: B006   # to show the default value on CLI
    gitignore: Annotated[
        bool,
        typer.Option(
            help="Respect .gitignore in the given directory. Nested .gitignore Not supported"
        ),
    ] = True,
    comment_type: Annotated[
        CommentType,
        typer.Option(
            "--comment-type",
            "-c",
            help="The relevant file extensions which use the specified the comment type will be discovered.",
        ),
    ] = CommentType.cpp,
) -> None:
    """Discover the filepaths from the given root directory."""

    src_discover_dict: SourceDiscoverConfigType = {
        "src_dir": src_dir,
        "exclude": exclude,
        "include": include,
        "gitignore": gitignore,
        "comment_type": comment_type,
    }

    src_discover_config = SourceDiscoverConfig(**src_discover_dict)

    errors = src_discover_config.check_schema()
    if errors:
        raise typer.BadParameter(f"{linesep.join(errors)}")

    source_discover = SourceDiscover(src_discover_config)
    typer.echo(f"{len(source_discover.source_paths)} files discovered")
    for file_path in source_discover.source_paths:
        typer.echo(file_path)


def load_config_from_toml(
    toml_file: Path, project: str | None = None
) -> SrcTraceProjectConfigFileType:
    try:
        with toml_file.open("rb") as f:
            toml_data = tomllib.load(f)

        if project:
            toml_data = toml_data["src_trace"]["projects"][project]

    except Exception as e:
        raise Exception(
            f"Failed to load source tracing configuration from {toml_file}"
        ) from e

    return cast(SrcTraceProjectConfigFileType, toml_data)


def load_src_analyse_config_from_toml(toml_file: Path) -> SourceAnalyseConfigFileType:
    try:
        with toml_file.open("rb") as f:
            toml_data = tomllib.load(f)

    except Exception as e:
        raise Exception(
            f"Failed to load Source analyse configuration from {toml_file}"
        ) from e

    return cast(SourceAnalyseConfigFileType, toml_data)


class ConfigType(str, Enum):
    SourceDiscover = "source_discover"
    OneLineCommentStyle = "oneline_comment_style"
    NeedIdRefsConfig = "need_id_refs"
    MarkedRstCofig = "marked_rst"
    AnalzerConfig = "source_analyse"


def convert_dict_2_config(
    config_dict: SrcDiscoverConfigType4Analyse
    | OneLineCommentStyleType
    | NeedIdRefsConfigType
    | MarkedRstConfigType
    | None,
    config_type: ConfigType,
) -> SourceDiscoverConfig | OneLineCommentStyle | NeedIdRefsConfig | MarkedRstConfig:
    func_map: dict[
        ConfigType,
        Callable[
            [
                SrcDiscoverConfigType4Analyse
                | OneLineCommentStyleType
                | NeedIdRefsConfigType
                | MarkedRstConfigType
                | None
            ],
            SourceDiscoverConfig
            | OneLineCommentStyle
            | NeedIdRefsConfig
            | MarkedRstConfig,
        ],
    ] = {
        ConfigType.SourceDiscover: convert_src_discovery_config,  # type: ignore[dict-item] # the type is restrict by its key already
        ConfigType.OneLineCommentStyle: convert_oneline_comment_style_config,  # type: ignore[dict-item] # the type is restrict by its key already
        ConfigType.NeedIdRefsConfig: convert_need_id_refs_config,  # type: ignore[dict-item] # the type is restrict by its key already
        ConfigType.MarkedRstCofig: convert_marked_rst_config,  # type: ignore[dict-item] # the type is restrict by its key already
    }

    config = func_map[config_type](config_dict)

    return config


def convert_src_discovery_config(
    config_dict: SrcDiscoverConfigType4Analyse | None,
) -> SourceDiscoverConfig:
    if config_dict:
        src_dicover_dict = {}
        for key, value in config_dict.items():
            if key == "comment_type" and isinstance(value, list):
                file_types = []
                for comment_type in value:
                    file_types.extend(COMMENT_FILETYPE[comment_type])
                src_dicover_dict["file_types"] = file_types
            else:
                src_dicover_dict[key] = value  # type: ignore[assignment]  # dynamic assignment
        src_dicover_dict["src_dir"] = (
            Path(src_dicover_dict["src_dir"])
            if isinstance(src_dicover_dict["src_dir"], str)
            else src_dicover_dict["src_dir"]
        )
        src_discover_config = SourceDiscoverConfig(**src_dicover_dict)  # type: ignore[arg-type] # mypy is confused by dynamic assignment
    else:
        src_discover_config = SourceDiscoverConfig()

    return src_discover_config


def convert_oneline_comment_style_config(
    config_dict: OneLineCommentStyleType | None,
) -> OneLineCommentStyle:
    if config_dict is None:
        oneline_comment_style = OneLineCommentStyle()
    else:
        try:
            oneline_comment_style = OneLineCommentStyle(**config_dict)
        except TypeError as e:
            raise typer.BadParameter(
                f"Invalid oneline comment style configuration: {e}"
            ) from e
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
            raise typer.BadParameter(
                f"Invalid oneline comment style configuration: {e}"
            ) from e
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
            raise typer.BadParameter(
                f"Invalid oneline comment style configuration: {e}"
            ) from e
    return marked_rst_config


if __name__ == "__main__":
    app()
