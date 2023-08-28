import os

extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]

needs_table_style = "TABLE"

needs_types = [
    {"directive": "story", "title": "User Story", "prefix": "US_", "color": "#BFD8D2", "style": "node"},
    {"directive": "spec", "title": "Specification", "prefix": "SP_", "color": "#FEDCD2", "style": "node"},
    {"directive": "impl", "title": "Implementation", "prefix": "IM_", "color": "#DF744A", "style": "node"},
    {"directive": "test", "title": "Test Case", "prefix": "TC_", "color": "#DCB239", "style": "node"},
]

plantuml = "java -Djava.awt.headless=true -jar %s" % os.path.join(
    os.path.dirname(__file__), "..", "utils", "plantuml.jar"
)
plantuml_output_format = "svg"

needs_external_needs = [
    {"base_url": "http://my_company.com/docs/v1/", "json_path": "needs_test_small.json", "id_prefix": "ext_"},
    {"base_url": "../../_build/html", "json_path": "needs_test_small.json", "id_prefix": "ext_rel_path_"},
]
