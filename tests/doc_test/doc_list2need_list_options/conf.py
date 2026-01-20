extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]
project = "test for list2need list_global_options"
author = "Christophe SEYLER"

needs_table_style = "TABLE"

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

needs_extra_links = [
    {"option": "checks", "incoming": "is checked by", "outgoing": "checks"},
    {"option": "triggers", "incoming": "is triggered by", "outgoing": "triggers"},
]
needs_extra_options = ["aggregateoption"]
