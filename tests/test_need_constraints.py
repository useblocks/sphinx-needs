from pathlib import Path

import pytest


@pytest.mark.parametrize("test_app", [{"buildername": "html", "srcdir": "doc_test/need_constraints"}], indirect=True)
def test_need_constraints(test_app):
    app = test_app
    app.build()

    # stdout warnings
    warning = app._warning
    warnings = warning.getvalue()

    # check multiple warning registration
    assert 'invalid_status for "warnings" is already registered.' in warnings
