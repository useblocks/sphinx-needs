import re
from contextlib import suppress
from typing import Any, Sequence

from docutils import nodes
from docutils.parsers.rst import Directive, directives
from jinja2 import Template
from sphinx.errors import SphinxWarning

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

    @staticmethod
    def format(argument: str) -> Any:
        return directives.choice(argument, ("markdown",))

    option_spec = {
        "types": directives.unchanged,
        "delimiter": directives.unchanged,
        "format": directives.unchanged,
        "presentation": directives.unchanged,
    }

    def run(self) -> Sequence[nodes.Node]:
        presentation = self.options.get("presentation")
        if not presentation:
            presentation = "nested"
        if presentation not in ["nested", "standalone"]:
            raise SphinxWarning("'presentation' must be 'nested' or 'standalone'")

        line = re.compile(r"(?P<indent>[^\S\n]*)\*\s*(?P<text>.*)")
        id_regex = re.compile(r"(\((?P<need_id>.*)?\))")
        content_raw = "\n".join(self.content)
        types_raw = self.options.get("types")
        if not types_raw:
            raise SphinxWarning("types must be set.")

        # Create a dict, which delivers the need-type for the later level
        types = {}
        for x in range(0, len(types_raw)):
            types[x] = types_raw[x]

        list_needs = []

        # Storing the data in a sorted list
        for indent, text in line.findall(content_raw):
            need_id_result = id_regex.search(text)
            if need_id_result:
                need_id = need_id_result.group(2)
                text = id_regex.sub("", text)
            else:
                need_id = None

            splitted_text = text.split(".")
            title = splitted_text[0]
            content = ""
            with suppress(IndexError):
                content = ".".join(splitted_text[1:])

            indent = len(indent)
            if not indent % 2 == 0:
                raise IndentationError("Indentation for list must be always a multiply of 2.")

            level = int(indent / 2)

            need = {"title": title, "need_id": need_id, "type": "feature", "content": content.lstrip(), "level": level}
            list_needs.append(need)

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
