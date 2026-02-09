import json
import sys
import textwrap
import types
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from sphinx.testing.util import SphinxTestApp
from syrupy.filters import props

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


def test_api_add_field(
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
                from sphinx_needs.api import add_field
                add_field('my_extra_option', description='My extra field')
                return {'version': '0.1'}
            """
        ),
        "rst": textwrap.dedent(
            """
            Title
            =====

            .. req:: a req
                :id: REQ_1
                :my_extra_option: extra field value
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
    assert "extra field value" in html

    assert app.statuscode == 0


def test_api_add_field_schema(
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
                from sphinx_needs.api import add_field
                add_field(
                    'my_extra_option',
                    description='My extra field',
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


def test_api_add_field_schema_wrong(
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
                from sphinx_needs.api import add_field
                add_field(
                    'my_extra_option',
                    description='My extra field',
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


def test_api_add_field_default(
    tmpdir: Path,
    make_app: Callable[[], SphinxTestApp],
    write_fixture_files: Callable[[Path, dict[str, Any]], None],
    get_warnings_list,
    snapshot,
):
    content = {
        "conf": textwrap.dedent(
            """
            extensions = ['sphinx_needs']
            needs_build_json = True
            needs_json_remove_defaults = True
            
            def setup(app):
                from sphinx_needs.api import add_field
                add_field(
                    'my_extra_option',
                    description='My extra field',
                    default="hallo",
                    predicates=[('id == "REQ_1"', 'my predicate')]
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

            .. req:: a req
                :id: REQ_2
            """
        ),
    }
    write_fixture_files(tmpdir, content)
    app: SphinxTestApp = make_app(srcdir=Path(tmpdir), freshenv=True)
    app.build()

    assert app.statuscode == 0

    warnings = get_warnings_list(app)
    assert len(warnings) == 0, "\n".join(warnings)

    json_text = Path(app.outdir, "needs.json").read_text()
    needs_data = json.loads(json_text)
    assert needs_data == snapshot(exclude=props("created", "project", "creator"))


def test_api_add_field_default_wrong(
    tmpdir: Path,
    make_app: Callable[[], SphinxTestApp],
    write_fixture_files: Callable[[Path, dict[str, Any]], None],
    get_warnings_list,
    snapshot,
):
    content = {
        "conf": textwrap.dedent(
            """
            extensions = ['sphinx_needs']
            
            def setup(app):
                from sphinx_needs.api import add_field
                add_field(
                    'my_extra_option',
                    description='My extra field',
                    schema = {
                        'type': 'integer',
                    },
                    default="wrong default type",
                    predicates=[('id == "REQ_1"', 'wrong predicate type')]
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
    assert app.statuscode == 0

    warnings = get_warnings_list(app)
    assert warnings == [
        "add_field['my_extra_option']['default'] value is incorrect: Cannot convert 'wrong default type' to integer [needs.config]\n",
        "add_field['my_extra_option']['predicates'] value is incorrect: Cannot convert 'wrong predicate type' to integer [needs.config]\n",
    ]
