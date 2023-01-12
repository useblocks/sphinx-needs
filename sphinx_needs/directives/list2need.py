from typing import Any, Sequence

from docutils import nodes
from docutils.parsers.rst import Directive, directives

from sphinx_needs.api import add_need
from sphinx_needs.utils import add_doc


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
        env = self.state.document.settings.env

        nodes = []

        for x in range(0, 10):

            need_options = {
                "need_type": "feature",
                "title": "Test title",
                "id": f"TEST-00{x}",
                "content": "test",
                "status": "",
                "tags": "",
                "hide": "",
                "template": "",
                "pre_template": "",
                "post_template": "",
                "collapse": "",
                "style": "",
                "layout": "",
                "delete": "",
                "jinja_content": "",
            }

            need_node = add_need(
                env.app,
                self.state,
                env.docname,
                self.lineno,
                **need_options,  # type: ignore
            )
            nodes.extend(need_node)
        add_doc(env, env.docname)

        return nodes
