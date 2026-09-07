tags.add("tag_b")  # noqa: F821

extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]

# note, the plantuml command comes from the test suite, not from here: the pinned
# renderer for a build that opts into it, an inert one for every other build
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
needs_filter_data = {"assignee": "Randy Duodu"}
needs_fields = {
    "status": {
        "parse_variants": True,
    },
    "my_extra_option": {"nullable": True},
    "another_option": {"nullable": True},
    "author": {
        "nullable": True,
        "parse_variants": True,
    },
    "value": {"nullable": True},
    "field_bool": {
        "schema": {
            "type": "boolean",
        },
        "parse_variants": True,
    },
    "field_array_int": {
        "schema": {
            "type": "array",
            "items": {"type": "integer"},
        },
        "parse_variants": True,
    },
}
needs_links = {
    "relates": {
        "parse_variants": True,
    },
}

needs_build_json = True
needs_json_remove_defaults = True
