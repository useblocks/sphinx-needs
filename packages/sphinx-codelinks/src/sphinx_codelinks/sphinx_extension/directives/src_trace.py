import shutil
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, ClassVar, cast

from docutils import nodes
from docutils.parsers.rst import directives
from sphinx.application import Sphinx
from sphinx.util import logging
from sphinx.util.docutils import SphinxDirective

from sphinx_codelinks.analyse.analyse import SourceAnalyse
from sphinx_codelinks.analyse.models import OneLineNeed
from sphinx_codelinks.analyse.references import _relative_posix
from sphinx_codelinks.config import (
    CodeLinksConfig,
    CodeLinksProjectConfigType,
    file_lineno_href,
    locate_src_dir,
    need_id_refs_field,
)
from sphinx_codelinks.sphinx_extension.debug import measure_time
from sphinx_codelinks.sphinx_extension.need_id_refs import need_id_refs_store
from sphinx_codelinks.sphinx_extension.project_analysis import (
    collect_need_id_refs,
    fill_remote_url,
    prepare_analyse_config,
    url_context,
)
from sphinx_codelinks.sphinx_extension.rediscovery import (
    ScopeKind,
    ScopeRecord,
    build_output_dirs,
    discover_scope,
    file_fingerprint,
    files_fingerprint,
    is_unread,
    scope_store,
)
from sphinx_needs.api import add_need
from sphinx_needs.api.need import _make_hashed_id
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.utils import add_doc

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


