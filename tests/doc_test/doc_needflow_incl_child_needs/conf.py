import os

extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]

needs_table_style = "TABLE"

needs_id_regex = "^[A-Za-z0-9_]"

needs_types = [
    {"directive": "story", "title": "User Story", "prefix": "US_", "color": "#BFD8D2", "style": "node"},
    {"directive": "spec", "title": "Specification", "prefix": "SP_", "color": "#FEDCD2", "style": "node"},
    {"directive": "impl", "title": "Implementation", "prefix": "IM_", "color": "#DF744A", "style": "node"},
    {"directive": "test", "title": "Test Case", "prefix": "TC_", "color": "#DCB239", "style": "node"},
]


# needs_extra_links = [
#     {
#         "option": "blocks",
#         "incoming": "is blocked by",
#         "outgoing": "blocks",
#         "copy": False,
#         "style": "#AA0000",
#         "style_part": "dotted,#AA0000",
#         "style_start": "-",
#         "style_end": "-o",
#         "allow_dead_links": True,
#     },
# ]


plantuml = "java -Djava.awt.headless=true -jar %s" % os.path.join(
    os.path.dirname(__file__), "..", "utils", "plantuml.jar"
)
plantuml_output_format = "svg"
