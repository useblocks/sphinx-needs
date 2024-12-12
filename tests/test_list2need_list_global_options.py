from pathlib import Path

import pytest
import json

from sphinx_needs.api import get_needs_view




@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "srcdir": "doc_test/doc_list2need_list_global_options",
            "confoverrides": {"needs_reproducible_json": True},
        }
    ],
    indirect=True,
)
def test_doc_list2need_list_global_options(test_app, snapshot):
    app = test_app
    app.build()

    needs_list = json.loads(Path(app.outdir, "needs.json").read_text())
    
    needs = needs_list["versions"][""]["needs"]
 
    # Check that all entries have a status item equal to "open"
    for need_id, need in needs.items():
        assert need.get("status") == "open", f"Need {need_id} does not have status 'open'"
        assert "SomeValue" in need.get("aggregateoption", ""), f"Need {need_id} does not have 'SomeValue' in aggregateoption"

    # Check that NEED-D has "OtherValue" in its aggregateoption
    need_d = needs.get("NEED-D")
    assert need_d is not None, "NEED-D is missing"
    assert "OtherValue" in need_d.get("aggregateoption", ""), "NEED-D does not have 'OtherValue' in aggregateoption"
    
    
    
    
    