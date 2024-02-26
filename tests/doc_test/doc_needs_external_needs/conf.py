extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]

# note, the plantuml executable command is set globally in the test suite
plantuml_output_format = "svg"

needs_table_style = "TABLE"

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

needs_external_needs = [
    {
        "base_url": "http://my_company.com/docs/v1/",
        "json_path": "needs_test_small.json",
        "id_prefix": "ext_",
    },
    {
        "base_url": "../../_build/html",
        "json_path": "needs_test_small.json",
        "id_prefix": "ext_rel_path_",
    },
]

# we want to ensure only internal needs are checked against this regex, not the external ones
needs_id_regex = "INTERNAL.*"
