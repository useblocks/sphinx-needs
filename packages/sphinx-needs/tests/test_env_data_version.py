"""``ENV_DATA_VERSION`` is bumped together with the paragraph that says why.

Sphinx re-reads every document of an existing environment whose version differs, and
nothing else notices a missing bump: the build succeeds and leaves stale pages (or
doctrees the code no longer understands). The paragraphs of the constant's docstring
are the record of each bump, so the constant must be the highest version they name:
a bump without its paragraph, or a revert that leaves the paragraph, is red here.
"""

import ast
import re
from pathlib import Path

from sphinx_needs import data


def _docstring_versions() -> list[int]:
    """The ``Version N`` paragraphs of the docstring under ``ENV_DATA_VERSION``."""
    body = ast.parse(Path(data.__file__).read_text(encoding="utf-8")).body
    index = next(
        i
        for i, node in enumerate(body)
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "ENV_DATA_VERSION"
    )
    docstring = body[index + 1]
    assert isinstance(docstring, ast.Expr)
    assert isinstance(docstring.value, ast.Constant)
    assert isinstance(docstring.value.value, str)
    return [
        int(number)
        for number in re.findall(r"^Version (\d+) ", docstring.value.value, re.M)
    ]


def test_the_version_is_the_highest_its_docstring_names():
    """The constant is the version of the docstring's last paragraph."""
    versions = _docstring_versions()
    assert versions == sorted(versions), "the paragraphs are in version order"
    assert max(versions) == data.ENV_DATA_VERSION
