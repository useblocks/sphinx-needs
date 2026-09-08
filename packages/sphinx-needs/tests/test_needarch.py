import re
from pathlib import Path

import pytest
from syrupy.filters import props

from sphinx_needs.directives.needuml import NeedArchException
from sphinx_needs_testkit import assert_no_warnings


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needarch"}],
    indirect=True,
)
def test_doc_needarch(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text(encoding="utf8")
    assert html


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needarch_negative_tests"}],
    indirect=True,
)
def test_doc_needarch_negative(test_app):
    app = test_app

    with pytest.raises(
        NeedArchException,
        match=re.escape("Directive needarch can only be used inside a need."),
    ):
        app.build()


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needarch_jinja_func_import"}],
    indirect=True,
)
def test_doc_needarch_jinja_import(test_app, snapshot):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text(encoding="utf8")
    assert html

    # check needarch
    all_needumls = app.env._needs_all_needumls
    assert all_needumls == snapshot(exclude=props("process_time"))


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_needarch_jinja_func_need",
            "plantuml": True,
        }
    ],
    indirect=True,
)
def test_needarch_jinja_func_need(test_app, snapshot):
    app = test_app
    app.build()

    all_needumls = app.env._needs_all_needumls
    assert all_needumls == snapshot(exclude=props("process_time"))

    html = Path(app.outdir, "index.html").read_text(encoding="utf8")
    assert "as INT_001 [[../index.html#INT_001]]" in html

    assert app.statuscode == 0
    assert_no_warnings(app)
