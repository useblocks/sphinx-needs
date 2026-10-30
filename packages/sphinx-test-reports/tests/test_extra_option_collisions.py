"""A ``tr_extra_options`` name is checked against the fields the directives set (#2181).

The directives pass their need's fields to sphinx-needs in one mapping: the fields each
sets itself (``result``, ``cases``, ...), the report-path and source-location fields under
their configured names, and the configured extra options. An extra option named like one
of the others used to reach ``add_need`` twice and end the build with a bare ``TypeError``;
in one mapping it would override the directive's own value without a word. So the name is
refused where the configuration is read, naming the option, as a name the directives read
as their own OPTION already is (#2162).

A name no directive sets is an ordinary field, whatever it is called: ``state``, which
``add_need`` took as a parameter of its own (#2392).
"""

import io

import pytest

from sphinx_needs.data import SphinxNeedsData
from sphinx_test_reports.exceptions import InvalidConfigurationError

REPORT = (
    b'<testsuites><testsuite name="s1" tests="1">'
    b'<testcase classname="c1" name="t1" time="0.5"/>'
    b"</testsuite></testsuites>"
)

#: a test-file, a test-suite and a test-case of the report, each setting the extra option
PAGE = (
    "Probe\n=====\n\n"
    ".. test-file:: F\n   :id: TF_001\n   :file: r.xml\n   :{option}: from-the-option\n\n"
    ".. test-suite:: S\n   :id: TS_001\n   :file: r.xml\n   :suite: s1\n"
    "   :{option}: from-the-option\n\n"
    ".. test-case:: C\n   :id: TC_001\n   :file: r.xml\n   :suite: s1\n   :case: t1\n"
    "   :{option}: from-the-option\n"
)


def _project(tmp_path, conf, option):
    src = tmp_path / "src"
    src.mkdir()
    (src / "conf.py").write_text(
        'extensions = ["sphinx_needs", "sphinx_test_reports"]\n' + conf,
        encoding="utf-8",
    )
    (src / "index.rst").write_text(PAGE.format(option=option.lower()), encoding="utf-8")
    (src / "r.xml").write_bytes(REPORT)
    return src


def _built_values(app, name):
    needs = SphinxNeedsData(app.env).get_needs_view()
    return {
        need_id: needs[need_id].get(name) for need_id in ("TF_001", "TS_001", "TC_001")
    }


@pytest.mark.parametrize(
    "name",
    [
        # the fields a directive sets itself, beside its options
        "result",
        "time",
        "case_name",
        "case_parameter",
        "style",
        "suites",
        "cases",
        "passed",
        "skipped",
        "failed",
        "errors",
        # the core fields the creation call is given as its own arguments
        "title",
        "content",
        "type",
        # the source-location pair, under its default names
        "case_file",
        "case_line",
    ],
)
def test_an_extra_option_named_like_a_field_a_directive_sets_is_refused(
    make_app, tmp_path, clean_docutils_registry, name
):
    """#2181. Before: ``result`` crashed the build (``TypeError: add_need() got multiple
    values for keyword argument 'result'``); ``case_file`` and ``case_line`` overrode the
    test's source location silently. Should the check go, the build passes with the
    option's value in the field, and the failure below says so."""
    src = _project(tmp_path, f'tr_extra_options = ["{name}"]\n', name)
    with pytest.raises(
        InvalidConfigurationError, match=f"tr_extra_options holds '{name}'"
    ):
        app = make_app("html", srcdir=src, freshenv=True)
        app.build()
        pytest.fail(f"built, the field holding {_built_values(app, name)!r}")


def test_an_extra_option_named_like_a_renamed_field_is_refused(
    make_app, tmp_path, clean_docutils_registry
):
    """The report-path field under a name of the project's choosing is one of them."""
    src = _project(
        tmp_path,
        'tr_file_option = "report"\ntr_extra_options = ["report"]\n',
        "report",
    )
    with pytest.raises(
        InvalidConfigurationError, match="tr_extra_options holds 'report'"
    ):
        app = make_app("html", srcdir=src, freshenv=True)
        app.build()
        pytest.fail(f"built, the field holding {_built_values(app, 'report')!r}")


