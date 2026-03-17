import os

import pytest
from sphinx.application import Sphinx
from sphinx.util.console import strip_colors


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_link_conditions",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_link_conditions(test_app: Sphinx):
    """Test that link conditions produce the expected warnings."""
    app = test_app
    app.build()

    warnings = strip_colors(
        app._warning.getvalue().replace(str(app.srcdir) + os.sep, "srcdir/")
    ).splitlines()

    assert warnings == [
        # SPEC_002 links to REQ_002[status=="open"] but REQ_002 has status "closed"
        "srcdir/index.rst:28: WARNING: Need 'SPEC_002' link 'REQ_002' in field 'links': condition 'status==\"open\"' not satisfied by target need 'REQ_002' [needs.link_condition_failed]",
        # SPEC_003 links to REQ_001[status===] which has invalid syntax
        "srcdir/index.rst:34: WARNING: Need 'SPEC_003' link 'REQ_001' in field 'links': invalid condition syntax 'status===': Filter 'status===' not valid. Error: invalid syntax (<string>, line 1). [needs.link_condition_invalid]",
        # SPEC_005 links to REQ_003[status=="open"] which fails (REQ_003 has status "done")
        "srcdir/index.rst:46: WARNING: Need 'SPEC_005' link 'REQ_003' in field 'links': condition 'status==\"open\"' not satisfied by target need 'REQ_003' [needs.link_condition_failed]",
        # SPEC_006 links to REQ_001[["open" in tags]] with multi-bracket; fails because REQ_001 has no "open" tag
        "srcdir/index.rst:52: WARNING: Need 'SPEC_006' link 'REQ_001' in field 'links': condition '\"open\" in tags' not satisfied by target need 'REQ_001' [needs.link_condition_failed]",
    ]
