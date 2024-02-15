import json
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_build_only", "no_plantuml": True}],
    indirect=True,
)
def test_doc_build_only(test_app):
    app = test_app

    app.build()
    assert app._warning.getvalue() == ""

    needs = json.loads(Path(app.outdir, "needs.json").read_text("utf8"))
    id_to_expr = {
        k: v.get("only_expressions") for k, v in needs["versions"]["1"]["needs"].items()
    }
    assert id_to_expr == {
        "REQ_1": None,
        "REQ_2": ["html"],
        "REQ_3": ["html"],
        "REQ_4": ["not something", "other"],
    }
