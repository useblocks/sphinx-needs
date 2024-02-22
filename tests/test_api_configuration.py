import sys
import types
from pathlib import Path

import pytest

dummy_code = """
def setup(app):
    return {'version': '0.1'}
"""

dummy_extension = types.ModuleType("dummy_extension.dummy")
exec(dummy_code, dummy_extension.__dict__)
sys.modules["dummy_extension.dummy"] = dummy_extension


@pytest.mark.parametrize(
    "test_app", [{"buildername": "html", "srcdir": "doc_test/api_doc"}], indirect=True
)
def test_api_get_types(test_app):
    from sphinx_needs.api import get_need_types

    app = test_app

    need_types = get_need_types(app)
    assert set(need_types) == {"story", "spec", "impl", "test"}


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/api_doc_awesome"}],
    indirect=True,
)
def test_api_add_type(test_app, snapshot):
    from sphinx_needs.api import add_need_type

    app = test_app

    add_need_type(app, "awesome", "Awesome", "AW_", "#000000", "cloud")
    need_types = app.config.needs_types
    assert need_types == snapshot

    app.builder.build_all()
    html = Path(app.outdir, "index.html").read_text()
    assert html is not None
    assert "Awesome spec" in html
