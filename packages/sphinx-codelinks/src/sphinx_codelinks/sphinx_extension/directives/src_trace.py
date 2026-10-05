import shutil
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path, PurePath
from typing import Any, ClassVar, cast

from docutils import nodes
from docutils.parsers.rst import directives
from sphinx.util import logging
from sphinx.util.docutils import SphinxDirective

from sphinx_codelinks.analyse.analyse import SourceAnalyse
from sphinx_codelinks.analyse.models import OneLineNeed
from sphinx_codelinks.analyse.references import NeedIdRef, need_id_ref_records
from sphinx_codelinks.config import (
    CodeLinksConfig,
    CodeLinksProjectConfigType,
    anchor_preproc_paths,
    file_lineno_href,
    need_id_refs_field,
)
from sphinx_codelinks.source_discover.config import SourceDiscoverConfig
from sphinx_codelinks.source_discover.source_discover import SourceDiscover
from sphinx_codelinks.sphinx_extension.debug import measure_time
from sphinx_codelinks.sphinx_extension.need_id_refs import need_id_refs_store
from sphinx_needs.api import add_need
from sphinx_needs.utils import add_doc
from ub_project import anchor

logger = logging.getLogger(__name__)


def get_rel_path(doc_path: Path, code_path: Path, base_dir: Path) -> tuple[Path, Path]:
    """Get the relative path from the document to the source code file and vice versa."""
    doc_depth = len(doc_path.parents) - 1
    src_rel_path = Path(*[".."] * doc_depth) / code_path.relative_to(base_dir)
    code_depth = len(code_path.relative_to(base_dir).parents) - 1
    doc_rel_path = Path(*[".."] * code_depth) / doc_path
    return src_rel_path, doc_rel_path.with_suffix(".html")


def _line_span(oneline_need: OneLineNeed) -> str:
    """The marker's line, or ``first-Llast`` for a marker spanning several lines."""
    start = oneline_need.source_map["start"]["row"] + 1
    end = oneline_need.source_map["end"]["row"] + 1
    return str(start) if start == end else f"{start}-L{end}"


def generate_str_link_name(oneline_need: OneLineNeed, target_filepath: Path) -> str:
    """The local URL field's value: the copied file's path and the marker's line.

    POSIX on every platform: the value becomes the link's href.
    """
    return f"{target_filepath.as_posix()}#L{_line_span(oneline_need)}"


def fill_remote_url(
    remote_url_pattern: str, commit: str | None, remote_path: PurePath, line: int | str
) -> str:
    """A project's ``remote_url_pattern`` filled in for one file and line.

    ``{path}`` is POSIX on every platform, as a URL path is. The one place both a
    created need's ``remote-url`` and a reference's remote URL are formed.
    """
    return remote_url_pattern.format(
        commit=commit, path=remote_path.as_posix(), line=line
    )


