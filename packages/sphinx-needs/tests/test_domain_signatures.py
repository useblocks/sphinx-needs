import json
from pathlib import Path

import pytest
from sphinx.testing.util import SphinxTestApp


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/domain_signatures"}],
    indirect=True,
)
def test_signature_of_domain_objects(test_app: SphinxTestApp):
    """A need inside a domain object takes that object's name as its signature,
    whether the domain writes the name as text (py, rst) or wraps it in a
    ``desc_sig_name`` (c, cpp, js) (#2394). A C++ template's parameter is a
    ``desc_name`` too, on the line before the declaration's own. The first
    signature of an object wins, the nearest enclosing object wins, and an
    empty name is no name. A ``desc_signature`` outside any domain object names no
    object, so it gives no signature."""
    app = test_app
    app.build()
    assert not app._warning.getvalue()

    needs = json.loads(Path(app.outdir, "needs.json").read_text())["versions"][""][
        "needs"
    ]
    assert {need_id: need["signature"] for need_id, need in needs.items()} == {
        "SIG_C": "cfunc",
        "SIG_CPP": "run",
        "SIG_CPP_TMPL": "tmpl",
        "SIG_CPP_TWO": "first",
        "SIG_CPP_IN_PY": "inner",
        "SIG_EMPTY": None,
        "SIG_EMPTY_IN_PY": "Outer",
        "SIG_JS": "go",
        "SIG_NEED_OUTER": None,
        "SIG_OUTSIDE": None,
        "SIG_PY": "meth",
        "SIG_PY_IN_NEED": "in_need",
        "SIG_PY_IN_NEED_CHILD": "in_need",
        "SIG_RST": ":opt:",
    }


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/domain_signatures"}],
    indirect=True,
)
def test_a_need_in_a_domain_object_in_a_need(test_app: SphinxTestApp):
    """A need in a function written inside another need's content takes the function's
    name as its signature and that need as its parent; a need inside it takes the same
    signature, and its nearest need, not the outermost, as its parent."""
    app = test_app
    app.build()
    assert not app._warning.getvalue()

    needs = json.loads(Path(app.outdir, "needs.json").read_text())["versions"][""][
        "needs"
    ]
    assert {
        need_id: (needs[need_id]["signature"], needs[need_id]["parent_needs"])
        for need_id in ("SIG_NEED_OUTER", "SIG_PY_IN_NEED", "SIG_PY_IN_NEED_CHILD")
    } == {
        "SIG_NEED_OUTER": (None, []),
        "SIG_PY_IN_NEED": ("in_need", ["SIG_NEED_OUTER"]),
        "SIG_PY_IN_NEED_CHILD": ("in_need", ["SIG_PY_IN_NEED"]),
    }
