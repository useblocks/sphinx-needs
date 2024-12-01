import json
import os
import subprocess
from pathlib import Path

import pytest
from sphinx.util.console import strip_colors
from syrupy.filters import props


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/need_constraints"}],
    indirect=True,
)
def test_need_constraints(test_app, snapshot):
    app = test_app
    app.build()

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
