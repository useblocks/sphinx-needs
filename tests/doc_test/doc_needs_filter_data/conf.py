import os
import sys

sys.path.insert(0, os.path.abspath("./"))

extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]

# note, the plantuml executable command is set globally in the test suite
plantuml_output_format = "svg"

needs_id_regex = "^[A-Za-z0-9_]*"
needs_types = [
    {
        "directive": "story",
        "title": "User Story",
        "prefix": "US_",
        "color": "#BFD8D2",
        "style": "node",
    },
    {
        "directive": "spec",
        "title": "Specification",
        "prefix": "SP_",
        "color": "#FEDCD2",
        "style": "node",
    },
    {
        "directive": "impl",
        "title": "Implementation",
        "prefix": "IM_",
        "color": "#DF744A",
        "style": "node",
    },
    {
        "directive": "test",
        "title": "Test Case",
        "prefix": "TC_",
        "color": "#DCB239",
        "style": "node",
    },
]


def custom_func():
    return "my_tag"


needs_filter_data = {"current_variant": "project_x", "sphinx_tag": custom_func()}

needs_extra_options = ["variant"]

needs_warnings = {
    "variant_not_equal_current_variant": "variant != current_variant",
}

needs_warnings_always_warn = True
