from __future__ import annotations

import os
import re
from collections.abc import Sequence
from functools import partial
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from docutils import nodes
from docutils.parsers.rst import directives
from requests_file import FileAdapter
from sphinx.util.docutils import SphinxDirective

import ub_needs_exchange as exchange
from sphinx_needs._need_source import (
    NeedSourceHop,
    NeedSourcePhysical,
    directive_hops,
    directive_line,
    physical_for,
    upstream_hops,
    writing_project,
)
from sphinx_needs._need_templates import template_path
from sphinx_needs._needsfile_v2a1 import READ_DRAFTS
from sphinx_needs.api import InvalidNeedException, ingest_need_record
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.debug import measure_time
from sphinx_needs.filter_common import filter_import_item
from sphinx_needs.logging import log_warning
from sphinx_needs.need_content import resolve_content_parser
from sphinx_needs.need_item import NeedItemSource
from sphinx_needs.utils import (
    add_doc,
    coerce_to_boolean,
    import_prefix_link_edit,
    logger,
)


class Needimport(nodes.General, nodes.Element):
    pass


class NeedimportDirective(SphinxDirective):
    has_content = False

    required_arguments = 1
    optional_arguments = 0

    option_spec = {
        "version": directives.unchanged_required,
        "hide": directives.flag,
        "collapse": coerce_to_boolean,
        "ids": directives.unchanged_required,
        "filter": directives.unchanged_required,
        "id_prefix": directives.unchanged_required,
        "tags": directives.unchanged_required,
        "style": directives.unchanged_required,
        "layout": directives.unchanged_required,
        "template": directives.unchanged_required,
        "pre_template": directives.unchanged_required,
        "post_template": directives.unchanged_required,
        "allow_type_coercion": coerce_to_boolean,
        "parse_by_doctype": coerce_to_boolean,
    }

    final_argument_whitespace = True

    @measure_time("needimport")
    def run(self) -> Sequence[nodes.Node]:
        needs_config = NeedsSphinxConfig(self.config)
        needs_schema = SphinxNeedsData(self.env).get_schema()

        version = self.options.get("version")
        filter_string = self.options.get("filter")
        id_prefix = self.options.get("id_prefix", "")
        allow_type_coercion = self.options.get("allow_type_coercion", True)
        parse_by_doctype = self.options.get(
            "parse_by_doctype", needs_config.import_parse_by_doctype
        )

        need_import_path = needs_config.import_keys.get(
            self.arguments[0], self.arguments[0]
        )
        # the file and line the directive is written on: the line every need it
        # imports records (#1349), and where its own warnings are located (#2463)
        written_source, resolved = directive_line(self)
        location = self._written_location(written_source, resolved)

        # check if given argument is downloadable needs.json path
        url = urlparse(need_import_path)
        # a file:// URL has no netloc: it is fetched as the external reader fetches it
        if url.scheme and (url.netloc or url.scheme == "file"):
            # download needs.json
            logger.info(f"Downloading needs.json from url {need_import_path}")
            source_name = source_label = need_import_path
            imported = NeedSourceHop(
                kind="file",
                physical=NeedSourcePhysical(url=need_import_path),
                language=os.path.splitext(url.path)[1] or None,
            )
            s = requests.Session()
            s.mount("file://", FileAdapter())
            try:
                response = s.get(need_import_path)
                response.raise_for_status()
            except Exception as e:
                return self._refuse(
                    f"Could not load needs import file {need_import_path}: "
                    f"getting it failed: {e}",
                    location,
                )
            read = partial(exchange.parse, response.content)
        else:
            logger.info(f"Importing needs from {need_import_path}")

            correct_need_import_path = self.env.relfn2path(
                need_import_path, self.env.docname
            )[1]
            source_name = correct_need_import_path
            imported = NeedSourceHop(
                kind="file",
                physical=physical_for(self.env.srcdir, correct_need_import_path),
                language=os.path.splitext(correct_need_import_path)[1] or None,
            )
            # the file relative to the source directory, as its hop records it
            source_label = (
                imported.physical.path
                if imported.physical is not None and imported.physical.path is not None
                else correct_need_import_path
            )

            # noted before the file is looked for, so that a file that is missing or
            # cannot be read now is read again once it exists or changes (Sphinx takes
            # a noted dependency that does not exist as changed)
            self.env.note_dependency(correct_need_import_path)

            if not os.path.exists(correct_need_import_path):
                return self._refuse(
                    f"Could not load needs import file {correct_need_import_path}",
                    location,
                )
            read = partial(exchange.load, correct_need_import_path)

        try:
            # a draft 2a1 file is read too: reading it is harmless, only writing one is
            # behind needs_json_format_version
            selected = read().select_version(version, drafts=READ_DRAFTS)
        except exchange.ExchangeError as err:
            return self._refuse(
                f"Could not load needs import file {source_name}: {err.message}",
                location,
            )
        records = selected.records()
        for diagnostic in (
            *selected.diagnostics,
            *(d for r in records for d in r.diagnostics),
        ):
            log_warning(
                logger,
                f"Needs import file {source_name}: {diagnostic.message} "
                f"(at {diagnostic.path})",
                "needimport",
                location=location,
            )

        # note this is not exactly NeedsInfoType, because the export removes/adds some keys
        all_needs: dict[str, dict[str, Any]] = {r.key: r.fields for r in records}
        # a 2a1 record's hops, the need's upstream: a hop with no origin is the writing
        # project's, else the file's as this directive names it
        origin = writing_project(selected.data) or source_label
        upstream = {r.key: r.source for r in records}
        needs_list = all_needs

        if ids := self.options.get("ids"):
            id_list = [i.strip() for i in ids.split(",") if i.strip()]
            if absent := [i for i in id_list if i not in all_needs]:
                log_warning(
                    logger,
                    f"Needs import file {source_name} has no needs with the ids "
                    f"{absent!r}",
                    "needimport",
                    location=location,
                )
            needs_list = {key: all_needs[key] for key in id_list if key in all_needs}

        # Filter imported needs
        if filter_string is not None:
            needs_list_filtered = {}
            filter_error: Exception | None = None
            for key, need in needs_list.items():
                try:
                    if filter_import_item(need, needs_config, filter_string):
                        needs_list_filtered[key] = need
                except Exception as e:
                    # each need is still filtered on its own; the error is reported once
                    filter_error = filter_error or e
            if filter_error is not None:
                log_warning(
                    logger,
                    f"needimport: {filter_error}",
                    "needimport",
                    location=location,
                )
            needs_list = needs_list_filtered

        # tags update
        if tags := _split_tags(self.options.get("tags", "")):
            for need in needs_list.values():
                # a record may have no tags, or give them as a string: that is
                # extended (an empty one is no tags), and ``add_need`` converts it as
                # it converts any string of tags. Without coercion it refuses any
                # string, so the record's own, empty or not, is left for it to name;
                # as is any other value it refuses
                need_tags = need.get("tags")
                if need_tags is None:
                    need["tags"] = tags
                elif isinstance(need_tags, list):
                    need["tags"] = need_tags + tags
                elif isinstance(need_tags, str) and allow_type_coercion:
                    need["tags"] = (
                        f"{need_tags},{','.join(tags)}" if need_tags else tags
                    )

        # a link is prefixed when its target is a need of the file, imported here or not
        import_prefix_link_edit(
            needs_list,
            id_prefix,
            needs_schema.iter_link_field_names(),
            known_ids=all_needs,
        )

        # collect keys for warning logs, so that we only log one warning per key
        unknown_keys: set[str] = set()

        # directive options that can be override need fields
        override_options = (
            "collapse",
            "style",
            "layout",
            "template",
            "pre_template",
            "post_template",
        )

        # parsing by doctype: the content is anchored at the directive, in the file and
        # at the line it is written on, whatever the page's markup
        content_source: tuple[str, int] | None = None
        if parse_by_doctype:
            path, line = self.get_source_info()
            if path and isinstance(line, int) and line >= 1:
                content_source = (str(path), line)
        # a template the project gives through ``needs_fields`` is applied when the need
        # is created, after the markup is chosen here: a default, or a predicate, of any
        # declaration of the field, global or a need type's (which may not apply to the
        # need -- an over-approximation; which one applies is only known there), counts
        # as the need's template
        project_template = needs_schema.declares_default("template")
        # a record's template names are the PRODUCER's: its ``content`` is already the
        # rendered text, so its ``template`` and ``jinja_content`` are never applied
        # again (rendering it again wrapped it twice, rendered Jinja twice, or lost the
        # need where this project has no such template). Its ``pre_template`` and
        # ``post_template`` are still applied where this project has the template, with
        # a deprecation (until 10.0); the directive's own options, and this project's
        # defaults, decorate every imported need as they always have
        template_root = Path(str(self.env.srcdir))
        record_decorations: dict[tuple[str, str], bool] = {}
        deprecated_decorations: set[tuple[str, str]] = set()
        # each distinct doctype is resolved once: to ``None`` if the project parses it,
        # else to the reason it does not
        refusals: dict[str, str | None] = {}
        # the unparseable doctypes of the needs with content, and why, in import order
        fallbacks: dict[str, str] = {}

        # every need of the directive shares its hops: the imported file (resolved),
        # then the file and page the directive is written on
        hops = directive_hops(self, first=(imported,))
        need_nodes = []
        for key, need_params in needs_list.items():
            record = dict(need_params)
            # ``ingest_need_record`` drops the keys the project does not know AFTER
            # these are written; every override option (and ``hide``) is a field the
            # project knows and imports, so they survive the drop, as they did when
            # it happened before them here
            if "template" not in self.options:
                record.pop("template", None)
            record.pop("jinja_content", None)
            for decoration in ("pre_template", "post_template"):
                if decoration in self.options or not (name := record.get(decoration)):
                    continue
                if not isinstance(name, str):
                    continue
                # not ``key``: that names the record in the loop around this one
                decorated = (decoration, name)
                if decorated not in record_decorations:
                    record_decorations[decorated] = self._importer_has_template(
                        needs_config, name, template_root
                    )
                if record_decorations[decorated]:
                    deprecated_decorations.add(decorated)
                else:
                    del record[decoration]
            for override_option in override_options:
                if override_option in self.options:
                    record[override_option] = self.options[override_option]
            if "hide" in self.options:
                record["hide"] = True

            # Replace id, to get unique ids; an empty key is no id, whatever the prefix
            # (the record path refuses it only before the prefix is added)
            key_is_empty = not record["id"]
            need_id = record["id"] = id_prefix + record["id"]
            if key_is_empty:
                log_warning(
                    logger,
                    f"Need {need_id!r} could not be imported: id is empty",
                    "import_need",
                    location=location,
                )
                continue

            # its line is the one the directive is written on, as a need directive's
            # (#1349); the parser's line anchors the text parsed for the need
            need_source = NeedItemSource(
                hops,
                lineno=resolved or self.lineno,
                parser_lineno=self.lineno,
                is_import=True,
                upstream=upstream_hops(upstream[key], origin=origin),
            )

            # a template is a file of the importing project, written in the page's
            # markup: a need rendered through one (the directive's ``:template:``, or
            # one the project gives) is parsed as the page's, as its pre and post
            # templates always are; a record's own ``template`` is not applied, so
            # its content is parsed by its doctype like any other
            content_markup = None
            if parse_by_doctype and not record.get("template") and not project_template:
                content_markup = self._content_markup(record, refusals, fallbacks)

            try:
                need_node, _ = ingest_need_record(
                    self.env.app,
                    self.state,
                    record,
                    need_source=need_source,
                    content_markup=content_markup,
                    content_source=content_source if content_markup else None,
                    allow_type_coercion=allow_type_coercion,
                    # a need that cannot be created still reports its unknown keys
                    unknown_keys=unknown_keys,
                )
            except InvalidNeedException as err:
                log_warning(
                    logger,
                    f"Need {need_id!r} could not be imported: {err.message}",
                    "import_need",
                    location=location,
                )
            else:
                need_nodes.extend(need_node)

        for decoration, name in sorted(deprecated_decorations):
            log_warning(
                logger,
                f"Imported needs name the {decoration} {name!r} in their records, which "
                "this project renders: applying a record's pre or post template is "
                "deprecated, and stops in sphinx-needs 10.0. Name it on the needimport "
                f"directive (:{decoration}: {name}), or give it as a default of "
                f"needs_fields ({decoration}), to keep it.",
                "deprecated",
                location=location,
            )

        for doctype, reason in fallbacks.items():
            log_warning(
                logger,
                f"Imported needs declare doctype {doctype!r}, which this project "
                f"cannot parse content in: {reason}. Their content was parsed as this "
                "page's markup instead. Add the suffix to source_suffix with a "
                "reStructuredText or MyST parser, or set :parse_by_doctype: false.",
                "import_doctype",
                location=location,
            )

        if unknown_keys:
            log_warning(
                logger,
                f"Unknown keys in import need source: {sorted(unknown_keys)!r}",
                "unknown_import_keys",
                location=location,
            )

        add_doc(self.env, self.env.docname)

        return need_nodes

    def _importer_has_template(
        self, needs_config: NeedsSphinxConfig, name: str, template_root: Path
    ) -> bool:
        """Whether this project has the need template *name*.

        A template that exists is a dependency of the document, so editing or deleting
        it re-reads the page. One that does not is NOT noted: Sphinx takes a missing
        dependency as changed on every build, and a record naming the producer's
        template is this project's normal state, not a fault to fix. It is recorded as
        a probe of the document instead, which re-reads the page once the file exists
        (:func:`~sphinx_needs._need_templates.reread_on_template_inputs_change`). (A
        noted template folder would not do: Sphinx 9 takes a dependency that is not a
        file as missing.)
        """
        path = template_path(needs_config, name, template_root)
        if path is None:
            return False
        if path.is_file():
            self.env.note_dependency(str(path))
            return True
        SphinxNeedsData(self.env).template_probes.setdefault(
            self.env.docname, set()
        ).add(str(path))
        return False

    def _written_location(
        self, source: str | None, line: int | None
    ) -> str | tuple[str, int]:
        """Where every warning of the directive is located: ``source`` and ``line``,
        the file and line it is written on (:func:`directive_line`), the file made
        absolute, as Sphinx makes a node's (docutils records an included file
        relative to the working directory).

        A needimport another extension generates is written in no file: its source is
        ``<unknown>``, empty, or a name that is no file (``<generated>``). It keeps
        the page and the parser's line, as before #2463, which at least names the
        page that holds it.
        """
        if source and line and os.path.isfile(absolute := os.path.abspath(source)):
            return f"{absolute}:{line}"
        return (self.env.docname, self.lineno)

    def _refuse(
        self, message: str, location: str | tuple[str, int]
    ) -> list[nodes.Node]:
        """Report a file no need can be imported from: one warning at the directive,
        and the warning node in its place."""
        log_warning(
            logger,
            message,
            "needimport",
            location=location,
        )
        warning = nodes.warning()
        warning += nodes.paragraph(text=message)
        return [warning]

    def _content_markup(
        self,
        record: dict[str, Any],
        refusals: dict[str, str | None],
        fallbacks: dict[str, str],
    ) -> str | None:
        """The markup to parse a record's content in: its ``doctype``, if the project
        parses that; else ``None``, the page's markup.

        A ``doctype`` that is empty, missing or not a ``str`` says nothing, and is the
        page's markup silently. One that the project does not parse is noted in
        ``fallbacks``, with the reason, for a record whose content is not blank and is
        rendered: a hidden need's content is never parsed.
        """
        doctype = record.get("doctype")
        if not isinstance(doctype, str) or not doctype:
            return None
        if doctype not in refusals:
            try:
                resolve_content_parser(self.env.app, doctype)
            except InvalidNeedException as err:
                refusals[doctype] = err.message.removeprefix(
                    "Content markup "
                ).removesuffix(
                    "; only reStructuredText and MyST parsers are supported."
                )
            else:
                refusals[doctype] = None
        if (reason := refusals[doctype]) is None:
            return doctype
        content = record.get("content") or ""
        blank = isinstance(content, str) and not content.strip()
        if not blank and not record.get("hide"):
            fallbacks.setdefault(doctype, reason)
        return None

    @property
    def docname(self) -> str:
        return self.env.docname


def _split_tags(tags: str) -> list[str]:
    """The tags of a ``;`` or ``,`` separated string, stripped, empty ones dropped."""
    return [tag.strip() for tag in re.split("[;,]", tags) if tag.strip()]


class VersionNotFound(BaseException):
    """No longer raised: a needs.json without the version asked for is one
    ``needs.needimport`` warning, and the directive imports nothing."""


class CorruptedNeedsFile(BaseException):
    """No longer raised: a needs.json that cannot be read is one ``needs.needimport``
    warning, and the directive imports nothing."""


class NeedimportException(BaseException):
    """No longer raised: a needs.json that cannot be downloaded is one
    ``needs.needimport`` warning, and the directive imports nothing."""
