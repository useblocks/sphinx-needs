import sys
import types
from pathlib import Path

import pytest
from sphinx.testing.util import SphinxTestApp

from sphinx_needs.api import add_need_type, get_need_types


@pytest.fixture()
def add_extension1():
    dummy_code = """
def setup(app):
    from sphinx_needs.api import get_need_types

    def after_config(app, config):
        print(get_need_types(app))

    # app.connect('config-inited', after_config)
    print(get_need_types(app))
    return {'version': '0.1'}
    """
    dummy_extension = types.ModuleType("dummy_extension.dummy")
    exec(dummy_code, dummy_extension.__dict__)
    sys.modules["dummy_extension.dummy"] = dummy_extension
    yield
    sys.modules.pop("dummy_extension.dummy")


@pytest.fixture()
def add_extension2():
    dummy_code = """
def setup(app):
    return {'version': '0.1'}
"""
    dummy_extension = types.ModuleType("dummy_extension.dummy")
    exec(dummy_code, dummy_extension.__dict__)
    sys.modules["dummy_extension.dummy"] = dummy_extension
    yield
    sys.modules.pop("dummy_extension.dummy")


@pytest.mark.usefixtures("add_extension1")
@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_basic",
            "no_plantuml": True,
            "confoverrides": {"extensions": ["sphinx_needs", "dummy_extension.dummy"]},
        }
    ],
    indirect=True,
)
def test_api_configuration(test_app: SphinxTestApp):
    app = test_app

    app.build()
    assert app._warning.getvalue() == ""

    html = Path(app.outdir, "index.html").read_text()
    assert html is not None


@pytest.mark.usefixtures("add_extension2")
@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_basic",
            "no_plantuml": True,
            "confoverrides": {"extensions": ["sphinx_needs", "dummy_extension.dummy"]},
        }
    ],
    indirect=True,
)
def test_api_get_types(test_app: SphinxTestApp):
    app = test_app

    need_types = get_need_types(app)
    assert set(need_types) == {"story", "spec", "impl", "test"}


@pytest.mark.usefixtures("add_extension2")
@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_basic",
            "no_plantuml": True,
            "confoverrides": {"extensions": ["sphinx_needs", "dummy_extension.dummy"]},
        }
    ],
    indirect=True,
)
def test_api_add_type(test_app: SphinxTestApp, snapshot):
    app = test_app

    add_need_type(app, "awesome", "Awesome", "AW_", "#000000", "cloud")
    need_types = app.config.needs_types
    assert need_types == snapshot

    Path(app.srcdir, "other_api.rst").write_text(
        """
:orphan:

.. awesome:: my awesome need
    :id: AW_001
        """
    )

    app.build()
    assert app._warning.getvalue() == ""

    html = Path(app.outdir, "other_api.html").read_text()
    assert html is not None
    assert "my awesome need" in html
