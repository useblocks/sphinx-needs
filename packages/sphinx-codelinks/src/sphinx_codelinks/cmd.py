import json
from collections import deque
from os import linesep
from pathlib import Path
from typing import Annotated, TypeAlias, cast

import typer

from sphinx_codelinks.analyse.projects import AnalyseProjects
from sphinx_codelinks.config import (
    CodeLinksConfig,
    CodeLinksConfigType,
    CodeLinksProjectConfigType,
    anchor_preproc_paths,
    generate_project_configs,
    git_root_problem,
    git_root_warning,
    load_codelinks_table,
)
from sphinx_codelinks.logger import configure_cli, get_logger, logger
from sphinx_codelinks.needextend_write import MarkedObjType, convert_marked_content
from sphinx_codelinks.source_discover.config import (
    CommentType,
    SourceDiscoverConfig,
    SourceDiscoverConfigType,
)
from sphinx_codelinks.source_discover.source_discover import SourceDiscover
from ub_project import ProjectConfigError, anchor

#: the package logger: a warning goes to stderr once ``configure_cli`` ran
analysis_logger = get_logger(__name__)

app = typer.Typer(
    no_args_is_help=True, context_settings={"help_option_names": ["-h", "--help"]}
)
write_app = typer.Typer(
    help="Export marked content to other formats", no_args_is_help=True
)
app.add_typer(write_app, name="write", rich_help_panel="Sub-menus")

WRITE_RST_DEPRECATED = (
    "`write rst` is deprecated: the build attaches `@need-ids:` references itself "
    "(field `code_url`); it will be removed in sphinx-codelinks 2.0.0"
)

OptVerbose: TypeAlias = Annotated[  # has to be TypeAlias
    bool,
    typer.Option(
        ...,
        "-v",
        "--verbose",
        is_flag=True,
        help="Show debug information",
        rich_help_panel="Logging",
    ),
]
OptQuiet: TypeAlias = Annotated[  # has to be TypeAlias
    bool,
    typer.Option(
        ...,
        "-q",
        "--quiet",
        is_flag=True,
        help="Only show errors and warnings",
        rich_help_panel="Logging",
    ),
]


@app.command(no_args_is_help=True)
def analyse(  # for CLI, so it needs the branches
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
    verbose: OptVerbose = False,
    quiet: OptQuiet = False,
) -> None:
    """Analyse marked content in source code."""
    # @CLI command to analyse source code and extract traceability markers, IMPL_CLI_ANALYZE, impl, [FE_CLI_ANALYZE]
    configure_cli(verbose, quiet)

    data: CodeLinksConfigType = load_config_from_toml(config)

    try:
        codelinks_config = CodeLinksConfig(**data)
        generate_project_configs(codelinks_config.projects)
    except TypeError as e:
        raise typer.BadParameter(str(e)) from e

    errors: deque[str] = deque()
    if outdir:
        codelinks_config.outdir = outdir

    project_errors: list[str] = []
    if projects:
        for project in projects:
            if project not in codelinks_config.projects:
                if not project_errors:
                    project_errors.append("The following projects are not found:")
                project_errors.append(project)
    if project_errors:
        raise typer.BadParameter(f"{linesep.join(project_errors)}")

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
        src_discover_config.src_dir = anchor(
            src_discover_config.src_dir, config.parent
        ).resolve()

        src_discover = SourceDiscover(src_discover_config)

        # Init source analyse config
        analyse_config = _config["analyse_config"]
        analyse_config.src_files = src_discover.source_paths
        analyse_config.src_dir = Path(src_discover.src_discover_config.src_dir)

        # git_root shall be relative to the config file's location (like src_dir)
        if analyse_config.git_root is not None:
            analyse_config.git_root = anchor(
                analyse_config.git_root, config.parent
            ).resolve()
            # the build's rule: a git_root that does not contain src_dir is ignored,
            # and the analysis detects the repository from src_dir (#2062)
            problem = git_root_problem(analyse_config.git_root, analyse_config.src_dir)
            if problem is not None:
                analysis_logger.warning(
                    git_root_warning(project, problem), subtype="git_root"
                )
                analyse_config.git_root = None

        # preprocessor compile_commands / include dirs are relative to the config
        # file's location too (like src_dir / git_root).
        if analyse_config.preprocessor is not None:
            analyse_config.preprocessor = anchor_preproc_paths(
                analyse_config.preprocessor, config.parent
            )

        analyse_errors = analyse_config.check_fields_configuration()
        errors.extend(analyse_errors)
        if errors:
            raise typer.BadParameter(f"{linesep.join(errors)}")

        specifed_project_configs[project] = {"analyse_config": analyse_config}

    codelinks_config.projects = specifed_project_configs
    analyse_projects = AnalyseProjects(codelinks_config)
    analyse_projects.run()

    # Output warnings to console for CLI users: one shape for every kind
    for src_analyse in analyse_projects.projects_analyse.values():
        for warning in src_analyse.warnings:
            logger.warning(
                f"Analyse warning in {warning.file_path}:{warning.lineno} "
                f"- {warning.sub_type}: {warning.msg}",
            )

    analyse_projects.dump_markers()


