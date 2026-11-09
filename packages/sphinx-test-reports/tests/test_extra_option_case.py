"""A ``tr_extra_options`` name matches a directive option ignoring case, in MyST too.

docutils lowercases a reStructuredText option's name, so each extra option is registered
in lower case and its value stored under the configured spelling (#2115): ``:TestType:``
and ``:testtype:`` both set ``TestType``. myst-parser hands the name over as written and
looks it up exactly, so in MyST only ``:testtype:`` worked and ``:TestType:`` -- the
configured spelling itself -- was an unknown option, its value lost. Now every spelling
lands under ``TestType`` in both markups, as Sphinx-Needs matches its own fields.

Where MyST writes one extra option twice in two cases, the lower-case spelling, which
matched before, keeps its value and the other is reported and ignored.
"""

import io
import re
from pathlib import Path

import pytest

from sphinx_needs.data import SphinxNeedsData
from sphinx_test_reports.exceptions import InvalidConfigurationError

UTILS = Path(__file__).parent / "doc_test" / "utils"

CONF = (
    'extensions = ["sphinx_needs", "sphinx_test_reports", "myst_parser"]\n'
    'tr_extra_options = ["TestType"]\n'
)


def _build(make_app, tmp_path, host, options, conf=CONF):
    """A ``test-file`` with ``options`` in the host's markup; ``(needs, warnings)``."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "conf.py").write_text(conf, encoding="utf-8")
    (src / "g.xml").write_bytes((UTILS / "gtest_data.xml").read_bytes())
    written = [("id", "TF_XXX"), ("file", "g.xml"), ("auto_suites", ""), *options]
    if host == "rst":
        body = ".. test-file:: F\n" + "".join(
            f"   :{key}: {value}".rstrip() + "\n" for key, value in written
        )
        (src / "index.rst").write_text("Probe\n=====\n\n" + body, encoding="utf-8")
    else:
        body = "```{test-file} F\n" + "".join(
            f":{key}: {value}".rstrip() + "\n" for key, value in written
        )
        (src / "index.md").write_text("# Probe\n\n" + body + "```\n", encoding="utf-8")
    warning = io.StringIO()
    app = make_app("html", srcdir=src, warning=warning, freshenv=True)
    app.build()
    return dict(SphinxNeedsData(app.env).get_needs_view()), warning.getvalue()


@pytest.mark.parametrize("host", ["rst", "myst"])
@pytest.mark.parametrize("written", ["TestType", "testtype", "TESTTYPE"])
def test_an_extra_option_is_set_by_any_case(
    make_app, tmp_path, clean_docutils_registry, host, written
):
    needs, warnings = _build(make_app, tmp_path, host, [(written, "unit")])
    assert warnings == ""
    assert needs["TF_XXX"]["TestType"] == "unit"
    # the expansion's suites are handed the option too
    suites = [n for i, n in needs.items() if i.startswith("TF_XXX_")]
    assert suites
    assert all(n["TestType"] == "unit" for n in suites)


@pytest.mark.parametrize(
    ("options", "ignored", "kept"),
    [
        ([("testtype", "unit"), ("TestType", "system")], "TestType", "testtype"),
        ([("TestType", "system"), ("testtype", "unit")], "TestType", "testtype"),
        ([("TESTTYPE", "unit"), ("TestType", "system")], "TestType", "TESTTYPE"),
    ],
    ids=["lower-first", "lower-second", "neither-lower"],
)
def test_myst_writing_an_extra_option_twice_keeps_the_value_set_before(
    make_app, tmp_path, clean_docutils_registry, options, ignored, kept
):
    """MyST ``:testtype:`` set the field before and ``:TestType:`` was unknown: the
    value stays the lower-case one's (else the first written), and the other is
    reported, once (the expansion's suites are not each told again), naming the kept
    option as it is written."""
    needs, warnings = _build(make_app, tmp_path, "myst", options)
    assert needs["TF_XXX"]["TestType"] == "unit"
    assert warnings.count("WARNING:") == 1
    assert f"Option '{ignored}' repeats option '{kept}'" in warnings


def test_a_built_in_option_keeps_myst_matching_it_exactly(
    make_app, tmp_path, clean_docutils_registry
):
    """The rule is for the configured names: a directive's own option (``:ID:``) is
    myst-parser's to match, exactly, as before: ``ID`` is unknown although ``id`` is
    allowed. myst-parser 5.2 rewords the warning, from ``Unknown option keys: ['ID']``
    to ``Unknown option key: 'ID'``; both are accepted."""
    _, warnings = _build(make_app, tmp_path, "myst", [("ID", "TF_YYY")])
    assert re.search(
        r"Unknown option keys?: \[?'ID'\]? \(allowed: \[[^\]]*'id'", warnings
    )


def test_an_extra_option_equal_to_a_field_the_directives_set_but_for_case_is_refused(
    make_app, tmp_path
):
    """``Result`` would land beside ``result``, a field a test case sets itself."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "conf.py").write_text(
        'extensions = ["sphinx_needs", "sphinx_test_reports"]\n'
        'tr_extra_options = ["Result"]\n',
        encoding="utf-8",
    )
    (src / "index.rst").write_text("Probe\n=====\n", encoding="utf-8")
    with pytest.raises(InvalidConfigurationError, match=r"'Result'.*'result'"):
        make_app("html", srcdir=src, freshenv=True)
