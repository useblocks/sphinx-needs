import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]

needs_id_regex = "^[A-Za-z0-9_]*"

needs_types = [
    {
        "directive": "feature",
        "title": "Feature",
        "prefix": "FE_",
        "color": "#FEDCD2",
        "style": "node",
    },
    {
        "directive": "usecase",
        "title": "Use Case",
        "prefix": "USE_",
        "color": "#DF744A",
        "style": "node",
    },
]

needs_extra_options = ["ti", "tcl"]

needs_extra_links = [
    {
        "option": "features",
        "incoming": "featured by",
        "outgoing": "features",
        "copy": False,
        "style": "#Gold",
        "style_part": "#Gold",
    },
]

needs_allow_unsafe_filters = True
