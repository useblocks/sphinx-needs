project = "needs test docs"
master_doc = "intro"

extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]

# figures, tables and code-blocks are automatically numbered if they have a caption
numfig = True

# note, the plantuml command comes from the test suite, not from here: the pinned
# renderer for a build that opts into it, an inert one for every other build
plantuml_output_format = "svg"
