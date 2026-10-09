import os
from collections.abc import Callable, Collection, Mapping
from pathlib import Path, PurePosixPath
from typing import Any, ClassVar, cast

from docutils import nodes
from docutils.parsers.rst import directives
from sphinx.application import Sphinx
from sphinx.util import logging
from sphinx.util.docutils import SphinxDirective

from sphinx_codelinks.analyse.analyse import SourceAnalyse
from sphinx_codelinks.analyse.models import (
    MarkedContentType,
    MultilineNeed,
    OneLineNeed,
)
from sphinx_codelinks.analyse.references import _relative_posix
from sphinx_codelinks.config import (
    CodeLinksConfig,
    CodeLinksProjectConfigType,
    locate_src_dir,
    need_id_refs_field,
)
from sphinx_codelinks.sphinx_extension.debug import measure_time
from sphinx_codelinks.sphinx_extension.need_id_refs import need_id_refs_store
from sphinx_codelinks.sphinx_extension.project_analysis import (
    SourcePage,
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
    source_pages_store,
)
from sphinx_needs.api import InvalidNeedException, add_need

try:  # remove at the 9.0.0 floor bump: the record path is new in Sphinx-Needs 9.0.0
    from sphinx_needs.api import ingest_need_record
except ImportError:  # pragma: no cover - the tests stub the name instead
    ingest_need_record = None
# remove at the 9.0.0 floor bump: 9.0.0's public generate_need_id replaces it
from sphinx_needs.api.need import _make_hashed_id
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.need_item import NeedItemSourceUnknown
from sphinx_needs.utils import add_doc, coerce_to_boolean

logger = logging.getLogger(__name__)

Marker = OneLineNeed | MultilineNeed
"""A marker ``src-trace`` creates a need from."""

NEED_DIRECTIVE_OPTIONS: frozenset[str] = frozenset(
    {
        "id",
        "jinja_content",
        "status",
        "tags",
        "collapse",
        "hide",
        "style",
        "layout",
        "template",
        "pre_template",
        "post_template",
        "constraints",
    }
)
"""The options of a need directive (``.. req::``) besides the project's extra and link
fields: a multi-line need takes these, and those fields, and nothing else."""

RECORD_KEYS: frozenset[str] = frozenset({"type", "title", "content", "doctype"})
"""The keys a multi-line need's record sets itself, never from an option."""


def from_document(docname: str, target: str) -> Path:
    """``target`` (relative to the output directory, POSIX) relative to the page of
    ``docname`` -- the depth-dependent local URL value."""
    depth = len(PurePosixPath(docname).parents) - 1
    return Path(*[".."] * depth, target)


def _line_span(oneline_need: Marker) -> str:
    """The marker's line, or ``first-Llast`` for a one-line marker spanning several
    lines; a multi-line need's open line, where its type, title and options are."""
    start = oneline_need.source_map["start"]["row"] + 1
    end = oneline_need.source_map["end"]["row"] + 1
    if isinstance(oneline_need, MultilineNeed):
        return str(start)
    return str(start) if start == end else f"{start}-L{end}"


def generate_str_link_name(oneline_need: Marker, target_filepath: Path) -> str:
    """The local URL field's value: the copied file's path and the marker's line.

    POSIX on every platform: the value becomes the link's href.
    """
    return f"{target_filepath.as_posix()}#L{_line_span(oneline_need)}"


