from sphinx.util.docutils import SphinxDirective

from sphinx_needs.api import add_need

extensions = ["sphinx_needs"]

# link text is the title and id, so a role showing only the id is told apart
needs_show_link_title = True


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


class External(SphinxDirective):
    """An external need, for the links each role still makes to one."""

    def run(self):
        return add_need(
            self.env.app,
            self.state,
            None,
            None,
            need_type="req",
            title="External need",
            id="R_EXT",
            is_external=True,
            external_url="https://example.com/R_EXT.html",
            links=["R_DOC"],
        )


def setup(app):
    app.add_directive("nodocname", NoDocname)
    app.add_directive("externalneed", External)
