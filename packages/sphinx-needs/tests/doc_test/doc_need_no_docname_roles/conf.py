from sphinx.util.docutils import SphinxDirective

from sphinx_needs.api import add_need

extensions = ["sphinx_needs"]


class NoDocname(SphinxDirective):
    """Add a need through the API with no document, as ``add_need`` allows."""

    def run(self):
        return add_need(
            self.env.app,
            self.state,
            None,
            None,
            need_type="req",
            title="Need without a document",
            id="R_NODOC",
            # so that R_DOC has a backlink from it, for need_incoming
            links=["R_DOC"],
        )


def setup(app):
    app.add_directive("nodocname", NoDocname)
