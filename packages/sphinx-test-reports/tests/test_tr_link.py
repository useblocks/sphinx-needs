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
    # the test-case links the needs whose title is its classname
    assert needs["TESTLINK_1"]["links"] == ["TESTSPEC_001", "TESTSPEC_002"]
    # the test-file has no classname, so it links nothing -- and raises nothing; not even
    # the spec titled "None", which `str(None)` would match
    assert needs["TESTFILE_1"]["links"] == []
    assert needs["TESTSPEC_NONE"]["links_back"] == []
    assert needs["TESTFILE_1"]["classname"] is None
    # compared on the TARGET's classname: only the test-case has one, so it is the one
    # link, and the needs whose classname is None (the test-file, both specs) are skipped
    assert needs["TESTSPEC_002"]["links"] == ["TESTLINK_1"]


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/tr_link_readers"}],
    indirect=True,
)
def test_the_readers_of_its_links_hold_them(test_app):
    """``tr_link`` declares what it reads (its ``test_option`` on its own need, its
    ``target_option`` on every need), so sphinx-needs computes it with the built-in
    functions, before those that read its links: a ``links_from_filter`` on them, a
    ``links`` rule's ``where`` on every need, a ``union`` over them, and a filter on
    the union. Undeclared, it ran after them all, and each read the links empty.
    """
    app = test_app
    app.build()
    assert app._warning.getvalue() == ""

    needs = dict(SphinxNeedsData(app.env).get_needs_view())
    assert [needs[i]["links"] for i in ("TEST_1", "TEST_2", "TEST_3")] == [
        ["REQ_A"],
        ["REQ_B"],
        ["REQ_A", "REQ_B"],
    ]
    assert needs["REQ_A"]["covers"] == ["TEST_1", "TEST_3"]
    assert needs["REQ_B"]["covers"] == ["TEST_2", "TEST_3"]
    assert needs["TEST_3"]["all_links"] == ["REQ_A", "REQ_B"]
    assert needs["REQ_A"]["cov_u"] == ["TEST_1", "TEST_3"]
    assert needs["REQ_A"]["verified"] == ["TEST_1", "TEST_2", "TEST_3"]
    assert needs["TEST_1"]["verified"] == ["TEST_2", "TEST_3"]
