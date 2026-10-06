"""``needextend``'s ``:+field:`` on a nullable field that was never set (#2038).

A field from ``needs_fields`` is nullable unless it says otherwise, so a need that does
not set it holds ``None``. Appending to it behaves as setting it to the appended value,
the way ``:+tags:`` behaves on a need with no tags, for a literal and for a dynamic
function, on an array field and on a string field.
"""

from pathlib import Path
from typing import Any

import pytest
from sphinx.application import Sphinx

from sphinx_needs_testkit import build_warnings
from tests.test_needextend_priority import needs_by_id

CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_fields = {
    "refs": {"schema": {"type": "array", "items": {"type": "string"}}},
    "note": {"schema": {"type": "string"}},
}
"""

NEEDS = """\
Index
=====

.. req:: Extended
   :id: REQ_1

.. req:: Untouched
   :id: REQ_2
"""


def project(extends: str) -> list[dict[str, Any]]:
    """``test_app`` parameters for ``NEEDS`` followed by ``extends``."""
    return [
        {
            "buildername": "html",
            "files": [
                (Path("conf.py"), CONF),
                (Path("index.rst"), NEEDS + extends),
            ],
        }
    ]


def built_needs(app: Sphinx) -> dict[str, dict[str, Any]]:
    """Build without a warning, and return the needs of ``needs.json`` by id.

    ``REQ_2`` is never extended, so its fields show the project's fields are unset,
    and nullable: ``None`` in ``needs.json``.
    """
    app.build()
    assert build_warnings(app) == []
    needs = needs_by_id(app)
    assert needs["REQ_2"]["refs"] is None
    assert needs["REQ_2"]["note"] is None
    return needs


@pytest.mark.parametrize(
    "test_app",
    project("""
.. needextend:: REQ_1
   :+refs: a
"""),
    indirect=True,
)
def test_append_literal_to_unset_array_sets_it(test_app: Sphinx):
    """M1: the literal array arm treats ``None`` as the empty list."""
    assert built_needs(test_app)["REQ_1"]["refs"] == ["a"]


@pytest.mark.parametrize(
    "test_app",
    project("""
.. needextend:: REQ_1
   :+refs: a

.. needextend:: REQ_1
   :+refs: b
"""),
    indirect=True,
)
def test_appends_to_unset_array_accumulate(test_app: Sphinx):
    """M2: the first append sets the field, the second appends to it (the issue's case)."""
    need = built_needs(test_app)["REQ_1"]
    assert need["refs"] == ["a", "b"]
    assert need["modifications"] == 2


@pytest.mark.parametrize(
    "test_app",
    project("""
.. needextend:: REQ_1
   :+refs: [[copy("id")]]
"""),
    indirect=True,
)
def test_append_function_to_unset_array_sets_it(test_app: Sphinx):
    """M3: the function arm makes a function array of the appended items alone."""
    assert built_needs(test_app)["REQ_1"]["refs"] == ["REQ_1"]


@pytest.mark.parametrize(
    "test_app",
    project("""
.. needextend:: REQ_1
   :+note: [[copy("id")]]
"""),
    indirect=True,
)
def test_append_function_to_unset_string_sets_it(test_app: Sphinx):
    """The function arm on a string field: the same function array, resolved to a string."""
    assert built_needs(test_app)["REQ_1"]["note"] == "REQ_1"


@pytest.mark.parametrize(
    "test_app",
    project("""
.. needextend:: REQ_1
   :+note: x
"""),
    indirect=True,
)
def test_append_literal_to_unset_string_sets_it(test_app: Sphinx):
    """M4: the literal string arm already treated an unset value as empty; it still does."""
    assert built_needs(test_app)["REQ_1"]["note"] == "x"
