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
            "srcdir": "doc_test/doc_global_options_old",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_doc_global_option_old(test_app, snapshot):
    test_app.build()
    warnings = strip_colors(
        test_app._warning.getvalue().replace(str(test_app.srcdir) + os.sep, "srcdir/")
    ).splitlines()
    assert warnings == [
        "WARNING: needs_global_options 'option_5', item 0, has default value but is not the last item [needs.config]",
        "WARNING: Dynamic function not closed correctly:  (in needs_global_options) [needs.dynamic_function]",
        "WARNING: needs_global_options 'link3' has a default value that is not of type 'str_list' [needs.config]",
        "WARNING: needs_global_options 'bad_value_type' has a default value that is not of type 'str' [needs.config]",
        "WARNING: needs_global_options 'too_many_params' has an unknown value format [needs.config]",
        "WARNING: needs_global_options 'unknown' must also exist in needs_extra_options, needs_extra_links, or ['constraints', 'layout', 'status', 'style', 'tags'] [needs.config]",
        "WARNING: needs_global_options uses old, non-dict, format. please update to new format: {'layout': {'default': 'clean_l'}, 'option_1': {'default': 'test_global'}, 'option_2': {'default': \"[[copy('id')]]\"}, 'option_3': {'predicates': [('status == \"implemented\"', 'STATUS_IMPL')]}, 'option_4': {'predicates': [('status == \"closed\"', 'STATUS_CLOSED')], 'default': 'STATUS_UNKNOWN'}, 'option_5': {'predicates': [('status == \"implemented\"', 'STATUS_IMPL'), ('status == \"closed\"', 'STATUS_CLOSED')], 'default': 'final'}, 'link1': {'default': ['SPEC_1']}, 'link2': {'predicates': [('status == \"implemented\"', ['SPEC_2', \"[[copy('link1')]]\"]), ('status == \"closed\"', ['SPEC_3'])], 'default': ['SPEC_1']}, 'tags': {'predicates': [('status == \"implemented\"', ['a', 'b']), ('status == \"closed\"', ['c'])], 'default': ['d']}} [needs.deprecated]",
    ]

    needs_config = NeedsSphinxConfig(test_app.config)
    assert needs_config.field_defaults == snapshot

    json_data = Path(test_app.outdir, "needs.json").read_text()
    needs = json.loads(json_data)
    assert needs == snapshot(
        exclude=props("created", "project", "creator", "needs_schema")
    )


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
        "WARNING: needs_global_options 'link3' has a default value that is not of type 'str_list' [needs.config]",
        "WARNING: needs_global_options 'bad_value_type' has a default value that is not of type 'str' [needs.config]",
        "WARNING: needs_global_options 'too_many_params', 'predicates', must be a list of (filter string, value) pairs [needs.config]",
        "WARNING: needs_global_options 'unknown' must also exist in needs_extra_options, needs_extra_links, or ['constraints', 'layout', 'status', 'style', 'tags'] [needs.config]",
    ]

    needs_config = NeedsSphinxConfig(test_app.config)
    assert needs_config.field_defaults == snapshot

    json_data = Path(test_app.outdir, "needs.json").read_text()
    needs = json.loads(json_data)
    assert needs == snapshot(
        exclude=props("created", "project", "creator", "needs_schema")
    )
