extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]

# note, the plantuml executable command is set globally in the test suite
plantuml_output_format = "svg"

# needs_types entries without an explicit 'color' field.
# This reproduces the situation that caused dark/black nodes in needflow.
needs_types = [
    {
        "directive": "spec",
        "title": "Specification",
        "prefix": "S_",
    },
]
