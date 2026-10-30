"""The need types each field belongs to (#2372).

A test report gives three kinds of need -- a test file, a test suite, a test case -- and
each field is carried by the kinds that set it, so the build declares it on those need
types alone. The table is ubCode's too (``FILE_NEED_FIELDS``, ``SUITE_NEED_FIELDS``,
``CASE_NEED_FIELDS`` in ``ubc_test_reports``), so it is pinned here field by field.
"""

import pytest

from ub_test_reports.fields import (
    FIELDS,
    FILE_NEED_FIELDS,
    NEED_KINDS,
    RENAMEABLE_FIELDS,
    SUITE_NEED_FIELDS,
    need_kinds,
)


@pytest.mark.parametrize(
    ("name", "role", "kinds"),
    [
        ("suites", None, ("file",)),
        ("cases", None, ("file", "suite")),
        ("passed", None, ("file", "suite")),
        ("skipped", None, ("file", "suite")),
        ("failed", None, ("file", "suite")),
        ("errors", None, ("file", "suite")),
        ("suite", None, ("suite", "case")),
        ("case", None, ("case",)),
        ("case_name", None, ("case",)),
        ("case_parameter", None, ("case",)),
        ("classname", None, ("case",)),
        ("time", None, ("case",)),
        ("result", None, ("case",)),
        # written by the converter alone, on test cases
        ("result_text", None, ("case",)),
        ("remote_url", None, ("case",)),
        # the report path is on every kind, the source location on cases
        ("file", "file_option", ("file", "suite", "case")),
        ("case_file", "source_file_option", ("case",)),
        ("case_line", "source_line_option", ("case",)),
        # an extra option (`tr_extra_options`) is on every kind
        ("owner", None, ("file", "suite", "case")),
    ],
)
def test_each_field_belongs_to_the_kinds_that_set_it(name, role, kinds):
    assert need_kinds(name, role) == kinds


def test_every_field_of_the_tables_has_a_kind():
    """No field of the declarations is left without a need type to be declared on."""
    for name in FIELDS:
        assert need_kinds(name), name
    for role in RENAMEABLE_FIELDS:
        assert need_kinds("renamed", role), role
    assert set(NEED_KINDS) == {"file", "suite", "case"}
    assert set(FILE_NEED_FIELDS) | set(SUITE_NEED_FIELDS) <= set(FIELDS)
