from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from collections.abc import Set as AbstractSet
from contextlib import suppress
from typing import Any

from docutils import nodes
from docutils.parsers.rst import directives
from docutils.statemachine import StringList
from sphinx.errors import SphinxError, SphinxWarning
from sphinx.util.docutils import SphinxDirective

from sphinx_needs.api import InvalidNeedException, add_need
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.directives.need import _get_title
from sphinx_needs.logging import WarningSubTypes, get_logger, log_warning
from sphinx_needs.need_item import NeedItemSourceDirective
from sphinx_needs.nodes import Need
from sphinx_needs.utils import add_doc, coerce_to_boolean

LOGGER = get_logger(__name__)

LINE_REGEX = re.compile(
    r"(?P<indent>[^\S\n]*)\*\s*(?P<text>.*)|[\S\*]*(?P<more_text>.*)"
)
ID_REGEX = re.compile(
    r"(\((?P<need_id>[^\"'=\n]+)?\))"
)  # Exclude some chars, which are used by option list
OPTION_AREA_REGEX = re.compile(r"\(\((.*)\)\)")
OPTIONS_REGEX = re.compile(r"([^=,\s]*)=[\"']([^\"]*)[\"']")

#: Need options an inline ``((name="value"))`` may set, on top of the extra fields
#: and link types the project configures. Mirrors what the need directives accept.
CORE_OPTIONS = frozenset(
    {
        "collapse",
        "constraints",
        "hide",
        "id",
        "jinja_content",
        "layout",
        "post_template",
        "pre_template",
        "status",
        "style",
        "tags",
        "template",
    }
)


class List2Need(nodes.General, nodes.Element):
    pass