def test_an_extra_option_of_the_declarative_file_is_refused_alike(
    make_app, tmp_path, clean_docutils_registry
):
    """``[test_reports] extra_options`` becomes ``tr_extra_options``: the same check."""
    src = _project(tmp_path, "", "result")
    (src / "ubproject.toml").write_text(
        '[test_reports]\nextra_options = ["result"]\n', encoding="utf-8"
    )
    with pytest.raises(
        InvalidConfigurationError, match="tr_extra_options holds 'result'"
    ):
        app = make_app("html", srcdir=src, freshenv=True)
        app.build()
        pytest.fail(f"built, the field holding {_built_values(app, 'result')!r}")


def test_the_value_of_a_field_a_directive_sets_is_the_report_s(
    make_app, tmp_path, clean_docutils_registry
):
    """The provenance the refusal protects: with no extra option of its name, the
    test-case's ``result`` and ``time`` are the report's."""
    src = _project(tmp_path, 'tr_extra_options = ["owner"]\n', "owner")
    warning = io.StringIO()
    app = make_app("html", srcdir=src, freshenv=True, warning=warning)
    app.build()
    assert warning.getvalue() == ""
    need = SphinxNeedsData(app.env).get_needs_view()["TC_001"]
    assert (need["result"], need["time"], need["owner"]) == (
        "passed",
        "0.5",
        "from-the-option",
    )


def test_an_extra_option_named_state_is_an_ordinary_field(
    make_app, tmp_path, clean_docutils_registry
):
    """#2392. Before: ``TypeError: add_need() got multiple values for keyword argument
    'state'`` -- ``add_need``'s parser state."""
    src = _project(tmp_path, 'tr_extra_options = ["state"]\n', "state")
    warning = io.StringIO()
    app = make_app("html", srcdir=src, freshenv=True, warning=warning)
    app.build()
    assert warning.getvalue() == ""
    assert _built_values(app, "state") == dict.fromkeys(
        ("TF_001", "TS_001", "TC_001"), "from-the-option"
    )


JSON_MAPPING = """
tr_json_mapping = {
    "clash": {
        "testsuite": {
            "name": (["name"], "unknown"),
            "tests": (["tests"], 0),
            "errors": (["errors"], 0),
            "failures": (["failures"], 0),
            "skips": (["skips"], 0),
            "passed": (["passed"], 0),
            "time": (["time"], 0),
            "testcases": (["testcase"], []),
        },
        "testcase": {
            "name": (["name"], "unknown"),
            "classname": (["classname"], "unknown"),
            "file": (["file"], "unknown"),
            "line": (["line"], -1),
            "time": (["time"], 0),
            "result": (["result"], "passed"),
            "type": (["type"], ""),
            "text": (["text"], ""),
            "message": (["message"], ""),
            "system-out": (["system-out"], ""),
            "case_name": (["case_name"], ""),
        },
    }
}
"""

JSON_REPORT = (
    b'[{"name": "s1", "tests": 1, "errors": 0, "failures": 0, "skips": 0, "passed": 1,'
    b' "time": 1, "testcase": [{"name": "t1", "classname": "c1", "result": "passed",'
    b' "case_name": "from-the-report"}]}]'
)


def test_a_report_value_named_like_a_field_a_directive_sets_refuses_the_need(
    make_app, tmp_path, clean_docutils_registry
):
    """A JSON report mapped to a key the directive sets itself (``case_name``) reached
    ``add_need`` twice and crashed; it refuses the need, with the directive's warning,
    rather than override the directive's value."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "conf.py").write_text(
        'extensions = ["sphinx_needs", "sphinx_test_reports"]\n' + JSON_MAPPING,
        encoding="utf-8",
    )
    (src / "index.rst").write_text(
        "Probe\n=====\n\n"
        ".. test-case:: C\n   :id: TC_001\n   :file: r.json\n   :suite: s1\n"
        "   :case: t1\n",
        encoding="utf-8",
    )
    (src / "r.json").write_bytes(JSON_REPORT)
    warning = io.StringIO()
    app = make_app("html", srcdir=src, freshenv=True, warning=warning)
    app.build()
    assert (
        "index.rst:4: WARNING: Need could not be created: ['case_name'] given by the "
        "report or the configuration, and set by the directive itself"
    ) in warning.getvalue()
    assert "TC_001" not in SphinxNeedsData(app.env).get_needs_view()
