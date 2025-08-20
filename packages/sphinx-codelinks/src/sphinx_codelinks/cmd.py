from collections import deque
from os import linesep
from pathlib import Path
import tomllib
from typing import Annotated, cast

import typer

from sphinx_codelinks.analyse.projects import AnalyseProjects
from sphinx_codelinks.config import (
    CodeLinksConfig,
    CodeLinksConfigType,
    CodeLinksProjectConfigType,
    generate_project_configs,
)
from sphinx_codelinks.source_discover.config import (
    CommentType,
    SourceDiscoverConfig,
    SourceDiscoverConfigType,
)
from sphinx_codelinks.source_discover.source_discover import SourceDiscover

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
    projects: Annotated[
        list[str] | None,
        typer.Option(
            "--project",
            "-p",
            help="Specify the project name of the config. If not specified, take all",
            show_default=True,
        ),
    ] = None,
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

    data: CodeLinksConfigType = load_config_from_toml(config)

    try:
        codelinks_config = CodeLinksConfig(**data)
        generate_project_configs(codelinks_config.projects)
    except TypeError as e:
        raise typer.BadParameter(str(e)) from e

    errors: deque[str] = deque()
    if outdir:
        codelinks_config.outdir = outdir

    specifed_project_configs: dict[str, CodeLinksProjectConfigType] = {}
    for project, _config in codelinks_config.projects.items():
        if projects and project not in projects:
            continue
        # Get source_discover configuration
        src_discover_config = _config["source_discover_config"]

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

        # Init source analyse config
        analyse_config = _config["analyse_config"]
        analyse_config.src_files = src_discover.source_paths
        analyse_config.src_dir = Path(src_discover.src_discover_config.src_dir)

        analyse_errors = analyse_config.check_fields_configuration()
        errors.extend(analyse_errors)
        if errors:
            raise typer.BadParameter(f"{linesep.join(errors)}")

        specifed_project_configs[project] = {"analyse_config": analyse_config}

    codelinks_config.projects = specifed_project_configs
    analyse_projects = AnalyseProjects(codelinks_config)
    analyse_projects.run()
    analyse_projects.dump_markers()


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


def load_config_from_toml(toml_file: Path) -> CodeLinksConfigType:
    try:
        with toml_file.open("rb") as f:
            toml_data = tomllib.load(f)

    except Exception as e:
        raise typer.BadParameter(
            f"Failed to load CodeLinks configuration from {toml_file}"
        ) from e

    codelink_dict = toml_data.get("codelinks")

    if not codelink_dict:
        raise typer.BadParameter(f"No 'codelinks' section found in {toml_file}")

    return cast(CodeLinksConfigType, codelink_dict)


if __name__ == "__main__":
    app()
