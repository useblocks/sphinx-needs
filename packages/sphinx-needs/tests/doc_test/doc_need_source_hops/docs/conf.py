import os
import sys

# the local extension lives beside this file, the autodoc'd module outside the source
# directory (its hop's path starts with ``..``); each build imports them from its own copy
# of the project, so that the docstring's file is this project's
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "outside"))
sys.path.insert(0, _HERE)
sys.modules.pop("source_hops_module", None)
sys.modules.pop("source_hops_service", None)

extensions = [
    "sphinx_needs",
    "myst_parser",
    "sphinx.ext.autodoc",
    "source_hops_service",
]
source_suffix = {".rst": "restructuredtext", ".md": "markdown"}
# shifts the parser's line count of every page: a hop given a parser line points at
# the wrong line of its file
rst_prolog = """
.. |p1| replace:: P1

.. |p2| replace:: P2
"""
needs_types = [
    {
        "directive": "req",
        "title": "Req",
        "prefix": "R_",
        "color": "#fff",
        "style": "node",
    }
]
needs_external_needs = [
    {"base_url": "http://example.org", "json_path": "ext.json", "id_prefix": "EXT_"}
]
myst_enable_extensions = ["colon_fence"]
# the included files are read through their hosts only
exclude_patterns = ["frag/**", "_build"]
