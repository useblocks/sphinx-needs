import json
import os
from pathlib import Path

import pytest
from sphinx.util.console import strip_colors
from syrupy.filters import props

from sphinx_needs.data import SphinxNeedsData


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_global_options",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_doc_global_option(test_app, snapshot):
    test_app.build()
    warnings = strip_colors(
        test_app._warning.getvalue().replace(str(test_app.srcdir) + os.sep, "srcdir/")
    ).splitlines()
    assert warnings == [
        "WARNING: needs_global_options 'link3' default value is incorrect: Invalid value for field 'link3': 1 [needs.config]",
        "WARNING: needs_global_options 'bad_value_type' default value is incorrect: Invalid value for field 'bad_value_type': 1.27 [needs.config]",
        "WARNING: needs_global_options 'too_many_params' predicates are incorrect: defaults must be a list of (filter, value) pairs. [needs.config]",
        "WARNING: needs_global_options 'unknown' does not match any defined need option [needs.config]",
    ]

    needs_schema = SphinxNeedsData(test_app.env).get_schema()
    assert {
        s.name: {"default": s.default, "predicate_defaults": s.predicate_defaults}
        for s in needs_schema.iter_all_fields()
    } == snapshot

    json_data = Path(test_app.outdir, "needs.json").read_text()
    needs = json.loads(json_data)
    assert needs == snapshot(exclude=props("created", "project", "creator"))
