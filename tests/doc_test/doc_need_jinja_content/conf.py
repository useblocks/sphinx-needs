import os

extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]

plantuml = "java -Djava.awt.headless=true -jar %s" % os.path.join(
    os.path.dirname(__file__), "..", "utils", "plantuml.jar"
)
plantuml_output_format = "svg"

needs_id_regex = "^[A-Za-z0-9_]"

needs_types = [
    {"directive": "req", "title": "Requirement", "prefix": "R_", "color": "#BFD8D2", "style": "node"},
    {"directive": "spec", "title": "Specification", "prefix": "SP_", "color": "#FEDCD2", "style": "node"},
    {"directive": "impl", "title": "Implementation", "prefix": "IM_", "color": "#DF744A", "style": "node"},
    {"directive": "test", "title": "Test Case", "prefix": "TC_", "color": "#DCB239", "style": "node"},
]


def custom_defined_func():
    return "Content from custom_defined_func."


needs_render_context = {
    "custom_data_1": "Project_X",
    "custom_data_2": custom_defined_func(),
    "custom_data_3": True,
    "custom_data_4": ["Daniel - ID: 811982", "Marco - ID: 234232"],
}
