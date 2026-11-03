import os
import sys

# the local extension lives beside this file; each build imports it from its own copy
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.modules.pop("source_shapes_ext", None)

extensions = ["sphinx_needs", "source_shapes_ext"]
