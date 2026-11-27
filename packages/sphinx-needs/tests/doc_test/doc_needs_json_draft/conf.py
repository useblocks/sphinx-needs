import os
import sys

# the autodoc'd module and the local service live beside this file; each build imports
# them from its own copy of the project
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.modules.pop("jsondraft_module", None)
sys.modules.pop("jsondraft_service", None)

project = "up"
version = "1.0"
extensions = ["sphinx_needs", "sphinx.ext.autodoc", "jsondraft_service"]
# the included files are read through their hosts only
exclude_patterns = ["frag/**", "_build"]

needs_json_format_version = "2a1"
needs_types = {
    "req": {"title": "Requirement", "prefix": "R_"},
    "spec": {
        "title": "Specification",
        "prefix": "S_",
        "fields": {"verdict": {"schema": {"type": "string"}}},
    },
}
needs_fields = {"asil": {"default": "QM", "nullable": True}}
needs_links = {
    "implements": {"incoming": "is implemented by", "outgoing": "implements"}
}
