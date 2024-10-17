"""
Provide a role which executes a dynamic function.
"""

from __future__ import annotations

from docutils import nodes
from sphinx.application import Sphinx
from sphinx.environment import BuildEnvironment
from sphinx.util.docutils import SphinxRole

from sphinx_needs.data import NeedsInfoType, SphinxNeedsData
from sphinx_needs.logging import get_logger, log_warning
from sphinx_needs.utils import add_doc

LOGGER = get_logger(__name__)


class NeedFuncRole(SphinxRole):
    """Role for creating ``NeedFunc`` node."""

    def __init__(self, *, with_brackets: bool = False) -> None:
        """Initialize the role.

        :param with_brackets: If True, the function is expected to be wrapped in brackets ``[[]]``.
        """
        self.with_brackets = with_brackets
        super().__init__()

    def run(self) -> tuple[list[nodes.Node], list[nodes.system_message]]:
        add_doc(self.env, self.env.docname)
        node = NeedFunc(
            self.rawtext,
            nodes.literal(self.rawtext, self.text),
            with_brackets=self.with_brackets,
            **self.options,
        )
        self.set_source_info(node)
        if self.with_brackets:
            from sphinx_needs.functions.functions import FUNC_RE

            msg = "The `need_func` role is deprecated. "
            if func_match := FUNC_RE.search(node.astext()):
                func_call = func_match.group(1)
                msg += f"Replace with :ndf:`{func_call}` instead."
            else:
                msg += "Replace with ndf role instead."
            log_warning(LOGGER, msg, "deprecated", location=node)
        return [node], []


class NeedFunc(nodes.Inline, nodes.Element):
    @property
    def with_brackets(self) -> bool:
        """Return the function with brackets."""
        return self.get("with_brackets", False)  # type: ignore[no-any-return]

    def get_text(self, env: BuildEnvironment, need: NeedsInfoType | None) -> nodes.Text:
        """Execute function and return result."""
        from sphinx_needs.functions.functions import check_and_get_content, execute_func

        if not self.with_brackets:
            func_return = execute_func(
                env.app,
                need,
                SphinxNeedsData(env).get_needs_view(),
                self.astext(),
                self,
            )
            if isinstance(func_return, list):
                func_return = ", ".join(str(el) for el in func_return)

            return nodes.Text("" if func_return is None else str(func_return))

        result = check_and_get_content(self.astext(), need, env, self)

        return nodes.Text(str(result))


def process_need_func(
    app: Sphinx,
    doctree: nodes.document,
    _fromdocname: str,
    found_nodes: list[nodes.Element],
) -> None:
    node_need_func: NeedFunc
    for node_need_func in found_nodes:  # type: ignore[assignment]
        new_node_func = node_need_func.get_text(app.env, None)
        node_need_func.replace_self(new_node_func)
