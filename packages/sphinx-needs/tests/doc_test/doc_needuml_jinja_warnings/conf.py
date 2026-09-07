extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]

# note, the plantuml command comes from the test suite, not from here: the pinned
# renderer for a build that opts into it, an inert one for every other build
plantuml_output_format = "svg"

# defined for every need, set on none of them: the shape import() must ignore
needs_fields = {"myopt": {"nullable": False, "default": ""}}
