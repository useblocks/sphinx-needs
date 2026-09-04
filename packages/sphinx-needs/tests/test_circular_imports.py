import pkgutil
import subprocess
import sys

import sphinx_needs


def test_no_circular_imports():
    """
    Test for circular imports in the sphinx_needs package.

    Each package is tested isolated by importing it into a
    new Python interpreter.
    """
    for _, name, _ in pkgutil.walk_packages(
        sphinx_needs.__path__, prefix="sphinx_needs."
    ):
        subprocess.check_call(
            [
                sys.executable,
                "-c",
                "import importlib; importlib.import_module(" + repr(name) + ")",
            ]
        )
