import os

version = "1.0"

extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]

plantuml = "java -Djava.awt.headless=true -jar %s" % os.path.join(
    os.path.dirname(__file__), "..", "utils", "plantuml.jar"
)
plantuml_output_format = "svg"

needs_types = [
    {"directive": "story", "title": "User Story", "prefix": "US_", "color": "#BFD8D2", "style": "node"},
    {"directive": "spec", "title": "Specification", "prefix": "SP_", "color": "#FEDCD2", "style": "node"},
    {"directive": "impl", "title": "Implementation", "prefix": "IM_", "color": "#DF744A", "style": "node"},
    {"directive": "test", "title": "Test Case", "prefix": "TC_", "color": "#DCB239", "style": "node"},
]

needs_extra_links = [
    {
        "option": "links",
        "incoming": "is linked by",
        "outgoing": "links to",
        "copy": False,
        "style": "#black",
        "style_part": "dotted,#black",
    },
    {
        "option": "blocks",
        "incoming": "is blocked by",
        "outgoing": "blocks",
        "copy": True,
        "style": "bold,#AA0000",
    },
    {
        "option": "tests",
        "incoming": "is tested by",
        "outgoing": "tests",
        "copy": False,
        "style": "dashed,#00AA00",
        "style_part": "dotted,#00AA00",
    },
]

needs_flow_link_types = ["links", "tests"]
