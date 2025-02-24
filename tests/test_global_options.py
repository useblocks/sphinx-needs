import json
import os
from pathlib import Path

import pytest
from sphinx.util.console import strip_colors
from syrupy.filters import props


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
        "WARNING: needs_global_options key 'global_5' must also exist in needs_extra_options, needs_extra_links, or ['collapse', 'constraints', 'hide', 'layout', 'status', 'style', 'tags'] [needs.deprecated]"
    ]

    json_data = Path(test_app.outdir, "needs.json").read_text()
    needs = json.loads(json_data)
    assert needs == snapshot(
        exclude=props("created", "project", "creator", "needs_schema")
    )
