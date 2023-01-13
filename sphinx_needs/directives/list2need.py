import re
from contextlib import suppress
from typing import Any, Sequence

from docutils import nodes
from docutils.parsers.rst import Directive, directives
from jinja2 import Template
from sphinx.errors import SphinxError, SphinxWarning

NEED_TEMPLATE = """.. {{type}}:: {{title}}
   {% if need_id is not none %}:id: {{need_id}}{%endif%}

   {{content}}

"""


class List2Need(nodes.General, nodes.Element):  # type: ignore
    pass


class List2NeedDirective(Directive):
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
    }

    def run(self) -> Sequence[nodes.Node]:
        env = self.state.document.settings.env

        presentation = self.options.get("presentation")
        if not presentation:
            presentation = "nested"
        if presentation not in ["nested", "standalone"]:
            raise SphinxWarning("'presentation' must be 'nested' or 'standalone'")

        delimiter = self.options.get("delimiter")
        if not delimiter:
            delimiter = "."

        # line = re.compile(r"(?P<indent>[^\S\n]*)\*\s*(?P<text>.*)")
        # line = re.compile(r"(?P<indent>[^\S\n]*)\*\s*(?P<text>.*)|(?P<more_text>.*)")
        line = re.compile(r"(?P<indent>[^\S\n]*)\*\s*(?P<text>.*)|[\S\*]*(?P<more_text>.*)")
        id_regex = re.compile(r"(\((?P<need_id>.*)?\))")
        content_raw = "\n".join(self.content)
        types_raw = self.options.get("types")
        if not types_raw:
            raise SphinxWarning("types must be set.")

        # Create a dict, which delivers the need-type for the later level
        types = {}
        types_raw_list = [x.strip() for x in types_raw.split(",")]

        conf_types = [x["directive"] for x in env.config.needs_types]
        for x in range(0, len(types_raw_list)):
            types[x] = types_raw_list[x]
            if types[x] not in conf_types:
                raise SphinxError(f"Unknown type configured: {types[x]}. Allowed are {', '.join(conf_types)}")

        list_needs = []
        # Storing the data in a sorted list
        for content_line in content_raw.split("\n"):
            # for groups in line.findall(content_raw):
            match = line.search(content_line)
            if not match:
                continue
            indent, text, more_text = match.groups()

            if text:
                need_id_result = id_regex.search(text)
                if need_id_result:
                    need_id = need_id_result.group(2)
                    text = id_regex.sub("", text)
                else:
                    need_id = None

                splitted_text = text.split(delimiter)
                title = splitted_text[0]
                content = ""
                with suppress(IndexError):
                    content = delimiter.join(splitted_text[1:])  # Put the content together again

                indent = len(indent)
                if not indent % 2 == 0:
                    raise IndentationError("Indentation for list must be always a multiply of 2.")

                level = int(indent / 2)

                if level not in types:
                    raise SphinxWarning(f"No need type defined for identtion level {level}." f" Defined types {types}")

                need = {
                    "title": title,
                    "need_id": need_id,
                    "type": types[level],
                    "content": content.lstrip(),
                    "level": level,
                }
                list_needs.append(need)
            else:
                more_text = more_text.lstrip()
                if more_text.startswith(":"):
                    more_text = f"   {more_text}"
                list_needs[-1]["content"] = f"{list_needs[-1]['content']}\n   {more_text}"

        # Finally creating the rst code
        overall_text = []
        for list_need in list_needs:
            template = Template(NEED_TEMPLATE, autoescape=True)
            text = template.render(**list_need)
            text_list = text.split("\n")
            if presentation == "nested":
                indented_text_list = ["   " * list_need["level"] + x for x in text_list]
                text_list = indented_text_list
            overall_text += text_list

        self.state_machine.insert_input(overall_text, self.state_machine.document.attributes["source"])

        return []
