from sphinx.util.docutils import SphinxDirective

from sphinx_needs.api import add_need

extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]

# note, the plantuml command comes from the test suite, not from here
plantuml_output_format = "svg"

needs_flow_engine = "plantuml"


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
            # rendered only by `ref(option="status")`: no diagram card shows a status
            status="status_of_nodoc",
        )


def setup(app):
    app.add_directive("nodocname", NoDocname)
