from collections.abc import Callable
import os
from pathlib import Path
import subprocess
from typing import Any, ClassVar, cast

from docutils import nodes
from docutils.parsers.rst import directives
from packaging.version import Version
import sphinx
from sphinx.util.docutils import SphinxDirective
from sphinx_needs.api import add_need  # type: ignore[import-untyped]
from sphinx_needs.utils import add_doc  # type: ignore[import-untyped]

from sphinx_codelinks.source_discovery.source_discover import SourceDiscover
from sphinx_codelinks.sphinx_extension.config import (
    SRC_TRACE_CACHE,
    SrcTraceProjectConfigType,
    SrcTraceSphinxConfig,
    file_lineno_href,
)
from sphinx_codelinks.sphinx_extension.debug import measure_time
from sphinx_codelinks.virtual_docs.ubt_models import UBTComment
from sphinx_codelinks.virtual_docs.utils import get_file_types
from sphinx_codelinks.virtual_docs.virtual_docs import VirtualDocs

sphinx_version = sphinx.__version__


if Version(sphinx_version) >= Version("1.6"):
    from sphinx.util import logging
else:
    import logging  # type: ignore[no-redef]

logger = logging.getLogger(__name__)


def generate_str_link_name(
    comment: UBTComment,
    target_filepath: Path,
    dirs: dict[str, Path],
    local: bool = False,
) -> str:
    if comment.start_line == comment.end_line:
        lineno = f"L{comment.start_line}"
    else:
        lineno = f"L{comment.start_line}-L{comment.end_line}"
    # url = str(target_filepath.relative_to(target_dir)) + f"#{lineno}"
    if local:
        url = str(target_filepath) + f"#{lineno}"
    else:
        remote_path = dirs["remote_src_dir"] / target_filepath.relative_to(
            dirs["target_dir"]
        )
        url = f"{remote_path!s}#{lineno}"

    return url


def get_git_commit_id(src_dir: Path) -> str:
    try:
        commit_id = (
            subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=src_dir)  # noqa: S607
            .decode("utf-8")
            .strip()
        )
    except subprocess.CalledProcessError as err:
        # raise RuntimeError("Failed to get the latest commit ID") from err
        logger.warning(f"Failed to get the latest commit ID: {err}")
        commit_id = ""
    return commit_id


def get_git_root(cwd: Path = Path()) -> Path | None:
    try:
        # Run the git command to get the root directory
        git_root = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],  # noqa: S607
            cwd=cwd,
            text=True,  # Ensures the output is a string
        ).strip()
        return Path(git_root)
    except subprocess.CalledProcessError:
        logger.warning(f"Failed to get the Git root directory for {cwd}.")
        return None


def validate_option(options: dict[str, str]) -> None:
    if "project" not in options:
        raise ValueError("Project option must be set.")
    if "file" in options and "directory" in options:
        raise ValueError("Either file or directory options can be set.")


class SourceTracing(nodes.General, nodes.Element):
    pass


