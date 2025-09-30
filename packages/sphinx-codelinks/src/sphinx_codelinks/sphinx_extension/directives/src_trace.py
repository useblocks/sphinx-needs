from collections.abc import Callable
import os
from pathlib import Path
from typing import Any, ClassVar, cast

from docutils import nodes
from docutils.parsers.rst import directives
from packaging.version import Version
import sphinx
from sphinx.util.docutils import SphinxDirective
from sphinx_needs.api import add_need  # type: ignore[import-untyped]
from sphinx_needs.utils import add_doc  # type: ignore[import-untyped]

from sphinx_codelinks.analyse.analyse import SourceAnalyse
from sphinx_codelinks.analyse.models import OneLineNeed
from sphinx_codelinks.config import (
    CodeLinksConfig,
    CodeLinksProjectConfigType,
    file_lineno_href,
)
from sphinx_codelinks.source_discover.config import SourceDiscoverConfig
from sphinx_codelinks.source_discover.source_discover import SourceDiscover
from sphinx_codelinks.sphinx_extension.debug import measure_time

sphinx_version = sphinx.__version__


if Version(sphinx_version) >= Version("1.6"):
    from sphinx.util import logging
else:
    import logging  # type: ignore[no-redef]

logger = logging.getLogger(__name__)


def get_rel_path(doc_path: Path, code_path: Path, base_dir: Path) -> tuple[Path, Path]:
    """Get the relative path from the document to the source code file and vice versa."""
    doc_depth = len(doc_path.parents) - 1
    src_rel_path = Path(*[".."] * doc_depth) / code_path.relative_to(base_dir)
    code_depth = len(code_path.relative_to(base_dir).parents) - 1
    doc_rel_path = Path(*[".."] * code_depth) / doc_path
    return src_rel_path, doc_rel_path.with_suffix(".html")


def generate_str_link_name(
    oneline_need: OneLineNeed,
    target_filepath: Path,
    dirs: dict[str, Path],
    local: bool = False,
) -> str:
    if oneline_need.source_map["start"]["row"] == oneline_need.source_map["end"]["row"]:
        lineno = f"L{oneline_need.source_map['start']['row'] + 1}"
    else:
        lineno = f"L{oneline_need.source_map['start']['row'] + 1}-L{oneline_need.source_map['end']['row'] + 1}"
    # url = str(target_filepath.relative_to(target_dir)) + f"#{lineno}"
    if local:
        url = str(target_filepath) + f"#{lineno}"
    else:
        remote_path = dirs["remote_src_dir"] / target_filepath.relative_to(
            dirs["target_dir"]
        )
        url = f"{remote_path!s}#{lineno}"

    return url


def validate_option(options: dict[str, str]) -> None:
    if "project" not in options:
        raise ValueError("Project option must be set.")
    if "file" in options and "directory" in options:
        raise ValueError("Either file or directory options can be set.")


class SourceTracing(nodes.General, nodes.Element):
    pass


