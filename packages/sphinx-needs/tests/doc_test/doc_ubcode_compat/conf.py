extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]

# note, the plantuml command comes from the test suite, not from here: the pinned
# renderer for a build that opts into it, an inert one for every other build
plantuml_output_format = "svg"

needs_id_regex = "^[A-Za-z0-9_]"
