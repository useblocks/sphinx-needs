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
    empty name is no name."""
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
        "SIG_JS": "go",
        "SIG_PY": "meth",
        "SIG_RST": ":opt:",
    }
