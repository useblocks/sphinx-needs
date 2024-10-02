import os
import random
import sys
import time

from sphinx_needs.api import add_dynamic_function

sys.path.insert(0, os.path.abspath("."))

extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]

# note, the plantuml executable command is set globally in the test suite
plantuml_output_format = "svg"

needs_debug_measurement = True
needs_debug_filters = True

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


def dyn_func(app, need, needs, *args, **kwargs):
    time.sleep(random.randrange(1, 5) * 0.1)  # Let's wait some time for our test
    return "some data"


def another_func(app, need, needs, *args, **kwargs):
    time.sleep(random.randrange(1, 5) * 0.01)  # Let's wait some time for our test
    return "some other data"


def setup(app):
    add_dynamic_function(app, dyn_func)
    add_dynamic_function(app, another_func)
