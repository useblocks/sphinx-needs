import json
import os
import subprocess
from pathlib import Path

import pytest
from sphinx.util.console import strip_colors
from syrupy.filters import props


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/need_constraints",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_need_constraints(test_app, snapshot):
    app = test_app
    app.build()

    warnings = (
        strip_colors(test_app._warning.getvalue())
        .replace(str(test_app.srcdir) + os.path.sep, "<srcdir>/")
        .splitlines()
    )

    # check this isolated as Sphinx version 7 and 8 behave differently for warning type logs
    assert any(
        "undefined label: 'needs_constraint_failed_options'" in w for w in warnings
    )

    # TODO here we remove some spurious warnings that should be fixed properly
    warnings = {
        w
        for w in warnings
        if "Aborted attempted copy" not in w
        and "cannot cache unpickable configuration value" not in w
        and "cannot cache unpickleable configuration value" not in w
        and "undefined label: 'needs_constraint_failed_options'" not in w
        and "is already registered" not in w
    }
    # TODO(mh) ignore warning order and improve debugging which warning failed
    expected_warnings = {
        "<srcdir>/index.rst:11: WARNING: Constraint 'critical' in tags for need SP_TOO_002 FAILED! severity: CRITICAL None [needs.constraint]",
        "<srcdir>/index.rst:32: WARNING: Constraint 'critical' in tags for need SP_3EBFA FAILED! severity: CRITICAL None [needs.constraint]",
        "<srcdir>/index.rst:39: WARNING: Constraint 'team_requirement' in links for need SP_CA3FB FAILED! severity: MEDIUM None [needs.constraint]",
        "<srcdir>/style_test.rst:4: WARNING: Constraint 'critical' in tags for need TEST_STYLE FAILED! severity: CRITICAL None [needs.constraint]",
        "<srcdir>/style_test.rst:11: WARNING: Constraint 'team_requirement' in links for need TEST_STYLE2 FAILED! severity: MEDIUM None [needs.constraint]",
        "WARNING: invalid_status: failed",
        "\t\tfailed needs: 8 (SP_TOO_001, SP_TOO_002, SECURITY_REQ, SP_109F4, SP_3EBFA, SP_CA3FB, TEST_STYLE, TEST_STYLE2)",
        "\t\tused filter: status not in ['open', 'closed', 'done', 'example_2', 'example_3'] [needs.warnings]",
    }
    # Debug output for mismatched warnings
    if set(warnings) != set(expected_warnings):
        warnings_only = set(warnings) - set(expected_warnings)
        expected_only = set(expected_warnings) - set(warnings)
        if warnings_only:
            raise AssertionError(f"Unexpected warnings found: {warnings_only}")
        if expected_only:
            raise AssertionError(f"Expected warnings missing: {expected_only}")

    json_text = Path(app.outdir, "needs.json").read_text()
    needs_data = json.loads(json_text)
    assert needs_data == snapshot(exclude=props("created", "project", "creator"))

    srcdir = Path(app.srcdir)
    out_dir = srcdir / "_build"

    # Check return code when "-W --keep-going" not used
    out_normal = subprocess.run(
        ["sphinx-build", "-M", "html", srcdir, out_dir], capture_output=True
    )
    assert out_normal.returncode == 0

    # Check return code when only "-W" is used
    out_w = subprocess.run(
        ["sphinx-build", "-M", "html", srcdir, out_dir, "-W"], capture_output=True
    )
    assert out_w.returncode >= 1

    # test if constraints_results / constraints_passed is properly set
    html = Path(app.outdir, "index.html").read_text()
    assert (
        "<span class=\"needs_label\">constraints_results: </span>{'critical': {'check_0': False}}</span>"
        in html
    )
    assert '<span class="needs_label">constraints_passed: </span>False</span>' in html

    # test force_style
    html1 = Path(app.outdir, "style_test.html").read_text()
    assert "red_bar" in html1
    assert "red_border" not in html1

    # test medium severity without force_style, appends to style
    assert "blue_border, yellow_bar" in html1


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/need_constraints_failed",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_need_constraints_config(test_app):
    test_app.build()
    warnings = (
        strip_colors(test_app._warning.getvalue())
        .replace(str(test_app.srcdir) + os.path.sep, "<srcdir>/")
        .splitlines()
    )
    assert warnings == [
        "<srcdir>/index.rst:4: WARNING: Need could not be created: Constraints {'non_existing'} not in 'needs_constraints'. [needs.create_need]"
    ]
