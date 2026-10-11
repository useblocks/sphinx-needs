from __future__ import annotations

import os
import re
from collections.abc import Sequence
from functools import partial
from typing import Any
from urllib.parse import urlparse

import requests
from docutils import nodes
from docutils.parsers.rst import directives
from requests_file import FileAdapter
from sphinx.util.docutils import SphinxDirective

from sphinx_needs import exchange
from sphinx_needs.api import InvalidNeedException, ingest_need_record
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.debug import measure_time
from sphinx_needs.filter_common import filter_import_item
from sphinx_needs.logging import log_warning
from sphinx_needs.need_content import resolve_content_parser
from sphinx_needs.need_item import NeedItemSourceImport
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

        # check if given argument is downloadable needs.json path
        url = urlparse(need_import_path)
        if url.scheme and url.netloc:
            # download needs.json
            logger.info(f"Downloading needs.json from url {need_import_path}")
            source_name = need_import_path
            s = requests.Session()
            s.mount("file://", FileAdapter())
            try:
                response = s.get(need_import_path)
            except Exception as e:
                raise NeedimportException(
                    f"Getting {need_import_path} didn't work. Reason: {e}."
                )
            read = partial(exchange.parse, response.content)
        else:
            logger.info(f"Importing needs from {need_import_path}")

            correct_need_import_path = self.env.relfn2path(
                need_import_path, self.env.docname
            )[1]
            source_name = correct_need_import_path

            if not os.path.exists(correct_need_import_path):
                return self._refuse(
                    f"Could not load needs import file {correct_need_import_path}"
                )

            # noted before the file is read, so that a file that cannot be read now
            # is read again once it changes
            self.env.note_dependency(correct_need_import_path)
            read = partial(exchange.load, correct_need_import_path)

        try:
            selected = read().select_version(version)
        except exchange.ExchangeError as err:
            return self._refuse(
                f"Could not load needs import file {source_name}: {err.message}"
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
                location=(self.env.docname, self.lineno),
            )

        # note this is not exactly NeedsInfoType, because the export removes/adds some keys
        all_needs: dict[str, dict[str, Any]] = {r.key: r.fields for r in records}
        needs_list = all_needs

        if ids := self.options.get("ids"):
            id_list = [i.strip() for i in ids.split(",") if i.strip()]
            if absent := [i for i in id_list if i not in all_needs]:
                log_warning(
                    logger,
                    f"Needs import file {source_name} has no needs with the ids "
                    f"{absent!r}",
                    "needimport",
                    location=(self.env.docname, self.lineno),
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
                    location=(self.env.docname, self.lineno),
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
        # is created, after the markup is chosen here: a default, or a predicate (which
        # may not match the need -- an over-approximation; which predicate matches is
        # only known there), counts as the need's template
        template_field = needs_schema.get_core_field("template")
        project_template = template_field is not None and (
            template_field.default is not None
            or bool(template_field.predicate_defaults)
        )
        # each distinct doctype is resolved once: to ``None`` if the project parses it,
        # else to the reason it does not
        refusals: dict[str, str | None] = {}
        # the unparseable doctypes of the needs with content, and why, in import order
        fallbacks: dict[str, str] = {}

        need_nodes = []
        for need_params in needs_list.values():
            record = dict(need_params)
            # ``ingest_need_record`` drops the keys the project does not know AFTER
            # these are written; every override option (and ``hide``) is a field the
            # project knows and imports, so they survive the drop, as they did when
            # it happened before them here
            for override_option in override_options:
                if override_option in self.options:
                    record[override_option] = self.options[override_option]
            if "hide" in self.options:
                record["hide"] = True

            # Replace id, to get unique ids
            need_id = record["id"] = id_prefix + record["id"]

            # set location
            need_source = NeedItemSourceImport(
                docname=self.env.docname,
                lineno=self.lineno,
                path=need_import_path,
            )

            # a template is a file of the importing project, written in the page's
            # markup: a need rendered through one is parsed as the page's, as its
            # pre and post templates always are
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
                    location=self.get_location(),
                )
            else:
                need_nodes.extend(need_node)

        for doctype, reason in fallbacks.items():
            log_warning(
                logger,
                f"Imported needs declare doctype {doctype!r}, which this project "
                f"cannot parse content in: {reason}. Their content was parsed as this "
                "page's markup instead. Add the suffix to source_suffix with a "
                "reStructuredText or MyST parser, or set :parse_by_doctype: false.",
                "import_doctype",
                location=self.get_location(),
            )

        if unknown_keys:
            log_warning(
                logger,
                f"Unknown keys in import need source: {sorted(unknown_keys)!r}",
                "unknown_import_keys",
                location=self.get_location(),
            )

        add_doc(self.env, self.env.docname)

        return need_nodes

    def _refuse(self, message: str) -> list[nodes.Node]:
        """Report a file no need can be imported from: one warning at the directive,
        and the warning node in its place."""
        log_warning(
            logger,
            message,
            "needimport",
            location=(self.env.docname, self.lineno),
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
        content = record.get("content") or record.get("description") or ""
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
    """Raised when a remote needs.json cannot be downloaded."""
