import os

extensions = ["sphinxcontrib.plantuml", "sphinx_needs"]

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
]

test_dir = os.path.dirname(__file__)
test_json = os.path.join(test_dir, "needs_test_small.json")
# test_json = os.path.join(test_dir, 'needs_test_invalid.json')

# needs_external_needs = [{"base_url": f"file://{test_dir}", "json_url": f"file://{test_json}", "id_prefix": "ext_"}]
needs_external_needs = [
    {
        "base_url": "http://my_company.com/docs/v1/",
        "json_path": "needs_test_small.json",
        "id_prefix": "EXT_",
    }
]

# Needed to export really ALL needs. The default entry would filter out all needs coming from external
needs_builder_filter = "True"