def generate_remote_url(
    oneline_need: OneLineNeed,
    target_filepath: Path,
    dirs: dict[str, Path],
    remote_url_pattern: str,
    commit: str | None,
) -> str:
    """The remote URL field's value: the project's ``remote_url_pattern``, filled in.

    ``{path}`` is the file's path below the git root (or the source directory's path,
    outside a git repository), POSIX on every platform as a URL path is; ``{line}`` the
    marker's line.
    """
    remote_path = dirs["remote_src_dir"] / target_filepath.relative_to(
        dirs["target_dir"]
    )
    return fill_remote_url(
        remote_url_pattern, commit, remote_path, _line_span(oneline_need)
    )


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

        # ``analyse_config`` is stored in the ``src_trace_projects`` config value,
        # which is registered with ``rebuild="env"`` and therefore persisted into
        # ``environment.pickle``. Mutating it in place would make Sphinx compare the
        # build-populated object against the freshly generated (empty) config on the
        # next build and report ``[config changed ('src_trace_projects')]`` every
        # time, forcing a full re-read. Build a per-directive copy instead so the
        # stored config value stays equal to what ``generate_project_configs`` yields.
        base_analyse_config = src_trace_conf["analyse_config"]
        # Resolve the config file's directory once (used for git_root + preproc).
        conf_dir = Path(self.env.app.confdir)
        if src_trace_sphinx_config.config_from_toml:
            src_trace_toml_path = Path(src_trace_sphinx_config.config_from_toml)
            conf_dir = anchor(src_trace_toml_path.parent, conf_dir)
        # git_root shall be relative to the config file's location (if provided)
        git_root = base_analyse_config.git_root
        if git_root:
            git_root = anchor(git_root, conf_dir).resolve()
        # preprocessor compile_commands / include dirs are relative to the config
        # file's location too (like src_dir / git_root).
        preprocessor = base_analyse_config.preprocessor
        if preprocessor is not None:
            preprocessor = anchor_preproc_paths(preprocessor, conf_dir)
            # Editing an explicitly-configured compile_commands.json changes the
            # flags (hence which #if branches are active, hence the extracted
            # markers), so register it as a build dependency to trigger a rebuild.
            # (Auto-discovered databases are located per-file inside the analysis
            # and are not tracked here.)
            if preprocessor.compile_commands is not None:
                self.env.note_dependency(str(preprocessor.compile_commands))
        analyse_config = replace(
            base_analyse_config,
            src_dir=src_dir,
            src_files=source_files,
            git_root=git_root,
            preprocessor=preprocessor,
        )
        src_analyse = SourceAnalyse(analyse_config, name=project)
        src_analyse.run()

        dirs = {
            "src_dir": src_dir,
            "out_dir": out_dir,
            "target_dir": target_dir,
        }

        # The fields' string links are registered once, at config-inited
        # (``sphinx_extension/string_links.py``): written here, at read time, they
        # were lost in every ``-j N`` worker.
        local_url_field = None
        remote_url_field = None
        remote_url_pattern = None
        if src_trace_sphinx_config.set_local_url:
            local_url_field = src_trace_sphinx_config.local_url_field
        if (
            src_trace_sphinx_config.set_remote_url
            and src_trace_conf["remote_url_pattern"]
        ):
            remote_url_field = src_trace_sphinx_config.remote_url_field
            remote_url_pattern = src_trace_conf["remote_url_pattern"]
            if not src_analyse.git_root:
                # No git root found, use the source directory as the remote source directory
                remote_src_dir = src_dir
            else:
                remote_src_dir = src_dir.relative_to(src_analyse.git_root)
            dirs["remote_src_dir"] = remote_src_dir
            if src_analyse.git_root is None or src_analyse.git_commit_rev is None:
                # no git root, or a repository without a commit: no remote URL (#2045)
                # -- the pattern would be filled with commit None (and, without a git
                # root, the build machine's absolute path). ubCode writes none either;
                # the analysis has already warned (codelinks.git_root / git_ref).
                remote_url_pattern = None

        # keep the @need-ids references, to be attached once every need is known
        if need_id_refs_field(src_trace_sphinx_config, src_trace_conf) is not None:
            need_id_refs_store(self.env).setdefault(self.env.docname, []).extend(
                self.collect_need_id_refs(
                    src_analyse, project, dirs, local_url_field, remote_url_pattern
                )
            )

        # render needs from the source files
        rendered_needs = self.render_needs(
            src_analyse,
            local_url_field,
            remote_url_field,
            dirs,
            remote_url_pattern,
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
                follow_links=src_discover_config.follow_links,
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
            conf_dir = anchor(src_trace_toml_path.parent, conf_dir)

        src_dir = anchor(src_discover_config.src_dir, conf_dir).resolve()
        return src_dir

    def collect_need_id_refs(
        self,
        src_analyse: SourceAnalyse,
        project: str,
        dirs: dict[str, Path],
        local_url_field: str | None,
        remote_url_pattern: str | None,
    ) -> list[NeedIdRef]:
        """The analysis' ``@need-ids:`` references, as records.

        Their URLs follow the created needs' rules: the remote one fills the project's
        ``remote_url_pattern`` exactly as a created need's does. The local one -- only
        when it is the value, i.e. there is no remote URL -- names the source copied
        into the build output, beside which its page is generated; with a remote URL
        nothing is copied, so no orphan copy or page is left in the output.
        """
        src_dir = dirs["src_dir"]

        def remote_url(filepath: Path, line: int) -> str | None:
            if remote_url_pattern is None:
                return None
            return fill_remote_url(
                remote_url_pattern,
                src_analyse.git_commit_rev,
                dirs["remote_src_dir"] / filepath.relative_to(src_dir),
                line,
            )

        def local_url(filepath: Path, line: int) -> str | None:
            if local_url_field is None or remote_url_pattern is not None:
                return None
            target_filepath = dirs["target_dir"] / filepath.relative_to(src_dir)
            if str(target_filepath) not in file_lineno_href.mappings:
                # copy the file and have its page generated, as for a created need
                target_filepath.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(filepath, target_filepath)
                file_lineno_href.mappings[str(target_filepath)] = {}
            relative = target_filepath.relative_to(dirs["out_dir"]).as_posix()
            return f"{relative}#L{line}"

        return need_id_ref_records(
            src_analyse.need_id_refs,
            project=project,
            root=src_analyse.git_root or src_dir,
            root_kind="git" if src_analyse.git_root else "src_dir",
            remote_url=remote_url,
            local_url=local_url,
        )

    def render_needs(
        self,
        src_analyse: SourceAnalyse,
        local_url_field: str | None,
        remote_url_field: str | None,
        dirs: dict[str, Path],
        remote_url_pattern: str | None = None,
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
                # copy files to _build/html, as bytes: no codec, no newline translation
                target_filepath.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(filepath, target_filepath)
            local_link_name = None
            remote_link_name = None
            if local_url_field:
                # generate link name
                # calculate the relative path from the current doc to the target file
                local_rel_path, docs_href = get_rel_path(
                    Path(self.env.docname), target_filepath, dirs["out_dir"]
                )
                local_link_name = generate_str_link_name(oneline_need, local_rel_path)
            if remote_url_field and remote_url_pattern is not None:
                remote_link_name = generate_remote_url(
                    oneline_need,
                    target_filepath,
                    dirs,
                    remote_url_pattern,
                    src_analyse.git_commit_rev,
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
                    **cast(dict[str, Any], kwargs),
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
