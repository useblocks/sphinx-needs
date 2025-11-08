import sys
import textwrap
import types
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from sphinx.testing.util import SphinxTestApp

from sphinx_needs.api import add_need_type, get_need_types
from sphinx_needs.exceptions import NeedsConfigException


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


def test_api_add_extra_option(
    tmpdir: Path,
    make_app: Callable[[], SphinxTestApp],
    write_fixture_files: Callable[[Path, dict[str, Any]], None],
    get_warnings_list,
):
    content = {
        "conf": textwrap.dedent(
            """
            extensions = ['sphinx_needs']
            
            def setup(app):
                from sphinx_needs.api import add_extra_option
                add_extra_option(app, 'my_extra_option', description='My extra option')
                return {'version': '0.1'}
            """
        ),
        "rst": textwrap.dedent(
            """
            Title
            =====

            .. req:: a req
                :id: REQ_1
                :my_extra_option: extra option value
            """
        ),
    }
    write_fixture_files(tmpdir, content)
    app: SphinxTestApp = make_app(srcdir=Path(tmpdir), freshenv=True)
    app.build()

    warnings = get_warnings_list(app)
    assert len(warnings) == 0, "\n".join(warnings)

    html = Path(app.outdir, "index.html").read_text()
    assert html is not None
    assert "extra option value" in html

    assert app.statuscode == 0


def test_api_add_extra_option_schema(
    tmpdir: Path,
    make_app: Callable[[], SphinxTestApp],
    write_fixture_files: Callable[[Path, dict[str, Any]], None],
    get_warnings_list,
):
    content = {
        "conf": textwrap.dedent(
            """
            extensions = ['sphinx_needs']
            
            def setup(app):
                from sphinx_needs.api import add_extra_option
                add_extra_option(
                    app,
                    'my_extra_option',
                    description='My extra option',
                    schema={
                        'type': 'integer',
                        'maximum': 10,
                    }
                )
                return {'version': '0.1'}
            """
        ),
        "rst": textwrap.dedent(
            """
            Title
            =====

            .. req:: a req
                :id: REQ_1
                :my_extra_option: 8
            """
        ),
    }
    write_fixture_files(tmpdir, content)
    app: SphinxTestApp = make_app(srcdir=Path(tmpdir), freshenv=True)
    app.build()

    warnings = get_warnings_list(app)
    assert len(warnings) == 0, "\n".join(warnings)

    html = Path(app.outdir, "index.html").read_text()
    assert html is not None
    assert "8" in html

    assert app.statuscode == 0


def test_api_add_extra_option_schema_wrong(
    tmpdir: Path,
    make_app: Callable[[], SphinxTestApp],
    write_fixture_files: Callable[[Path, dict[str, Any]], None],
    snapshot,
):
    content = {
        "conf": textwrap.dedent(
            """
            extensions = ['sphinx_needs']
            
            def setup(app):
                from sphinx_needs.api import add_extra_option
                add_extra_option(
                    app,
                    'my_extra_option',
                    description='My extra option',
                    schema={
                        'type': 'integer',
                        'not_exist': 10,
                    }
                )
                return {'version': '0.1'}
            """
        ),
        "rst": textwrap.dedent(
            """
            Title
            =====

            .. req:: a req
                :id: REQ_1
                :my_extra_option: 8
            """
        ),
    }
    write_fixture_files(tmpdir, content)
    with pytest.raises(NeedsConfigException) as excinfo:
        app = make_app(srcdir=Path(tmpdir), freshenv=True)
        app.build()

    assert str(excinfo.value) == snapshot
