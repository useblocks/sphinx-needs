import os

extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]

# note, the plantuml executable command is set globally in the test suite
plantuml_output_format = "svg"

needs_id_regex = "^[A-Za-z0-9_]"

needs_types = [
    {
        "directive": "req",
        "title": "Requirement",
        "prefix": "RE_",
        "color": "#BFD8D2",
        "style": "node",
    },
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
    {
        "directive": "user",
        "title": "User",
        "prefix": "U_",
        "color": "#777777",
        "style": "node",
    },
    {
        "directive": "action",
        "title": "Action",
        "prefix": "A_",
        "color": "#FFCC00",
        "style": "node",
    },
]

needs_extra_links = [
    {
        "option": "triggers",
        "incoming": "triggered by",
        "outgoing": "triggers",
        "copy": False,
        "style": "#00AA00",
        "style_part": "solid,#777777",
        "allow_dead_links": True,
    },
]

needs_css = os.path.join(os.path.dirname(__file__), "filter.css")
