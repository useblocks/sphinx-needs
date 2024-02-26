extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]

# note, the plantuml executable command is set globally in the test suite
plantuml_output_format = "svg"

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

suppress_warnings = ["needs.link_outgoing"]

needs_extra_links = [
    {
        "option": "blocks",
        "incoming": "is blocked by",
        "outgoing": "blocks",
        "copy": False,
        "style": "bold,#AA0000",
        "allow_dead_links": True,
    },
    {
        "option": "tests",
        "incoming": "is tested by",
        "outgoing": "tests",
        "copy": True,
        "style": "dashed,#00AA00",
        "style_part": "dotted,#00AA00",
    },
]
