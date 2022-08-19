from typing import Sequence

from docutils import nodes
from sphinx.application import Sphinx

from sphinx_needs.directives.need import Need
from sphinx_needs.directives.needuml import NeedumlDirective
from sphinx_needs.utils import unwrap


class NeedarchDirective(NeedumlDirective):
    """
    Directive inherits from Needuml, but works only inside a need object.
    """

    def run(self) -> Sequence[nodes.Node]:
        return NeedumlDirective.run(self)


def process_needarch(app: Sphinx, doctree: nodes.document, fromdocname: str) -> None:
    builder = unwrap(app.builder)
    env = unwrap(builder.env)

    # check if needarch only used inside a need
    if hasattr(env, "needs_all_needumls"):
        for needuml in env.needs_all_needumls.values():  # type: ignore[attr-defined]
            if needuml["is_arch"] and not (
                needuml["target_node"].parent and isinstance(needuml["target_node"].parent, Need)
            ):
                raise NeedArchException("Directive needarch can only be used inside a need.")


class NeedArchException(BaseException):
    """Errors during Needarch handling."""