def would_be_id(app: Sphinx, need: Mapping[str, Any]) -> str | None:
    """The id ``add_need`` will give a one-line need: its ``id`` field, else the one
    Sphinx-Needs generates for a need without one -- ``generate_need`` calls
    ``_make_hashed_id(<the type's prefix>, <full_title, else title>, <content>, config)``
    (``sphinx_needs/api/need.py``, the same at the 8.5.0 floor), with the type, title and
    fields :meth:`SourceTracingDirective.render_needs` passes. ``None`` when ``add_need``
    refuses the need before any id exists (an unknown type, ``needs_id_required``).
    """
    given = need.get("id")
    if given is not None:
        return given if isinstance(given, str) and given else None
    config = NeedsSphinxConfig(app.config)
    if config.id_required:
        return None
    types = {need_type["directive"]: need_type for need_type in config.types}
    need_type = types.get(str(need.get("type")))
    if need_type is None:
        return None
    full_title = need.get("full_title")
    return _make_hashed_id(
        need_type["prefix"],
        str(need.get("title")) if full_title is None else str(full_title),
        str(need.get("content", "")),
        config,
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
        src_dir = locate_src_dir(
            self.env.app.confdir, src_trace_sphinx_config, src_discover_config
        )
        out_dir = Path(self.env.app.outdir)

        kind, target = self.scope()
        source_files = discover_scope(
            src_dir,
            src_discover_config,
            kind,
            target,
            exclude=build_output_dirs(self.env.app),
        )

        # add source files into the dependency (discovery's paths are canonical
        # already: resolving them again would only walk the file system a second time)
        # https://www.sphinx-doc.org/en/master/extdev/envapi.html#sphinx.environment.BuildEnvironment.note_dependency
        for source_file in source_files:
            self.env.note_dependency(str(source_file))
        # and record the scope, so that a file ADDED to it re-reads this document
        # (a new file is a dependency of nothing; ``rediscovery.find_outdated_scopes``)
        if kind == "file":
            found = file_fingerprint(src_dir, target)
        else:
            found = files_fingerprint(source_files, (src_dir / target).resolve())

        analyse_config = prepare_analyse_config(
            self.env.app.confdir,
            src_trace_sphinx_config,
            src_trace_conf,
            src_dir=src_dir,
            src_files=source_files,
        )
        preprocessor = analyse_config.preprocessor
        if preprocessor is not None and preprocessor.compile_commands is not None:
            # Editing an explicitly-configured compile_commands.json changes the
            # flags (hence which #if branches are active, hence the extracted
            # markers), so register it as a build dependency to trigger a rebuild.
            # (Auto-discovered databases are located per-file inside the analysis
            # and are not tracked here.)
            self.env.note_dependency(str(preprocessor.compile_commands))
        src_analyse = SourceAnalyse(analyse_config, name=project)
        src_analyse.run(log_summary=False)

        # The fields' string links are registered once, at config-inited
        # (``sphinx_extension/string_links.py``): written here, at read time, they
        # were lost in every ``-j N`` worker.
        context = url_context(
            src_trace_sphinx_config, src_trace_conf, src_analyse, src_dir, out_dir
        )

        # keep the @need-ids references, to be attached once every need is known
        if need_id_refs_field(src_trace_sphinx_config, src_trace_conf) is not None:
            need_id_refs_store(self.env).setdefault(self.env.docname, []).extend(
                collect_need_id_refs(src_analyse, project, context)
            )

        # render needs from the source files
        rendered_needs = self.render_needs(
            src_analyse,
            context.local_url_field,
            context.remote_url_field,
            context.dirs,
            context.remote_url_pattern,
        )
        skipped = self._deferred
        src_analyse.log_summary(
            f", {len(skipped)} skipped (already defined)" if skipped else ""
        )
        # record the scope, and the needs another document owns: its change re-reads
        # this one (``rediscovery.find_outdated_scopes``)
        deferred = tuple(
            dict.fromkeys(
                (need_id, owner)
                for need_id, owner in skipped
                if owner != self.env.docname
            )
        )
        scope_store(self.env).setdefault(self.env.docname, []).append(
            ScopeRecord(
                project=project,
                kind=kind,
                target=target,
                fingerprint=found,
                deferred=deferred,
            )
        )

        # for post-processing of need links
        # https://github.com/useblocks/sphinx-needs/issues/1210
        add_doc(self.env, self.env.docname)

        return rendered_needs

    def scope(self) -> tuple[ScopeKind, str]:
        """The directive's scope: ``:file:``, else ``:directory:``, else the project's
        whole source directory (``"./"``)."""
        if "file" in self.options:
            return "file", self.options["file"]
        return "directory", self.options.get("directory", "./")

    def defined_elsewhere(
        self, oneline_need: OneLineNeed, filepath: Path, root: Path
    ) -> bool:
        """Whether a need with this one-line need's id exists already; if so, warn
        once at the marker's line and remember the owner, for :meth:`run`.

        The id is the one ``add_need`` will use: written in the marker, or generated by
        Sphinx-Needs (:func:`would_be_id`). The first owner keeps an id -- another
        ``src-trace`` directive, a hand-written need, an imported one: codelinks never
        takes an id over. A need of a document this build has still to read is the
        previous build's and about to be purged, so it does not count: it is removed,
        and this directive defines the need.
        """
        if not oneline_need.need:
            return False
        need_id = would_be_id(self.env.app, oneline_need.need)
        if need_id is None:
            return False
        data = SphinxNeedsData(self.env)
        existing = data.get_needs_mutable().get(need_id)
        if existing is None:
            return False
        owner = existing.get("docname")
        if isinstance(owner, str) and owner and is_unread(self.env, owner):
            data.remove_need(need_id)
            return False
        where = (
            f"in document {owner!r}"
            if isinstance(owner, str) and owner
            else "by an external need"
        )
        # two markers of this document's own scopes generating one id is a title
        # collision, not an overlap: the cure differs
        cure = (
            "give the markers distinct ids"
            if owner == self.env.docname
            else "narrow one directive's scope"
        )
        logger.warning(
            f"one-line need {need_id!r} is already defined {where}: not created again "
            f"by the src-trace directive in {self.env.docname!r} ({cure})",
            type="codelinks",
            subtype="duplicate_need",
            location=f"{_relative_posix(filepath, root)}:"
            f"{oneline_need.source_map['start']['row'] + 1}",
        )
        self._deferred.append((need_id, owner if isinstance(owner, str) else ""))
        return True

    def render_needs(
        self,
        src_analyse: SourceAnalyse,
        local_url_field: str | None,
        remote_url_field: str | None,
        dirs: dict[str, Path],
        remote_url_pattern: str | None = None,
    ) -> list[nodes.Node]:
        """Render the needs from the virtual docs; a need whose id is defined already
        is skipped (:meth:`defined_elsewhere`)."""
        rendered_needs: list[nodes.Node] = []
        self._deferred: list[tuple[str, str]] = []
        root = src_analyse.git_root or src_analyse.analyse_config.src_dir
        for oneline_need in src_analyse.oneline_needs:
            filepath = src_analyse.analyse_config.src_dir / oneline_need.filepath
            if self.defined_elsewhere(oneline_need, filepath, root):
                continue
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
