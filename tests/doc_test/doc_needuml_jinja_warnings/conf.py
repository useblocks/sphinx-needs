extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]

# note, the plantuml executable command is set globally in the test suite
plantuml_output_format = "svg"

# defined for every need, set on none of them: the shape import() must ignore
needs_fields = {"myopt": {"nullable": False, "default": ""}}
