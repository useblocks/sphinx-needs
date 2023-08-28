import os

extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]

needs_table_style = "TABLE"

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
    {"directive": "sys", "content": "plantuml", "title": "System", "prefix": "S_", "color": "#FF68D2", "style": "node"},
    {
        "directive": "prod",
        "content": "plantuml",
        "title": "Product",
        "prefix": "P_",
        "color": "#FF68D2",
        "style": "node",
    },
    {"directive": "story", "title": "User Story", "prefix": "US_", "color": "#BFD8D2", "style": "node"},
    {"directive": "spec", "title": "Specification", "prefix": "SP_", "color": "#FEDCD2", "style": "node"},
    {"directive": "impl", "title": "Implementation", "prefix": "IM_", "color": "#DF744A", "style": "node"},
    {"directive": "test", "title": "Test Case", "prefix": "TC_", "color": "#DCB239", "style": "node"},
]

plantuml = "java -Djava.awt.headless=true -jar %s" % os.path.join(
    os.path.dirname(__file__), "..", "utils", "plantuml.jar"
)
plantuml_output_format = "svg"

needs_build_needumls = "my_needumls"
