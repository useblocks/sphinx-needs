extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]

# note, the plantuml executable command is set globally in the test suite
plantuml_output_format = "svg"

needs_types = [
    {
        "directive": "int",
        "content": "plantuml",
        "title": "Interface",
        "prefix": "I_",
        "color": "#BFD8D2",
        "style": "card",
    },
    {
        "directive": "comp",
        "content": "plantuml",
        "title": "Component",
        "prefix": "C_",
        "color": "#BFD8D2",
        "style": "card",
    },
    {
        "directive": "sys",
        "content": "plantuml",
        "title": "System",
        "prefix": "S_",
        "color": "#FF68D2",
        "style": "node",
    },
    {
        "directive": "prod",
        "content": "plantuml",
        "title": "Product",
        "prefix": "P_",
        "color": "#FF68D2",
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
]

needs_extra_links = [
    {
        "option": "uses",
        "incoming": "is used by",
        "outgoing": "uses",
    },
    {
        "option": "tests",
        "incoming": "is tested by",
        "outgoing": "tests",
        "style": "#00AA00",
    },
]
