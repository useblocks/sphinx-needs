tags.add("tag_b")  # noqa: F821

extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]

# note, the plantuml executable command is set globally in the test suite
plantuml_output_format = "svg"

needs_id_regex = "^[A-Za-z0-9_]"

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
needs_variants = {"change_author": "assignee == 'Randy Duodu'"}
needs_variant_options = []
needs_filter_data = {"assignee": "Randy Duodu"}
needs_extra_options = [
    "my_extra_option",
    "another_option",
    "author",
    "comment",
    "amount",
    "hours",
    "image",
    "config",
    "github",
    "value",
    "unit",
]