class List2NeedDirective(SphinxDirective):
    """Create need objects out ouf a given list,
    where each list entry is used to create a single need.
    """

    has_content = True

    required_arguments = 0
    optional_arguments = 0
    final_argument_whitespace = True

    @staticmethod
    def presentation(argument: str) -> Any:
        return directives.choice(argument, ("nested", "standalone"))

    option_spec = {
        "types": directives.unchanged,
        "delimiter": directives.unchanged,
        "presentation": directives.unchanged,
        "links-down": directives.unchanged,
        "tags": directives.unchanged,
    }

    def run(self) -> Sequence[nodes.Node]:
        env = self.env
        needs_config = NeedsSphinxConfig(env.config)

        presentation = self.options.get("presentation")
        if not presentation:
            presentation = "nested"
        if presentation not in ["nested", "standalone"]:
            raise SphinxWarning("'presentation' must be 'nested' or 'standalone'")

        delimiter = self.options.get("delimiter")
        if not delimiter:
            delimiter = "."

        content_raw = "\n".join(self.content)
        types_raw = self.options.get("types")
        if not types_raw:
            raise SphinxWarning("types must be set.")
        # Create a dict, which delivers the need-type for the later level
        types = {}
        types_raw_list = [x.strip() for x in types_raw.split(",")]
        conf_types = [x["directive"] for x in needs_config.types]
        for x in range(0, len(types_raw_list)):
            types[x] = types_raw_list[x]
            if types[x] not in conf_types:
                raise SphinxError(
                    f"Unknown type configured: {types[x]}. Allowed are {', '.join(conf_types)}"
                )

        down_links_raw = self.options.get("links-down")
        if down_links_raw is None or down_links_raw == "":
            down_links_raw = ""

        # Create a dict, which delivers the need-link for the later level
        down_links_types = {}
        if down_links_raw is None or down_links_raw == "":
            down_links_raw_list = []
        else:
            down_links_raw_list = [x.strip() for x in down_links_raw.split(",")]
        needs_schema = SphinxNeedsData(self.env).get_schema()
        # the options an item may set inline, on top of the ones list2need computes
        known_options = (
            CORE_OPTIONS
            | set(needs_schema.iter_extra_field_names())
            | set(needs_schema.iter_link_field_names())
        )
        link_types = [link.name for link in needs_schema.iter_link_fields()]
        for i, down_link_raw in enumerate(down_links_raw_list):
            down_links_types[i] = down_link_raw
            if down_link_raw not in link_types:
                raise SphinxError(
                    f"Unknown link configured: {down_link_raw}. "
                    f"Allowed are {', '.join(link_types)}"
                )

        # Retrieve tags defined at list level
        tags = self.options.get("tags", "")

        list_needs = []
        # Storing the data in a sorted list
        for line_index, content_line in enumerate(content_raw.split("\n")):
            # for groups in line.findall(content_raw):
            match = LINE_REGEX.search(content_line)
            if not match:
                continue
            indent, text, more_text = match.groups()

            if text:
                indent = len(indent)
                if not indent % 2 == 0:
                    raise IndentationError(
                        "Indentation for list must be always a multiply of 2."
                    )
                level = int(indent / 2)

                if level not in types:
                    raise SphinxWarning(
                        f"No need type defined for indentation level {level}."
                        f" Defined types {types}"
                    )

                if down_links_types and level > len(down_links_types):
                    raise SphinxWarning(
                        f"Not enough links-down defined for indentation level {level}."
                    )

                splitted_text = text.split(delimiter)
                title = splitted_text[0]

                content = ""
                with suppress(IndexError):
                    content = delimiter.join(
                        splitted_text[1:]
                    )  # Put the content together again

                need_id = None
                need_id_result = ID_REGEX.search(title)
                if need_id_result:
                    need_id = need_id_result.group(2)
                    title = ID_REGEX.sub("", title)
                if need_id is None:
                    # Note the id is hashed from the title *before* any inline option
                    # area is removed from it, which is what the id of a title
                    # carrying options has always been.
                    prefix = ""
                    needs_id_length = needs_config.id_length
                    for need_type in needs_config.types:
                        if need_type["directive"] == types[level]:
                            prefix = need_type["prefix"]
                            break

                    need_id = self.make_hashed_id(prefix, title, needs_id_length)

                need = {
                    "title": title,
                    "need_id": need_id,
                    "type": types[level],
                    # the content is kept line by line, so that every line can be
                    # handed to the need with the source position it was written at
                    "content": [content.lstrip()],
                    "content_lines": [line_index],
                    "level": level,
                    "line": line_index,
                    "options": {},
                }
                list_needs.append(need)
            else:
                more_text = more_text.lstrip()
                if more_text.startswith(":"):
                    # a continuation line is stripped of the indentation it was written
                    # with, so this restores the one indentation a line beginning with
                    # ":" is likely to have needed: the options of a directive written
                    # in the content of an item, which are one field list line each
                    more_text = f"   {more_text}"
                list_needs[-1]["content"].append(more_text)
                list_needs[-1]["content_lines"].append(line_index)

        # Extract the inline options of every item
        for list_need in list_needs:
            # Search for meta data in the complete title/content
            content_text = "\n".join(list_need["content"])
            search_string = list_need["title"] + content_text
            result = OPTION_AREA_REGEX.search(search_string)
            if result is not None:  # An option was found
                option_str = result.group(1)  # We only deal with the first finding
                option_result = OPTIONS_REGEX.findall(option_str)
                list_need["options"] = {x[0]: x[1] for x in option_result}

                # Remove possible option-strings from title and content.
                # The option area cannot span a line break, so substituting on the
                # joined content and splitting it up again preserves the line count,
                # and with it every line's mapping back to its source position.
                list_need["title"] = OPTION_AREA_REGEX.sub("", list_need["title"])
                list_need["content"] = OPTION_AREA_REGEX.sub("", content_text).split(
                    "\n"
                )

            # Add tags defined at list level (if exists) to the ones potentially defined in the content
            if tags:
                if "options" not in list_need:
                    list_need["options"] = {}
                current_tags = list_need["options"].get("tags", "")
                if current_tags:
                    list_need["options"]["tags"] = current_tags + "," + tags
                else:
                    list_need["options"]["tags"] = tags

            # an explicitly given id wins over the one derived from the title,
            # and has to be known before the links-down of any other item are built.
            # An empty one is handed on as it stands, so that it is refused with a
            # diagnostic instead of being silently replaced by the title hash.
            if (given_id := list_need["options"].pop("id", None)) is not None:
                list_need["need_id"] = given_id

        # Finally creating the needs
        node_list: list[nodes.Node] = []
        # the needs a nested item can be placed inside, innermost last
        open_needs: list[tuple[int, Need]] = []
        created = False
        for index, list_need in enumerate(list_needs):
            options = dict(list_need["options"])

            need_links_down = self.get_down_needs(list_needs, index)
            if (
                down_links_types
                and list_need["level"] in down_links_types
                and need_links_down
            ):
                links_down_type = down_links_types[list_need["level"]]
                given = options.get(links_down_type)
                joined = ", ".join(need_links_down)
                options[links_down_type] = f"{given}, {joined}" if given else joined

            need_nodes = self._create_need(list_need, options, known_options)
            created = created or bool(need_nodes)

            if presentation == "nested":
                while open_needs and open_needs[-1][0] >= list_need["level"]:
                    open_needs.pop()
                if open_needs:
                    parent_node = open_needs[-1][1]
                    parent_node += need_nodes
                else:
                    node_list += need_nodes
                for node in need_nodes:
                    if isinstance(node, Need):
                        # a hidden need is taken out of the document once it has been
                        # read, so a child placed inside one would be rendered nowhere
                        # and referenced by an anchor that never reaches the page
                        if not node.get("hidden"):
                            open_needs.append((list_need["level"], node))
                        break
            else:
                node_list += need_nodes

        if created:
            add_doc(self.env, self.env.docname)

        return node_list

    def _create_need(
        self,
        list_need: dict[str, Any],
        options: dict[str, str],
        known_options: AbstractSet[str],
    ) -> list[nodes.Node]:
        """Create a single need from one parsed list item.

        :param list_need: The parsed item.
        :param options: Its inline options, plus any ``links-down`` values.
        :param known_options: The option names a need accepts.
        :return: The nodes of the created need, or nothing if it could not be created.
        """
        lineno = self._source_line(list_need["line"])
        location = (self.env.docname, lineno)
        needs_config = NeedsSphinxConfig(self.env.config)

        def warn(message: str, code: WarningSubTypes = "directive") -> None:
            log_warning(LOGGER, message, code, location=location)

        # the options a need directive reads as a boolean rather than as a string
        flags: dict[str, bool] = {}
        for name in ("delete", "jinja_content", "title_from_content"):
            if name not in options:
                continue
            try:
                flags[name] = coerce_to_boolean(options.pop(name))
            except ValueError as err:
                warn(f"Invalid value for {name!r} option: {err}")
                return []
        if flags.get("delete"):  # the item asked for no need to be created
            return []

        kwargs: dict[str, Any] = {}
        if "jinja_content" in flags:
            kwargs["jinja_content"] = flags["jinja_content"]

        for key, option_value in options.items():
            if key in known_options:
                kwargs[key] = option_value
            else:
                warn(f"Unknown option '{key}'")

        content, lineno_content = self._content(list_need)

        # the title is decided exactly as it is for a need directive: an item whose
        # own title is empty is one written without a directive argument
        title, full_title = _get_title(
            [list_need["title"]] if list_need["title"].strip() else [],
            content,
            title_optional=needs_config.title_optional,
            title_from_content=flags.get(
                "title_from_content", needs_config.title_from_content
            ),
            max_title_length=needs_config.max_title_length,
            warn=warn,
        )

        try:
            return add_need(
                app=self.env.app,
                state=self.state,
                need_source=NeedItemSourceDirective(
                    docname=self.env.docname,
                    lineno=lineno,
                    lineno_content=lineno_content,
                ),
                need_type=list_need["type"],
                title=title,
                full_title=full_title,
                id=list_need["need_id"],
                content=content,
                **kwargs,
            )
        except InvalidNeedException as err:
            warn(f"Need could not be created: {err.message}", "create_need")
            return []

    def _content(self, list_need: dict[str, Any]) -> tuple[StringList, int]:
        """Build the source mapped content of one parsed list item.

        Blank lines are stripped from both ends, as the parser does for the content
        block of any directive, so that an item whose title carries no content at all
        contributes an empty content rather than a leading empty line.

        :return: The content, and the source line its first line was written on.
        """
        lines: list[str] = list(list_need["content"])
        indexes: list[int] = list(list_need["content_lines"])
        while lines and not lines[0].strip():
            del lines[0], indexes[0]
        while lines and not lines[-1].strip():
            del lines[-1], indexes[-1]

        items = [self._source_info(index) for index in indexes]
        content = StringList(
            lines, source=str(self.env.doc2path(self.env.docname)), items=items
        )
        # ``items`` holds 0-based offsets, the need wants a 1-based line number
        lineno_content = (
            items[0][1] + 1 if items else self._source_line(list_need["line"])
        )
        return content, lineno_content

    def _content_is_source_mapped(self) -> bool:
        """Whether the content lines carry their true position in the source.

        Under the reStructuredText parser they do, and that mapping is authoritative:
        it survives ``.. include::`` and anything else that moves the parser's flat
        line counter away from the file being read.

        Under myst-parser they do not. Its mock state machine hands the directive a
        content block whose entries are numbered from zero, so line *i* reports
        offset *i* regardless of where the fence was written. There is no expression
        for "the source line of content line *i*" that is correct in both hosts, so
        the two are told apart here, once per directive, by whether the first content
        line claims to be at offset 0 -- which real reStructuredText content never is,
        the directive marker itself always occupying an earlier line.
        """
        try:
            _, offset = self.content.info(0)
        except (IndexError, TypeError):
            return False
        return bool(offset)

    def _source_info(self, index: int) -> tuple[str, int]:
        """Return the source and 0-based source offset of content line ``index``."""
        if self._content_is_source_mapped():
            source, offset = self.content.info(index)
            return str(source), int(offset)
        # myst-parser: rebuild the offset from the position of the directive itself
        _, lineno = self.get_source_info()
        if lineno is None:
            lineno = self.lineno
        return (
            str(self.env.doc2path(self.env.docname)),
            lineno + self.content_offset + index,
        )

    def _source_line(self, index: int) -> int:
        """Return the 1-based source line number of content line ``index``."""
        return self._source_info(index)[1] + 1

    def make_hashed_id(self, type_prefix: str, title: str, id_length: int) -> str:
        hashable_content = title
        return "{}{}".format(
            type_prefix,
            hashlib.sha1(hashable_content.encode("UTF-8"))
            .hexdigest()
            .upper()[:id_length],
        )

    def get_down_needs(self, list_needs: list[Any], index: int) -> list[str]:
        """
        Return all needs which are directly under the one given by the index
        """
        current_level = list_needs[index]["level"]

        down_links = []
        next_index = index + 1
        try:
            next_need = list_needs[next_index]
        except IndexError:
            return []

        while next_need:
            if next_need["level"] == current_level + 1:
                down_links.append(next_need["need_id"])

            if next_need["level"] == current_level:
                break  # No further needs below this need

            next_index += 1
            try:
                next_need = list_needs[next_index]
            except IndexError:
                next_need = None

        return down_links
