from __future__ import annotations

import hashlib
import re
from contextlib import suppress
from typing import Any, Sequence

from docutils import nodes
from docutils.parsers.rst import directives
from jinja2 import Template
from sphinx.errors import SphinxError, SphinxWarning
from sphinx.util.docutils import SphinxDirective

from sphinx_needs.config import NeedsSphinxConfig

NEED_TEMPLATE = """.. {{type}}:: {{title}}
   {% if need_id is not none %}:id: {{need_id}}{%endif%}
   {% if set_links_down %}:{{links_down_type}}: {{ links_down|join(', ') }}{%endif%}
   {%- for name, value in options.items() %}:{{name}}: {{value}}
   {% endfor %}

   {{content}}

"""

LINE_REGEX = re.compile(
    r"(?P<indent>[^\S\n]*)\*\s*(?P<text>.*)|[\S\*]*(?P<more_text>.*)"
)
ID_REGEX = re.compile(
    r"(\((?P<need_id>[^\"'=\n]+)?\))"
)  # Exclude some chars, which are used by option list
OPTION_AREA_REGEX = re.compile(r"\(\((.*)\)\)")
OPTIONS_REGEX = re.compile(r"([^=,\s]*)=[\"']([^\"]*)[\"']")


class List2Need(nodes.General, nodes.Element):
    pass


class List2NeedDirective(SphinxDirective):
    """
    Directive to filter needs and present them inside a list, table or diagram.

    .. deprecated:: 0.2.0
       Use needlist, needtable or needdiagram instead
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
        link_types = [x["option"] for x in needs_config.extra_links]
        for i, down_link_raw in enumerate(down_links_raw_list):
            down_links_types[i] = down_link_raw
            if down_link_raw not in link_types:
                raise SphinxError(
                    f"Unknown link configured: {down_link_raw}. "
                    f"Allowed are {', '.join(link_types)}"
                )
        list_needs = []
        # Storing the data in a sorted list
        for content_line in content_raw.split("\n"):
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

                need_id_result = ID_REGEX.search(title)
                if need_id_result:
                    need_id = need_id_result.group(2)
                    title = ID_REGEX.sub("", title)
                else:
                    # Calculate the hash value, so that we can later reuse it
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
                    "content": content.lstrip(),
                    "level": level,
                    "options": {},
                }
                list_needs.append(need)
            else:
                more_text = more_text.lstrip()
                if more_text.startswith(":"):
                    more_text = f"   {more_text}"
                list_needs[-1]["content"] = (
                    f"{list_needs[-1]['content']}\n   {more_text}"
                )

        # Finally creating the rst code
        overall_text = []
        for index, list_need in enumerate(list_needs):
            # Search for meta data in the complete title/content
            search_string = list_need["title"] + list_need["content"]
            result = OPTION_AREA_REGEX.search(search_string)
            if result is not None:  # An option was found
                option_str = result.group(1)  # We only deal with the first finding
                option_result = OPTIONS_REGEX.findall(option_str)
                list_need["options"] = {x[0]: x[1] for x in option_result}

                # Remove possible option-strings from title and content
                list_need["title"] = OPTION_AREA_REGEX.sub("", list_need["title"])
                list_need["content"] = OPTION_AREA_REGEX.sub("", list_need["content"])

            template = Template(NEED_TEMPLATE, autoescape=True)

            data = list_need
            need_links_down = self.get_down_needs(list_needs, index)
            if (
                down_links_types
                and list_need["level"] in down_links_types
                and need_links_down
            ):
                data["links_down"] = need_links_down
                data["links_down_type"] = down_links_types[list_need["level"]]
                data["set_links_down"] = True
            else:
                data["set_links_down"] = False

            text = template.render(**list_need)
            text_list = text.split("\n")
            if presentation == "nested":
                indented_text_list = ["   " * list_need["level"] + x for x in text_list]
                text_list = indented_text_list
            overall_text += text_list

        self.state_machine.insert_input(
            overall_text, self.state_machine.document.attributes["source"]
        )

        return []

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
