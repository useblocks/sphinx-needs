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
    ``desc_sig_name`` (c, cpp, js) (#2394)."""
    app = test_app
    app.build()
    assert not app._warning.getvalue()

    needs = json.loads(Path(app.outdir, "needs.json").read_text())["versions"][""][
        "needs"
    ]
    assert {need_id: need["signature"] for need_id, need in needs.items()} == {
        "SIG_C": "cfunc",
        "SIG_CPP": "run",
        "SIG_JS": "go",
        "SIG_PY": "meth",
        "SIG_RST": ":opt:",
    }
