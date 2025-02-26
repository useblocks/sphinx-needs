import json
import os
from pathlib import Path

import pytest
from sphinx.util.console import strip_colors
from syrupy.filters import props

from sphinx_needs.config import NeedsSphinxConfig


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
    print(warnings)
    assert warnings == [
        "WARNING: Dynamic function not closed correctly:  (in needs_global_options) [needs.dynamic_function]",
        "WARNING: needs_global_options key 'link3' has a default value that is not of type 'str or list' [needs.config]",
        "WARNING: needs_global_options key 'bad_value_type' has a default value that is not of type 'str' [needs.config]",
        "WARNING: needs_global_options key 'too_many_params' has wrong amount of parameters [needs.config]",
        "WARNING: needs_global_options key 'unknown' must also exist in needs_extra_options, needs_extra_links, or ['layout', 'status', 'style'] [needs.config]",
    ]

    needs_config = NeedsSphinxConfig(test_app.config)
    assert needs_config.field_defaults == snapshot

    json_data = Path(test_app.outdir, "needs.json").read_text()
    needs = json.loads(json_data)
    assert needs == snapshot(
        exclude=props("created", "project", "creator", "needs_schema")
    )
