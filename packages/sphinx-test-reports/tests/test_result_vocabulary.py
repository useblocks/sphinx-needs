"""The ``result`` field's vocabulary, and the one place it is decided.

A test case's ``result`` used to be whatever the input spelled it: the JUnit
parser passed the name of the ``<testcase>`` child element through verbatim
(``failure``), the JSON parser passed the report's own value through, and the
two states with no element of their own -- ``passed`` and ``disabled`` -- were
spelled as participles because nothing forced a choice. So one product said
``failure`` for a single case and ``failed`` for the count of them
(``fields.FIELDS``), and the documented value and the documented example
disagreed.

These tests pin the vocabulary down: every parser maps its input onto the same
participles, and the mapping is the only place that decides. The part-level
``kind`` is deliberately *not* normalised -- it names the XML element the
evidence came from, which is what the rendered evidence heading reports.

This is the half that needs Sphinx: the shipped report template rendering the vocabulary.
The parsers' half is ub-test-reports', ``packages/ub-test-reports/tests/test_result_vocabulary.py``.
"""

import pytest


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/default_tr_template"}],
    indirect=True,
)
def test_the_shipped_report_template_counts_a_failed_case(test_app):
    """The template that ``tr_report_template`` defaults to filters on the
    ``result`` value, and every fixture that exercises ``test-report`` used to
    override it -- so a rename could empty its "Failed test cases" table and
    its count without a single test noticing.
    """
    from pathlib import Path

    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()

    assert "Failed test cases: 1" in html