class SourceTracingDirective(SphinxDirective):
    required_arguments = 0
    optional_arguments = 0
    final_argument_whitespace = True
    # this enables content in the directive
    has_content = False
    option_spec: ClassVar[dict[str, Callable[[str], str]] | None] = {
        "project": directives.unchanged_required,
        "file": directives.unchanged_required,
        "directory": directives.unchanged_required,
    }

    @measure_time("src-trace")
    def run(self) -> list[nodes.Node]:
        validate_option(self.options)

        project = self.options["project"]
        # get source tracing config
        src_trace_sphinx_config = CodeLinksConfig.from_sphinx(self.env.config)

        # load config
        src_trace_conf: CodeLinksProjectConfigType = src_trace_sphinx_config.projects[
            project
        ]
        src_discover_config = src_trace_conf["source_discover_config"]
        src_dir = self.locate_src_dir(src_trace_sphinx_config, src_discover_config)

        out_dir = Path(self.env.app.outdir)
        # the directory where the source files are copied to
        target_dir = out_dir / src_dir.name

        source_files = self.get_src_files(self.options, src_dir, src_discover_config)

        # add source files into the dependency
        # https://www.sphinx-doc.org/en/master/extdev/envapi.html#sphinx.environment.BuildEnvironment.note_dependency
        for source_file in source_files:
            self.env.note_dependency(str(source_file.resolve()))

        analyse_config = src_trace_conf["analyse_config"]
        analyse_config.src_dir = src_dir
        analyse_config.src_files = source_files
        src_analyse = SourceAnalyse(analyse_config)
        src_analyse.run()

        dirs = {
            "src_dir": src_dir,
            "out_dir": out_dir,
            "target_dir": target_dir,
        }

        # inject needs_string_links config before add_need()
        # https://sphinx-needs.readthedocs.io/en/latest/configuration.html#needs-string-links
        # local URL
        local_url_field = None
        remote_url_field = None
        if src_trace_sphinx_config.set_local_url:
            local_url_field = src_trace_sphinx_config.local_url_field
            to_remove_str = f"{out_dir!s}{os.sep}"
            if os.name == "nt":
                to_remove_str = to_remove_str.replace("\\", "\\\\")
            self.env.config.needs_string_links[local_url_field] = {
                "regex": r"^(?P<value>.+?)\.[^\.]+#L(?P<lineno>\d+)",
                "link_url": ("{{value}}.html#L-{{lineno}}"),
                "link_name": f"{{{{value | replace('{to_remove_str}', '')}}}}#L{{{{lineno}}}}",
                "options": [local_url_field],
            }
        if (
            src_trace_sphinx_config.set_remote_url
            and src_trace_conf["remote_url_pattern"]
        ):
            remote_url_field = src_trace_sphinx_config.remote_url_field
            if not src_analyse.git_root:
                # No git root found, use the source directory as the remote source directory
                remote_src_dir = src_dir
            else:
                remote_src_dir = src_dir.relative_to(src_analyse.git_root)
            dirs["remote_src_dir"] = remote_src_dir
            remote_url_pattern = src_trace_conf["remote_url_pattern"].format(
                commit=src_analyse.git_commit_rev,
                # path=f"{remote_src_dir}/" + "{{value}}",
                path="{{value}}",
                line="{{lineno}}",
            )
            self.env.config.needs_string_links[remote_url_field] = {
                "regex": r"^(?P<value>.+)#L(?P<lineno>.*)?",
                "link_url": remote_url_pattern,
                "link_name": "{{value}}#L{{lineno}}",
                "options": [remote_url_field],
            }

        # render needs from the source files
        rendered_needs = self.render_needs(
            src_analyse,
            local_url_field,
            remote_url_field,
            dirs,
        )

        # for post-processing of need links
        # https://github.com/useblocks/sphinx-needs/issues/1210
        add_doc(self.env, self.env.docname)

        return rendered_needs

    def get_src_files(
        self,
        additional_options: dict[str, str],
        src_dir: Path,
        src_discover_config: SourceDiscoverConfig,
    ) -> list[Path]:
        """Leverage SourceDiscover to find sources files from the given directory."""
        source_files = []
        if "file" in self.options:
            file: str = self.options["file"]
            filepath = src_dir / file
            source_files.append(filepath.resolve())
            additional_options["file"] = file
        else:
            directory = self.options.get("directory")
            if directory is None:
                # when neither "file" and "directory" are given, the project root dir is by default
                directory = "./"
            else:
                additional_options["directory"] = directory
            dir_path = src_dir / directory
            # create a new config for the specified directory
            src_discover = SourceDiscoverConfig(
                dir_path,
                gitignore=src_discover_config.gitignore,
                include=src_discover_config.include,
                exclude=src_discover_config.exclude,
                comment_type=src_discover_config.comment_type,
            )
            source_discover = SourceDiscover(src_discover)
            source_files.extend(source_discover.source_paths)

        return source_files

    def locate_src_dir(
        self,
        src_trace_sphinx_config: CodeLinksConfig,
        src_discover_config: SourceDiscoverConfig,
    ) -> Path:
        """Locate the source directory based on the configuration."""
        #  src dir in src_trace_conf is relative to conf_dir by default
        conf_dir = Path(self.env.app.confdir)
        # if config toml file is used, src dir is relative to the config toml
        if src_trace_sphinx_config.config_from_toml:
            src_trace_toml_path = Path(src_trace_sphinx_config.config_from_toml)
            conf_dir = conf_dir / src_trace_toml_path.parent

        src_dir = (conf_dir / src_discover_config.src_dir).resolve()
        return src_dir

    def render_needs(
        self,
        src_analyse: SourceAnalyse,
        local_url_field: str | None,
        remote_url_field: str | None,
        dirs: dict[str, Path],
    ) -> list[nodes.Node]:
        """Render the needs from the virtual docs"""
        rendered_needs: list[nodes.Node] = []
        for oneline_need in src_analyse.oneline_needs:
            # # add source files into the dependency
            # # https://www.sphinx-doc.org/en/master/extdev/envapi.html#sphinx.environment.BuildEnvironment.note_dependency
            # self.env.note_dependency(str(oneline_need.filepath.resolve()))

            filepath = src_analyse.analyse_config.src_dir / oneline_need.filepath
            target_filepath = dirs["target_dir"] / filepath.relative_to(dirs["src_dir"])

            # mapping between lineno and need link in docs for local url

            # The link to the documentation page for the source file

            if local_url_field:
                # copy files to _build/html
                target_filepath.parent.mkdir(parents=True, exist_ok=True)
                target_filepath.write_text(filepath.read_text())
            local_link_name = None
            remote_link_name = None
            if local_url_field:
                # generate link name
                # calculate the relative path from the current doc to the target file
                local_rel_path, docs_href = get_rel_path(
                    Path(self.env.docname), target_filepath, dirs["out_dir"]
                )
                local_link_name = generate_str_link_name(
                    oneline_need,
                    local_rel_path,
                    dirs,
                    local=True,
                )
            if remote_url_field:
                remote_link_name = generate_str_link_name(
                    oneline_need, target_filepath, dirs, local=False
                )

            if oneline_need.need:
                # render needs from one-line marker
                kwargs: dict[str, str | list[str]] = {
                    field_name: field_value
                    for field_name, field_value in oneline_need.need.items()
                    if field_name
                    not in [
                        "title",
                        "type",
                    ]  # title and type are mandatory for add_need()
                }

                if local_url_field and local_link_name is not None:
                    kwargs[local_url_field] = local_link_name
                if remote_url_field and remote_link_name is not None:
                    kwargs[remote_url_field] = remote_link_name

                oneline_needs: list[nodes.Node] = add_need(
                    app=self.env.app,  # The Sphinx application object
                    state=self.state,  # The docutils state object
                    docname=self.env.docname,  # The current document name
                    lineno=self.lineno,  # The line number where the directive is used
                    need_type=str(oneline_need.need["type"]),  # The type of the need
                    title=str(oneline_need.need["title"]),  # The title of the need
                    **cast(dict[str, Any], kwargs),  # type: ignore[explicit-any]
                )
                rendered_needs.extend(oneline_needs)
                if local_url_field:
                    # save the mapping of need links and line numbers of source codes
                    # for the later use in `html-collect-pages`
                    if str(target_filepath) not in file_lineno_href.mappings:
                        file_lineno_href.mappings[str(target_filepath)] = {
                            oneline_need.source_map["start"]["row"]
                            + 1: f"{docs_href}#{oneline_need.need['id']}"
                        }
                    else:
                        file_lineno_href.mappings[str(target_filepath)][
                            oneline_need.source_map["start"]["row"] + 1
                        ] = f"{docs_href}#{oneline_need.need['id']}"

        return rendered_needs
