project = "needs test docs"
master_doc = "intro"

extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]

# figures, tables and code-blocks are automatically numbered if they have a caption
numfig = True

# note, the plantuml executable command is set globally in the test suite
plantuml_output_format = "svg"
