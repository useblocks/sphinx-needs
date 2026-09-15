"""Regressions for the three directive changes the workspace import made.

The first three tests each build a fixture project the suite did not have before: the
shape that triggered each problem was exactly a shape none of the existing fixtures
covered, which is why nothing caught any of them. The fourth is the positive control for
the third.
"""

import re
import warnings
from pathlib import Path

import pytest
from docutils import nodes

from sphinxcontrib.test_reports.exceptions import TestReportFileNotSetError

#: docutils' deprecation for ``Text()``'s second argument. ONE constant, shared by the fence in
#: the missing-file test and by its positive control, so that the two cannot drift apart. It is
#: anchored with ``^`` because the two read it differently: ``warnings.filterwarnings`` applies
#: ``re.match``, ``pytest.warns(match=...)`` applies ``re.search``, and without the anchor a
#: docutils message that gained a prefix would still satisfy the control while the fence stopped
#: matching.
RAWSOURCE_DEPRECATION = r'^nodes\.Text: initialization argument "rawsource"'


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/env_report_raw_no_data"}],
    indirect=True,
)
def test_raw_env_report_without_a_data_option_builds(test_app):
    """``:raw:`` and ``:env:`` with no ``:data:`` used to raise ``TypeError``.

    That branch iterated ``self.data_option_list`` outside the ``is not None`` guard its
    sibling branch keeps it inside, and ``:data:`` is optional -- so the list is ``None``
    and the loop raised. No existing ``test-env`` fixture had that combination -- they
    carried ``:data:`` with ``:env:``, the same with ``:raw:``, or no options at all, which
    takes neither branch -- so it had no coverage.
    """
    app = test_app
    app.build()
    html = Path(app.outdir / "index.html").read_text()

    # the requested environments render, and nothing else does
    assert "py35" in html
    assert "flake8" in html
    assert "pylint" not in html


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/test_file_no_file"}],
    indirect=True,
)
def test_a_test_file_without_a_file_option_raises_a_readable_error(test_app):
    """A ``test-file`` written with no ``:file:`` used to crash with ``TypeError``.

    ``prepare_basic_options`` sliced ``self.options.get("file")`` -- ``None`` when the
    option is absent -- before the guard in ``load_test_file`` could run, so that guard was
    dead code and the build died on ``TypeError: 'NoneType' object is not subscriptable``.
    Measured: that is exactly what ``app.build()`` raised on the published code, and it
    reaches this call unwrapped, as does the error below. Every existing ``test-file``
    fixture carried a ``:file:``.
    """
    with pytest.raises(TestReportFileNotSetError, match="Option test_file must be set"):
        test_app.build()


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/test_file_missing"}],
    indirect=True,
)
def test_a_missing_test_file_renders_an_error_node(test_app):
    """The "not found" path, which no other fixture reaches, and its ``nodes.Text`` call.

    That call used to pass a second argument. docutils ignores it, deprecates it and
    removes it only in Docutils 2.0, so the old call still WORKS on every supported
    docutils: an assertion on the rendered node alone passes either way, which was
    measured. The filter below is what makes this a fence. It turns exactly that
    deprecation into an error, and only when it is raised from this package's own code:
    docutils warns with ``stacklevel=2``, which attributes the warning to the caller, so
    ``module=`` matches ``sphinxcontrib.test_reports.directives.test_file`` -- and the same
    deprecation raised from Sphinx or sphinx-needs during the build is left alone. Both
    directions were measured.
    """
    app = test_app
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "error",
            message=RAWSOURCE_DEPRECATION,
            category=DeprecationWarning,
            module=r"sphinxcontrib\.test_reports",
        )
        app.build()
    html = Path(app.outdir / "index.html").read_text()

    assert "Test file not found" in html
    assert "no_such_report.xml" in html


def test_the_rawsource_pattern_still_matches_docutils():
    """The positive control for the fence in the test above.

    The fence can disarm SILENTLY in two ways -- the missing-file test would then stay green
    whatever the code did -- and this fails loudly on both:

    * docutils rewords the deprecation, prefixes included: the anchored constant stops matching
      here exactly as the filter's ``re.match`` stops matching there;
    * docutils moves the warning's attribution, say by changing its ``stacklevel``: the fence's
      ``module=`` scope relies on the warning being attributed to the CALLER of ``Text()``, so
      this asserts the warning below is attributed to this file, its caller.
    """
    with pytest.warns(DeprecationWarning, match=RAWSOURCE_DEPRECATION) as record:
        nodes.Text("x", "y")
    matching = [
        w
        for w in record
        if re.match(RAWSOURCE_DEPRECATION, str(w.message), re.IGNORECASE)
    ]
    assert matching, [str(w.message) for w in record]
    here = Path(__file__).resolve()
    assert all(Path(w.filename).resolve() == here for w in matching), [
        w.filename for w in matching
    ]