class SourceTracingDirective(SphinxDirective):
    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = True
    # this enables content in the directive
    has_content = True
    option_spec: ClassVar[dict[str, Callable[[str], str]] | None] = {
        "id": directives.unchanged_required,
        "project": directives.unchanged_required,
        "file": directives.unchanged_required,
        "directory": directives.unchanged_required,
    }

    @measure_time("src-trace")
    def run(self) -> list[nodes.Node]:
        validate_option(self.options)

        project = self.options["project"]
        title = self.arguments[0]
        # get source tracing config
        src_trace_sphinx_config = SrcTraceSphinxConfig(self.env.config)

        # load config
        src_trace_conf: SrcTraceProjectConfigType = src_trace_sphinx_config.projects[
            project
        ]
        comment_type = src_trace_conf["comment_type"]
        oneline_comment_style = src_trace_conf["oneline_comment_style"]

        src_dir = self.locate_src_dir(src_trace_sphinx_config, src_trace_conf)

        out_dir = Path(self.env.app.outdir)
        # the directory where the source files are copied to
        target_dir = out_dir / src_dir.name

        extra_options = {"project": project}
        source_files = self.get_src_files(self.options, src_dir, src_trace_conf)

        # add source files into the dependency
        # https://www.sphinx-doc.org/en/master/extdev/envapi.html#sphinx.environment.BuildEnvironment.note_dependency
        for source_file in source_files:
            self.env.note_dependency(str(source_file.resolve()))

        virtual_docs = VirtualDocs(
            source_files,
            str(src_dir),
            str(out_dir / SRC_TRACE_CACHE),
            oneline_comment_style,
            comment_type=comment_type,
        )
        virtual_docs.collect()

        needs = []

        # create the need for src-trace directive
        src_trace_need = add_need(
            app=self.env.app,  # The Sphinx application object
            state=self.state,  # The docutils state object
            docname=self.env.docname,  # The current document name
            lineno=self.lineno,  # The line number where the directive is used
            need_type="srctrace",  # The type of the need
            title=title,  # The title of the need
            **extra_options,
        )
        needs.extend(src_trace_need)

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
                "link_url": ("file://{{value}}.html#L-{{lineno}}"),
                "link_name": f"{{{{value | replace('{to_remove_str}', '')}}}}#L{{{{lineno}}}}",
                "options": [local_url_field],
            }
        if (
            src_trace_sphinx_config.set_remote_url
            and src_trace_conf["remote_url_pattern"]
        ):
            git_root_path: Path | None = get_git_root(src_dir)
            remote_url_field = src_trace_sphinx_config.remote_url_field
            commit_id = get_git_commit_id(src_dir)
            if git_root_path is None:
                # No git root found, use the source directory as the remote source directory
                remote_src_dir = src_dir
            else:
                remote_src_dir = src_dir.relative_to(git_root_path)
            dirs["remote_src_dir"] = remote_src_dir
            remote_url_pattern = src_trace_conf["remote_url_pattern"].format(
                commit=commit_id,
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
            virtual_docs,
            local_url_field,
            remote_url_field,
            dirs,
        )
        if rendered_needs:
            needs.extend(rendered_needs)

        # virtual docs caching
        virtual_docs.dump_virtual_docs()
        virtual_docs.cache.update_cache()

        # for post-processing of need links
        # https://github.com/useblocks/sphinx-needs/issues/1210
        add_doc(self.env, self.env.docname)

        return needs

    def get_src_files(
        self,
        extra_options: dict[str, str],
        src_dir: Path,
        src_trace_conf: SrcTraceProjectConfigType,
    ) -> list[Path]:
        source_files = []
        if "file" in self.options:
            file: str = self.options["file"]
            filepath = src_dir / file
            source_files.append(filepath.resolve())
            extra_options["file"] = file
        else:
            directory = self.options.get("directory")
            if directory is None:
                # when neither "file" and "directory" are given, the project root dir is by default
                directory = "./"
            else:
                extra_options["directory"] = directory
            dir_path = src_dir / directory
            file_types = get_file_types(src_trace_conf["comment_type"])
            source_discover = SourceDiscover(
                dir_path,
                gitignore=src_trace_conf["gitignore"],
                include=src_trace_conf["include"],
                exclude=src_trace_conf["exclude"],
                file_types=file_types,
            )
            source_files.extend(source_discover.source_paths)

        return source_files

    def locate_src_dir(
        self,
        src_trace_sphinx_config: SrcTraceSphinxConfig,
        src_trace_conf: SrcTraceProjectConfigType,
    ) -> Path:
        """Locate the source directory based on the configuration."""
        #  src dir in src_trace_conf is relative to conf_dir by default
        conf_dir = Path(self.env.app.confdir)
        # if config toml file is used, src dir is relative to the config toml
        if src_trace_sphinx_config.config_from_toml:
            src_trace_toml_path = Path(src_trace_sphinx_config.config_from_toml)
            conf_dir = conf_dir / src_trace_toml_path.parent

        src_dir = (conf_dir / src_trace_conf["src_dir"]).resolve()
        return src_dir

    def render_needs(
        self,
        virtual_docs: VirtualDocs,
        local_url_field: str | None,
        remote_url_field: str | None,
        dirs: dict[str, Path],
    ) -> list[nodes.Node]:
        """Render the needs from the virtual docs"""
        rendered_needs: list[nodes.Node] = []
        for virtual_doc in virtual_docs.virtual_docs:
            # # add source files into the dependency
            # # https://www.sphinx-doc.org/en/master/extdev/envapi.html#sphinx.environment.BuildEnvironment.note_dependency
            # self.env.note_dependency(str(virtual_doc.filepath.resolve()))

            filepath = virtual_doc.filepath
            target_filepath = dirs["target_dir"] / filepath.relative_to(dirs["src_dir"])
            # mapping between lineno and need link in docs for local url
            lineno_href = {}
            # The link to the documentation page for the source file
            docs_href = f"{dirs['out_dir'] / self.env.docname}.html"
            if local_url_field:
                # copy files to _build/html
                target_filepath.parent.mkdir(parents=True, exist_ok=True)
                target_filepath.write_text(filepath.read_text())
            for comment in virtual_doc.comments:
                local_link_name = None
                remote_link_name = None
                if local_url_field:
                    # generate link name
                    local_link_name = generate_str_link_name(
                        comment, target_filepath, dirs, local=True
                    )
                if remote_url_field:
                    remote_link_name = generate_str_link_name(
                        comment, target_filepath, dirs, local=False
                    )

                if comment.resolved_marker:
                    # render needs from one-line marker
                    kwargs: dict[str, str | list[str]] = {
                        field_name: field_value
                        for field_name, field_value in comment.resolved_marker.items()
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
                        need_type=str(
                            comment.resolved_marker["type"]
                        ),  # The type of the need
                        title=str(
                            comment.resolved_marker["title"]
                        ),  # The title of the need
                        **cast(dict[str, Any], kwargs),  # type: ignore[explicit-any]
                    )
                    rendered_needs.extend(oneline_needs)
                    if local_url_field:
                        # save the mapping of need links and line numbers of source codes
                        # for the later use in `html-collect-pages`
                        lineno_href[comment.start_line] = (
                            f"{docs_href}#{comment.resolved_marker['id']}"
                        )

                if local_url_field:
                    # save the mappings of need links and line numbers of source codes
                    # for the later use in `html-collect-pages`
                    file_lineno_href.mappings[str(target_filepath)] = lineno_href

        return rendered_needs
