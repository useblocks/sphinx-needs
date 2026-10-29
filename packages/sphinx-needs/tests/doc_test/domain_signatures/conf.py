from sphinx.addnodes import desc_name
from sphinx.directives import ObjectDescription

extensions = ["sphinx_needs"]

needs_build_json = True


class NamelessObject(ObjectDescription):
    """An object whose signature has an empty ``desc_name``."""

    def handle_signature(self, sig, signode):
        signode += desc_name()
        return sig


def setup(app):
    app.add_directive("nameless", NamelessObject)
