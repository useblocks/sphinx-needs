import os

extensions = ["sphinx_needs"]
needs_title_optional = True
needs_max_title_length = 50
smartquotes_action = "qD"

plantuml = "java -Djava.awt.headless=true -jar %s" % os.path.join(
    os.path.dirname(__file__), "..", "utils", "plantuml.jar"
)
plantuml_output_format = "svg"
