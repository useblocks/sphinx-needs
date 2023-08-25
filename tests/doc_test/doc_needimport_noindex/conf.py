import os

project = "needs test docs"
master_doc = "intro"

extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]

# figures, tables and code-blocks are automatically numbered if they have a caption
numfig = True


plantuml = "java -Djava.awt.headless=true -jar %s" % os.path.join(
    os.path.dirname(__file__), "..", "utils", "plantuml.jar"
)
plantuml_output_format = "svg"
