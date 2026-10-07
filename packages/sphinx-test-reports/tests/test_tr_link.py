"""``tr_link``, the dynamic function, on the usage ``docs/functions.rst`` documents."""

import pytest

from sphinx_needs.data import SphinxNeedsData


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/tr_link_documented"}],
    indirect=True,
)
def test_the_documented_usage_builds_without_a_warning(test_app):
    """``[[tr_link('classname', 'title')]]`` on a test-case and on a test-file (#1949).

    The test fields are registered on EVERY need with the value ``None``, so the
    function's old guard -- on the KEY -- never fired for a need that is not a test-case,
    and ``None.split`` raised: a warning per such need, and a failed ``-W`` build. The
    warning stream captured here is what ``-W`` turns into an error, so an empty stream
    is the ``-W`` build passing. The case's own links resolved all along, which is why
    the crash went unnoticed; they are asserted so that a fix which silences the warning
    by returning nothing is red too.
    """
    app = test_app
    app.build()
    assert app._warning.getvalue() == ""

    needs = dict(SphinxNeedsData(app.env).get_needs_view())
    # the test-case links the need whose title is its classname
    assert needs["TESTLINK_1"]["links"] == ["TESTSPEC_001"]
    # the test-file has no classname, so it links nothing -- and raises nothing
    assert needs["TESTFILE_1"]["links"] == []
    assert needs["TESTFILE_1"]["classname"] is None
