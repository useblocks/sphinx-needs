from docutils import nodes
from sphinx.addnodes import desc_name, desc_signature
from sphinx.directives import ObjectDescription
from sphinx.util.docutils import SphinxDirective

extensions = ["sphinx_needs"]

needs_build_json = True


class NamelessObject(ObjectDescription):
    """An object whose signature has an empty ``desc_name``."""

    def handle_signature(self, sig, signode):
        signode += desc_name()
        return sig


class OutsideSignature(SphinxDirective):
    """A ``desc_signature`` outside any ``desc``, before the content it holds.

    No Sphinx domain writes one: a signature names the object of the ``desc`` it is in.
    """

    has_content = True

    def run(self):
        container = nodes.container()
        signature = desc_signature()
        signature += desc_name("outside", "outside")
        container += signature
        self.state.nested_parse(self.content, self.content_offset, container)
        return [container]


def setup(app):
    app.add_directive("nameless", NamelessObject)
    app.add_directive("outside-signature", OutsideSignature)