def generate_remote_url(
    oneline_need: Marker,
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


def multiline_record(
    mneed: MultilineNeed, fields: Collection[str]
) -> tuple[dict[str, Any] | None, list[tuple[int, str]]]:
    """The record a multi-line need is created from: its options limited to the need
    directive's, converted as the directive converts them.

    A block's option values are directive strings, so it takes what ``.. req::`` takes
    (:data:`NEED_DIRECTIVE_OPTIONS` and the project's extra and link fields) and nothing
    else: a key the directive does not know -- ``parts``, ``docname`` -- is ignored with a
    warning, as the directive ignores an unknown option, ``jinja_content`` is a flag, and
    an empty ``id`` is refused with the directive's message.

    :param mneed: The multi-line need.
    :param fields: The project's extra and link field names.
    :return: The record, or ``None`` when the directive would refuse the need, and the
        warnings to report, as ``(source line, message)`` in option order.
    """
    open_line = int(mneed.source["start"]["line"])
    option_lines: Mapping[str, int] = mneed.source.get("option_lines") or {}
    record: dict[str, Any] = {}
    notes: list[tuple[int, str]] = []
    refused = False
    for key, value in mneed.need.items():
        line = option_lines.get(key, open_line)
        invalid: str | None = None
        if key in RECORD_KEYS:
            record[key] = value
        elif key not in NEED_DIRECTIVE_OPTIONS and key not in fields:
            notes.append(
                (
                    line,
                    f"multi-line need option {key!r} is not an option of the need "
                    "directive: ignored",
                )
            )
        elif key == "id" and not value:
            invalid = "'id' must not be empty"
        elif key == "jinja_content":
            try:
                record[key] = coerce_to_boolean(value)
            except ValueError as err:
                invalid = str(err)
        else:
            record[key] = value
        if invalid is not None:
            refused = True
            notes.append(
                (
                    line,
                    "multi-line need could not be created: Invalid value for "
                    f"{key!r} option: {invalid}",
                )
            )
    return (None if refused else record), notes


def report_oneline_warnings(src_analyse: SourceAnalyse, root: Path) -> None:
    """Report the analysis' warnings, each at its source line.

    One type per kind of marker, so one ``suppress_warnings`` entry silences each:
    ``codelinks.oneline`` for malformed one-line markers, ``codelinks.multiline_need``
    for multi-line needs (as for every other warning about them in the build); the
    kind leads the message.

    :param src_analyse: An analysis that has run.
    :param root: The root the locations are relative to, as for the other warnings at a
        source line.
    """
    for warning in src_analyse.oneline_warnings:
        logger.warning(
            f"{warning.sub_type}: {warning.msg}",
            type="codelinks",
            subtype="multiline_need"
            if warning.type == MarkedContentType.multiline_need
            else "oneline",
            location=f"{_relative_posix(Path(warning.file_path), root)}:"
            f"{warning.lineno}",
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
            exclude=build_output_dirs(
                self.env.app, parents=not src_discover_config.gitignore
            ),
        )
        if kind == "file" and not (src_dir / target).resolve().is_file():
            # a target that is no file (missing, or a directory) traces nothing and
            # the build goes on (#2069); the
            # scope is still recorded, so the file re-created reads this document
            logger.warning(
                f"src-trace: {target} is not a file below {src_dir.as_posix()}",
                location=self.get_location(),
                type="codelinks",
                subtype="missing_file",
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
        report_oneline_warnings(
            src_analyse, src_analyse.git_root or src_analyse.analyse_config.src_dir
        )

        # The fields' string links are registered once, at config-inited
        # (``sphinx_extension/string_links.py``): written here, at read time, they
        # were lost in every ``-j N`` worker.
        context = url_context(
            src_trace_sphinx_config, src_trace_conf, src_analyse, src_dir, out_dir
        )

        # keep the @need-ids references, to be attached once every need is known, and
        # the pages of the files their local URLs name
        if need_id_refs_field(src_trace_sphinx_config, src_trace_conf) is not None:
            records, pages = collect_need_id_refs(src_analyse, project, context)
            need_id_refs_store(self.env).setdefault(self.env.docname, []).extend(
                records
            )
            source_pages_store(self.env).setdefault(self.env.docname, []).extend(pages)

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
        self,
        oneline_need: Marker,
        need_id: str | None,
        filepath: Path,
        root: Path,
    ) -> bool:
        """Whether a need with this marker's id exists already; if so, warn once at the
        marker's line (a multi-line need's open line) and remember the owner, for
        :meth:`run`.

        ``need_id`` is the one ``add_need`` will use: written in the marker, or generated
        by Sphinx-Needs (:func:`would_be_id`). The first owner keeps an id -- another
        ``src-trace`` directive, a hand-written need, an imported one: codelinks never
        takes an id over. A need of a document this build has still to read is the
        previous build's and about to be purged, so it does not count: it is removed,
        and this directive defines the need.
        """
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
        kind = (
            "multi-line need"
            if isinstance(oneline_need, MultilineNeed)
            else "one-line need"
        )
        logger.warning(
            f"{kind} {need_id!r} is already defined {where}: not created again "
            f"by the src-trace directive in {self.env.docname!r} ({cure})",
            type="codelinks",
            subtype="duplicate_need",
            location=f"{_relative_posix(filepath, root)}:"
            f"{oneline_need.source_map['start']['row'] + 1}",
        )
        self._deferred.append((need_id, owner if isinstance(owner, str) else ""))
        return True

    def ingest_multiline(
        self,
        mneed: MultilineNeed,
        record: dict[str, Any],
        notes: list[tuple[int, str]],
        filepath: Path,
        location: Callable[[int], str],
        *,
        need_id: str | None,
        project_template: bool,
    ) -> list[nodes.Node] | None:
        """Create one multi-line need: its record, through ``ingest_need_record``.

        Its content is parsed in the markup its ``doctype`` names, anchored at the
        body's first line in the source file, so a message about the body names that
        file and line; the need itself is recorded at this directive, as a one-line
        need is. Two exceptions, ``needimport``'s: a need rendered through a template
        (its own, or one the project gives) is parsed as the page's markup, the
        template's; and a markup no parser of the project claims falls back to the
        page's, warned once per directive and markup, for a need whose content is
        parsed (not hidden, not blank).

        :param mneed: The multi-line need.
        :param record: Its record (:func:`multiline_record`), the URL fields added.
        :param notes: The warnings :func:`multiline_record` gave, reported here.
        :param filepath: The analysed file.
        :param location: The warning location of a line of the source file.
        :param need_id: The id the need gets (:func:`would_be_id`).
        :param project_template: Whether the project gives needs a template (the
            ``template`` field's default, or a predicate): a need it may apply to counts
            as rendered through one.
        :return: The need's nodes, or ``None`` when Sphinx-Needs refuses the need (warned
            at the open line).
        """
        for line, message in notes:
            logger.warning(
                message,
                type="codelinks",
                subtype="multiline_need",
                location=location(line),
            )
        open_line = mneed.source_map["start"]["row"] + 1
        doctype = record.get("doctype")
        markup = doctype if isinstance(doctype, str) and doctype else None
        if record.get("template") or project_template:
            # a template is a file of the project, written in the page's markup
            markup = None
        content_start = mneed.source.get("content_start")
        unknown: set[str] = set()

        def ingest(markup: str | None) -> list[nodes.Node]:
            # render_needs passes no block on without it (the 8.5.0 floor's guard)
            assert ingest_need_record is not None
            created, _ = ingest_need_record(
                self.env.app,
                self.state,
                record,
                need_source=NeedItemSourceUnknown(
                    docname=self.env.docname, lineno=self.lineno
                ),
                content_markup=markup,
                content_source=(
                    (os.path.abspath(filepath), int(content_start["line"]))
                    if markup is not None and content_start
                    else None
                ),
                unknown_keys=unknown,
            )
            return created

        try:
            try:
                return ingest(markup)
            except InvalidNeedException as err:
                # raised before the need is recorded: try again in the page's markup
                if err.type != "content_markup" or markup is None:
                    raise
                created = ingest(None)
                self._warn_unclaimed(markup, err.message, record, need_id)
                return created
        except InvalidNeedException as err:
            logger.warning(
                f"{err.type}: multi-line need could not be created: {err.message}",
                type="codelinks",
                subtype="multiline_need",
                location=location(open_line),
            )
            return None
        finally:
            # :func:`multiline_record` keeps only keys the project knows, so this is
            # empty unless the two disagree; then the key is lost, and said so
            option_lines: Mapping[str, int] = mneed.source.get("option_lines") or {}
            for key in sorted(unknown):
                logger.warning(
                    f"multi-line need option {key!r} is not an option of the need "
                    "directive: ignored",
                    type="codelinks",
                    subtype="multiline_need",
                    location=location(option_lines.get(key, open_line)),
                )

    def _warn_unclaimed(
        self, markup: str, reason: str, record: Mapping[str, Any], need_id: str | None
    ) -> None:
        """Warn, once per directive and markup, that a need's content was parsed as
        the page's markup because no parser claims its own -- unless the need is hidden
        or its content blank, when nothing was parsed."""
        if markup in self._unclaimed or not str(record.get("content", "")).strip():
            return
        need = (
            SphinxNeedsData(self.env).get_needs_mutable().get(need_id)
            if need_id is not None
            else None
        )
        if need is not None and need["hide"]:
            return
        self._unclaimed.add(markup)
        reason = reason.removeprefix("Content markup ").removesuffix(
            "; only reStructuredText and MyST parsers are supported."
        )
        logger.warning(
            f"Multi-line needs declare doctype {markup!r}, which this project cannot "
            f"parse content in: {reason}. Their content was parsed as this page's markup "
            "instead. Add the suffix to source_suffix with a reStructuredText or MyST "
            "parser, or map the markup to a suffix it parses.",
            type="codelinks",
            subtype="multiline_need",
            location=self.get_location(),
        )

    def render_needs(
        self,
        src_analyse: SourceAnalyse,
        local_url_field: str | None,
        remote_url_field: str | None,
        dirs: dict[str, Path],
        remote_url_pattern: str | None = None,
    ) -> list[nodes.Node]:
        """Render the needs from the virtual docs; a need whose id is defined already
        is skipped (:meth:`defined_elsewhere`).

        One-line and multi-line needs are one list, in the order of their first line
        (a multi-line need's open line) across the analysed files, as the analysis
        sorts one-line needs: so of two markers with one id, whatever their kinds, the
        earlier keeps it.

        With local URLs, each file a need is created from is recorded as a
        :class:`SourcePage` for this document -- copied and paged by every HTML build,
        never here.
        """
        rendered_needs: list[nodes.Node] = []
        self._deferred: list[tuple[str, str]] = []
        anchors: dict[str, tuple[str, list[tuple[int, str, str]]]] = {}
        root = src_analyse.git_root or src_analyse.analyse_config.src_dir
        multiline_needs = src_analyse.multiline_needs
        if multiline_needs and ingest_need_record is None:
            # remove at the 9.0.0 floor bump, with the guarded import
            logger.warning(
                "this sphinx-needs has no ingest_need_record; multi-line needs are "
                f"rendered from sphinx-needs 9.0.0 on: {len(multiline_needs)} not "
                "rendered, the one-line needs were created",
                type="codelinks",
                subtype="multiline_need",
                location=self.get_location(),
            )
            multiline_needs = []
        markers: list[Marker] = sorted(
            [*src_analyse.oneline_needs, *multiline_needs],
            key=lambda marker: (
                marker.source_map["start"]["row"],
                os.path.normcase(os.path.normpath(marker.filepath)),
                marker.source_map["start"]["column"],
            ),
        )
        # the markups whose content was parsed as the page's, warned once each
        self._unclaimed: set[str] = set()
        fields: frozenset[str] = frozenset()
        project_template = False
        if multiline_needs:
            schema = SphinxNeedsData(self.env).get_schema()
            fields = frozenset(
                [*schema.iter_extra_field_names(), *schema.iter_link_field_names()]
            )
            # a default or a predicate (which may not match the need: which one matches
            # is only known when the need is created, after its markup is chosen)
            template = schema.get_core_field("template")
            project_template = template is not None and (
                template.default is not None or bool(template.predicate_defaults)
            )
        for marker in markers:
            filepath = src_analyse.analyse_config.src_dir / marker.filepath

            def location(line: int, filepath: Path = filepath) -> str:
                return f"{_relative_posix(filepath, root)}:{line}"

            record: dict[str, Any] | None = None
            notes: list[tuple[int, str]] = []
            if isinstance(marker, MultilineNeed):
                record, notes = multiline_record(marker, fields)
                if record is None:
                    # an option the need directive would refuse: so is the need
                    for line, message in notes:
                        logger.warning(
                            message,
                            type="codelinks",
                            subtype="multiline_need",
                            location=location(line),
                        )
                    continue
            # the id add_need gives the need: the marker's, or the generated one (#2082)
            need_id = would_be_id(
                self.env.app, record if record is not None else marker.need
            )
            if self.defined_elsewhere(marker, need_id, filepath, root):
                continue
            target_filepath = dirs["target_dir"] / filepath.relative_to(dirs["src_dir"])
            # the copy's path relative to the output directory, POSIX
            target = target_filepath.relative_to(dirs["out_dir"]).as_posix()
            local_link_name = None
            remote_link_name = None
            if local_url_field:
                # the copy's path, relative to this document's page
                local_link_name = generate_str_link_name(
                    marker, from_document(self.env.docname, target)
                )
            if remote_url_field and remote_url_pattern is not None:
                remote_link_name = generate_remote_url(
                    marker,
                    target_filepath,
                    dirs,
                    remote_url_pattern,
                    src_analyse.git_commit_rev,
                )

            created: list[nodes.Node] | None = None
            if isinstance(marker, MultilineNeed) and record is not None:
                if local_url_field and local_link_name is not None:
                    record[local_url_field] = local_link_name
                if remote_url_field and remote_link_name is not None:
                    record[remote_url_field] = remote_link_name
                created = self.ingest_multiline(
                    marker,
                    record,
                    notes,
                    filepath,
                    location,
                    need_id=need_id,
                    project_template=project_template,
                )
            elif marker.need:
                # render needs from one-line marker
                kwargs: dict[str, str | list[str]] = {
                    field_name: field_value
                    for field_name, field_value in marker.need.items()
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

                try:
                    created = add_need(
                        app=self.env.app,  # The Sphinx application object
                        state=self.state,  # The docutils state object
                        docname=self.env.docname,  # The current document name
                        lineno=self.lineno,  # The line number where the directive is used
                        need_type=str(marker.need["type"]),  # The type of the need
                        title=str(marker.need["title"]),  # The title of the need
                        **cast(dict[str, Any], kwargs),
                    )
                except InvalidNeedException as err:
                    # a marker that fits the style, but a need Sphinx-Needs refuses
                    # (an id ``needs_id_regex`` rejects, say): warn, as for the others
                    logger.warning(
                        f"{err.type}: one-line need could not be created: {err.message}",
                        type="codelinks",
                        subtype="oneline",
                        location=location(marker.source_map["start"]["row"] + 1),
                    )
            if created is None:
                continue
            rendered_needs.extend(created)
            # a need add_need refused was skipped above (no anchor), so need_id
            # is the need's id here
            if local_url_field and need_id is not None:
                # the page's [docs] link back to the need, resolved when written
                line = marker.source_map["start"]["row"] + 1
                anchors.setdefault(target, (str(filepath), []))[1].append(
                    (line, self.env.docname, need_id)
                )

        if anchors:
            source_pages_store(self.env).setdefault(self.env.docname, []).extend(
                SourcePage(source, target, tuple(found))
                for target, (source, found) in anchors.items()
            )
        return rendered_needs
