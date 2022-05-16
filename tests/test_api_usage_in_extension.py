import imp
import sys
from pathlib import Path

import pytest

dummy_code = """
def setup(app):
    from sphinx_needs.api import get_need_types

    def after_config(app, config):
        print(get_need_types(app))

    # app.connect('config-inited', after_config)
    print(get_need_types(app))
    return {'version': '0.1'}
"""


dummy_extension = imp.new_module("dummy_extension.dummy")
exec(dummy_code, dummy_extension.__dict__)
sys.modules["dummy_extension.dummy"] = dummy_extension


@pytest.mark.parametrize("test_app", [{"buildername": "html", "srcdir": "doc_test/api_doc"}], indirect=True)
def test_api_configuration(test_app):
    app = test_app

    app.builder.build_all()
    html = Path(app.outdir, "index.html").read_text()
    assert html is not None
