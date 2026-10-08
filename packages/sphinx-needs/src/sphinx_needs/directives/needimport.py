from __future__ import annotations

import json
import os
import re
from collections.abc import Sequence
from typing import Any
from urllib.parse import urlparse

import requests
from docutils import nodes
from docutils.parsers.rst import directives
from requests_file import FileAdapter
from sphinx.util.docutils import SphinxDirective

from sphinx_needs.api import InvalidNeedException, ingest_need_record
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.debug import measure_time
from sphinx_needs.filter_common import filter_import_item
from sphinx_needs.logging import log_warning
from sphinx_needs.need_content import resolve_content_parser
from sphinx_needs.need_item import NeedItemSourceImport
from sphinx_needs.needsfile import SphinxNeedsFileException, check_needs_data
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
            s = requests.Session()
            s.mount("file://", FileAdapter())
            try:
                response = s.get(need_import_path)
                needs_import_list = (
                    response.json()
                )  # The downloaded file MUST be json. Everything else we do not handle!
            except Exception as e:
                raise NeedimportException(
                    f"Getting {need_import_path} didn't work. Reason: {e}."
                )
        else:
            logger.info(f"Importing needs from {need_import_path}")

            correct_need_import_path = self.env.relfn2path(
                need_import_path, self.env.docname
            )[1]

            if not os.path.exists(correct_need_import_path):
                warning_text = (
                    f"Could not load needs import file {correct_need_import_path}"
                )
                log_warning(
                    logger,
                    warning_text,
                    "needimport",
                    location=(self.env.docname, self.lineno),
                )

                paragraph = nodes.paragraph(text=warning_text)
                warning = nodes.warning()
                warning += paragraph
                return [warning]

            try:
                with open(correct_need_import_path) as needs_file:
                    needs_import_list = json.load(needs_file)
            except (OSError, json.JSONDecodeError) as e:
                # TODO: Add exception handling
                raise SphinxNeedsFileException(correct_need_import_path) from e

            self.env.note_dependency(correct_need_import_path)

            errors = check_needs_data(needs_import_list)
            if errors.schema:
                logger.info(
                    f"Schema validation errors detected in file {correct_need_import_path}:"
                )
                for error in errors.schema:
                    logger.info(
                        f"  {error.message} -> {'.'.join(str(p) for p in error.instance_path)}"
                    )

        if version is None:
            try:
                version = needs_import_list["current_version"]
                if not isinstance(version, str):
                    raise KeyError
            except KeyError:
                raise CorruptedNeedsFile(
                    f"Key 'current_version' missing or corrupted in {correct_need_import_path}"
                )
        if version not in needs_import_list["versions"]:
            raise VersionNotFound(
                f"Version {version} not found in needs import file {correct_need_import_path}"
            )

        data = needs_import_list["versions"][version]

        if ids := self.options.get("ids"):
            id_list = [i.strip() for i in ids.split(",") if i.strip()]
            data["needs"] = {
                key: data["needs"][key] for key in id_list if key in data["needs"]
            }

        # note this is not exactly NeedsInfoType, because the export removes/adds some keys
        needs_list: dict[str, dict[str, Any]] = data["needs"]
        if schema := data.get("needs_schema"):
            # Set defaults from schema
            defaults = {
                name: value["default"]
                for name, value in schema["properties"].items()
                if "default" in value
            }
            needs_list = {
                key: {**defaults, **value} for key, value in needs_list.items()
            }

        # Filter imported needs
        needs_list_filtered = {}
        for key, need in needs_list.items():
            if filter_string is None:
                needs_list_filtered[key] = need
            else:
                filter_context = need.copy()

                if "description" in need and not need.get("content"):
                    # legacy versions of sphinx-needs changed "description" to "content" when outputting to json
                    filter_context["content"] = need["description"]
                try:
                    if filter_import_item(filter_context, needs_config, filter_string):
                        needs_list_filtered[key] = need
                except Exception as e:
                    log_warning(
                        logger,
                        f"needimport: Filter {filter_string} not valid. Error: {e}. {self.docname}{self.lineno}",
                        "needimport",
                        location=(self.env.docname, self.lineno),
                    )

        needs_list = needs_list_filtered

        # tags update
        if tags := _split_tags(self.options.get("tags", "")):
            for need in needs_list.values():
                # a record may have no tags, or give them as a string (which
                # ``add_need`` accepts); any other value is left for it to refuse
                need_tags = need.get("tags")
                if need_tags is None:
                    need["tags"] = tags
                elif isinstance(need_tags, list):
                    need["tags"] = need_tags + tags
                elif isinstance(need_tags, str):
                    need["tags"] = _split_tags(need_tags) + tags

        import_prefix_link_edit(
            needs_list, id_prefix, needs_schema.iter_link_field_names()
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
    pass


class CorruptedNeedsFile(BaseException):
    pass


class NeedimportException(BaseException):
    pass
