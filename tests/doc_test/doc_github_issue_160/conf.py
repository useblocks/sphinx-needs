import os

extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]

plantuml = "java -Djava.awt.headless=true -jar %s" % os.path.join(
    os.path.dirname(__file__), "..", "utils", "plantuml.jar"
)
plantuml_output_format = "svg"

needs_id_regex = "^[A-Z0-9]-[A-Z0-9]+"
