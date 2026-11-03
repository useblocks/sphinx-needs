import os
import sys

# the autodoc'd package lives outside the source directory (its hops' paths start with
# ``..``); each build imports it from its own copy of the project
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "src"))
for _name in [
    name for name in sys.modules if name.partition(".")[0] == "docstring_hops"
]:
    del sys.modules[_name]

extensions = ["sphinx_needs", "sphinx.ext.autodoc"]
exclude_patterns = ["_build"]
needs_types = [
    {
        "directive": "req",
        "title": "Req",
        "prefix": "R_",
        "color": "#fff",
        "style": "node",
    }
]
