import imp
import sys
from pathlib import Path

from sphinx_testing import with_app

dummy_code = """
def setup(app):
    return {'version': '0.1'}
"""

dummy_extension = imp.new_module("dummy_extension.dummy")
exec(dummy_code, dummy_extension.__dict__)
sys.modules["dummy_extension.dummy"] = dummy_extension


@with_app(buildername="html", srcdir="doc_test/api_doc")
def test_api_get_types(app, status, warning):
    from sphinxcontrib.needs.api import get_need_types

    need_types = get_need_types(app)
    assert "story" in need_types
    assert "req" not in need_types


@with_app(buildername="html", srcdir="doc_test/api_doc_awesome")
def test_api_add_type(app, status, warning):
    from sphinxcontrib.needs.api import add_need_type

    add_need_type(app, "awesome", "Awesome", "AW_", "#000000", "cloud")
    need_types = app.config.needs_types
    assert len(need_types) == 5
    found = False
    for need_type in need_types:
        if need_type["directive"] == "awesome":
            found = True
            assert need_type["title"] == "Awesome"
            assert need_type["prefix"] == "AW_"
            assert need_type["color"] == "#000000"
            assert need_type["style"] == "cloud"

    assert found

    app.builder.build_all()
    html = Path(app.outdir, "index.html").read_text()
    assert html is not None
    assert "Awesome spec" in html