@app.command(no_args_is_help=True)
def discover(  # CLI command requires multiple parameters
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
    # @CLI command to discover source files recursively with gitignore support, IMPL_CLI_DISCOVER, impl, [FE_CLI_DISCOVER]
    gitignore: Annotated[
        bool,
        typer.Option(
            help="Respect .gitignore files in the given directory and its parents"
        ),
    ] = True,
    follow_links: Annotated[
        bool,
        typer.Option(help="Follow symbolic links during file discovery"),
    ] = False,
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
    # a file outside the directory is warned about: on stderr, whatever ran before
    configure_cli()

    src_discover_dict: SourceDiscoverConfigType = {
        "src_dir": src_dir,
        "exclude": exclude,
        "include": include,
        "gitignore": gitignore,
        "follow_links": follow_links,
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


@write_app.command("rst", no_args_is_help=True)
def write_rst(  # for CLI, so it takes as many as it requires
    jsonpath: Annotated[
        Path,
        typer.Argument(
            ...,
            help="Path of the JSON file which contains the extracted markers",
            show_default=False,
            dir_okay=False,
            file_okay=True,
            exists=True,
            resolve_path=True,
        ),
    ],
    # @CLI command to generate needextend RST file from extracted markers, IMPL_CLI_WRITE, impl, [FE_CLI_WRITE]
    outpath: Annotated[
        Path,
        typer.Option(
            "--outpath",
            "-o",
            help="The output path for generated rst file",
            show_default=True,
            dir_okay=False,
            file_okay=True,
            exists=False,
        ),
    ] = Path("needextend.rst"),
    remote_url_field: Annotated[
        str,
        typer.Option(
            "--remote-url-field",
            "-r",
            help="The field name for the remote url",
            show_default=True,
        ),
    ] = "remote_url",  # to show default value in this CLI
    title: Annotated[
        str | None,
        typer.Option(
            "--title",
            "-t",
            help="Give the title to the generated RST file",
            show_default=True,
        ),
    ] = None,  # to show default value in this CLI
    verbose: OptVerbose = False,
    quiet: OptQuiet = False,
) -> None:
    """Generate needextend.rst from the extracted obj in JSON (deprecated).

    The Sphinx build attaches ``@need-ids:`` references to the needs they name itself,
    in each project's ``ref_url_field`` (default ``code_url``).
    """
    configure_cli(verbose, quiet)
    typer.echo(WRITE_RST_DEPRECATED, err=True)
    try:
        with jsonpath.open("r") as f:
            marked_content = json.load(f)
    except Exception as e:
        raise typer.BadParameter(
            f"Failed to load marked content from {jsonpath}: {e}"
        ) from e

    marked_objs: list[MarkedObjType] = [
        obj for objs in marked_content.values() for obj in objs
    ]

    needextend_texts, errors = convert_marked_content(
        marked_objs, remote_url_field, title
    )
    if errors:
        raise typer.BadParameter(
            f"Errors occurred during conversion: {linesep.join(errors)}"
        )
    with outpath.open("w") as f:
        f.writelines(needextend_texts)
    typer.echo(f"Generated {outpath}")


def load_config_from_toml(toml_file: Path) -> CodeLinksConfigType:
    try:
        codelink_dict = load_codelinks_table(toml_file)
    except ProjectConfigError as error:
        # ub-project's message already names the file and says what is wrong
        raise typer.BadParameter(str(error)) from error
    except Exception as error:
        # the TOML parser can also fail with an exception ``load_toml`` does not wrap (a
        # RecursionError on a pathologically nested file): still a usage error
        raise typer.BadParameter(
            f"Failed to load CodeLinks configuration from {toml_file}: {error}"
        ) from error

    if not codelink_dict:
        raise typer.BadParameter(f"No 'codelinks' section found in {toml_file}")

    return cast(CodeLinksConfigType, codelink_dict)


if __name__ == "__main__":
    app()
