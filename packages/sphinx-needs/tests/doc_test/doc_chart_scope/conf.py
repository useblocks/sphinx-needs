import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

extensions = ["sphinx_needs"]

needs_id_regex = "^[A-Za-z0-9_]"
