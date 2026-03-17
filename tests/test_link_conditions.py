import json
import os
from pathlib import Path

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
        # EXT_COND_FAIL external need links to REQ_002[status=="open"] which fails
        "WARNING: http://my_company.com/docs/v1/index.html#COND_FAIL: Need 'EXT_COND_FAIL' link 'REQ_002' in field 'links': condition 'status==\"open\"' not satisfied by target need 'REQ_002' [needs.link_condition_failed]",
        # SPEC_002 links to REQ_002[status=="open"] but REQ_002 has status "closed"
        "srcdir/index.rst:28: WARNING: Need 'SPEC_002' link 'REQ_002' in field 'links': condition 'status==\"open\"' not satisfied by target need 'REQ_002' [needs.link_condition_failed]",
        # SPEC_003 links to REQ_001[status===] which has invalid syntax
        "srcdir/index.rst:34: WARNING: Need 'SPEC_003' link 'REQ_001' in field 'links': invalid condition syntax 'status===': Filter 'status===' not valid. Error: invalid syntax (<string>, line 1). [needs.link_condition_invalid]",
        # SPEC_005 links to REQ_003[status=="open"] which fails (REQ_003 has status "done")
        "srcdir/index.rst:46: WARNING: Need 'SPEC_005' link 'REQ_003' in field 'links': condition 'status==\"open\"' not satisfied by target need 'REQ_003' [needs.link_condition_failed]",
        # SPEC_006 links to REQ_001[["open" in tags]] with multi-bracket; fails because REQ_001 has no "open" tag
        "srcdir/index.rst:52: WARNING: Need 'SPEC_006' link 'REQ_001' in field 'links': condition '\"open\" in tags' not satisfied by target need 'REQ_001' [needs.link_condition_failed]",
        # IMP_COND_FAIL imported via needimport, links to REQ_002[status=="open"] which fails
        "srcdir/index.rst:61: WARNING: Need 'IMP_COND_FAIL' link 'REQ_002' in field 'links': condition 'status==\"open\"' not satisfied by target need 'REQ_002' [needs.link_condition_failed]",
    ]


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "srcdir": "doc_test/doc_link_conditions",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_json_includes_link_conditions_by_default(test_app: Sphinx):
    """Test that the default config includes link conditions in needs.json."""
    app = test_app
    app.build()

    needs_data = json.loads(Path(app.outdir, "needs.json").read_text())
    version = needs_data["current_version"]
    needs = needs_data["versions"][version]["needs"]

    # SPEC_001 links to REQ_001[status=="open"] — condition should be present
    assert 'REQ_001[status=="open"]' in needs["SPEC_001"]["links"]
    # SPEC_004 links to REQ_001 (no condition) — just the ID
    assert "REQ_001" in needs["SPEC_004"]["links"]
    # SPEC_005 links to REQ_001[status=="open"], REQ_003[status=="open"]
    assert 'REQ_001[status=="open"]' in needs["SPEC_005"]["links"]
    assert 'REQ_003[status=="open"]' in needs["SPEC_005"]["links"]
    # SPEC_006 links to REQ_001[["open" in tags]] — multi-bracket normalized to single
    assert 'REQ_001["open" in tags]' in needs["SPEC_006"]["links"]


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "srcdir": "doc_test/doc_link_conditions",
            "no_plantuml": True,
            "confoverrides": {"needs_json_include_link_conditions": False},
        }
    ],
    indirect=True,
)
def test_json_excludes_link_conditions_when_disabled(test_app: Sphinx):
    """Test that conditions are stripped from needs.json when config is False."""
    app = test_app
    app.build()

    needs_data = json.loads(Path(app.outdir, "needs.json").read_text())
    version = needs_data["current_version"]
    needs = needs_data["versions"][version]["needs"]

    # SPEC_001 links to REQ_001 — condition should be stripped
    assert needs["SPEC_001"]["links"] == ["REQ_001"]
    # SPEC_004 links to REQ_001 — unchanged (no condition)
    assert needs["SPEC_004"]["links"] == ["REQ_001"]
    # SPEC_005 — both links should have conditions stripped
    assert set(needs["SPEC_005"]["links"]) == {"REQ_001", "REQ_003"}
    # SPEC_006 — condition stripped
    assert needs["SPEC_006"]["links"] == ["REQ_001"]
