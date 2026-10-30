"""What the directives hand Sphinx-Needs, field by field, beside the fields they set.

The need is created from one mapping: the directive's own fields, the report path and
source location, the extra options, the report's further values and the JUnit properties
mapped by ``tr_property_link_types``. Each name goes where the project's schema says it
belongs (a link type to the links, any other name to the fields), and the names
``add_need`` took as its own arguments (``jinja_content``, ``doctype``) go to the
creation's arguments, as they did. A core field of Sphinx-Needs no option can set is
refused at configuration as an extra option, and refuses its need as a report value.
"""

import inspect
import io
import json

import pytest

import sphinx_test_reports.directives.test_common
from sphinx_needs.api import create_need
from sphinx_needs.data import NeedsCoreFields, SphinxNeedsData
from sphinx_test_reports.directives.test_common import DIRECTIVE_FIELDS
from sphinx_test_reports.exceptions import InvalidConfigurationError

PAGE = "Probe\n=====\n\n.. req:: r1\n   :id: REQ_1\n\n.. req:: r2\n   :id: REQ_2\n\n"

CASE = (
    ".. test-case:: C\n   :id: TC_001\n   :file: {file}\n   :suite: s1\n   :case: t1\n"
)

PROPERTY_REPORT = (
    b'<testsuites><testsuite name="s1" tests="1">'
    b'<testcase classname="c1" name="t1" time="0.5"><properties>'
    b'<property name="verifies" value="REQ_1,REQ_2"/>'
    b"</properties></testcase></testsuite></testsuites>"
)

REPORT = (
    b'<testsuites><testsuite name="s1" tests="1">'
    b'<testcase classname="c1" name="t1" time="0.5"/>'
    b"</testsuite></testsuites>"
)

JSON_MAPPING = """
tr_json_mapping = {{
    "cfg": {{
        "testsuite": {{
            "name": (["name"], "unknown"), "tests": (["tests"], 0),
            "errors": (["errors"], 0), "failures": (["failures"], 0),
            "skips": (["skips"], 0), "passed": (["passed"], 0),
            "time": (["time"], 0), "testcases": (["testcase"], []),
        }},
        "testcase": {{
            "name": (["name"], "unknown"), "classname": (["classname"], "unknown"),
            "file": (["file"], "unknown"), "line": (["line"], -1),
            "time": (["time"], 0), "result": (["result"], "passed"),
            "type": (["type"], ""), "text": (["text"], ""),
            "message": (["message"], ""), "system-out": (["system-out"], ""),
            {key!r}: (["extra"], ""),
        }},
    }}
}}
"""


def _json_report(value):
    return json.dumps(
        [
            {
                "name": "s1",
                "tests": 1,
                "errors": 0,
                "failures": 0,
                "skips": 0,
                "passed": 1,
                "time": 1,
                "testcase": [
                    {
                        "name": "t1",
                        "classname": "c1",
                        "result": "passed",
                        "extra": value,
                    }
                ],
            }
        ]
    ).encode()


def _build(make_app, tmp_path, conf, rst, files):
    src = tmp_path / "src"
    src.mkdir()
    (src / "conf.py").write_text(
        'extensions = ["sphinx_needs", "sphinx_test_reports"]\n' + conf,
        encoding="utf-8",
    )
    (src / "index.rst").write_text(PAGE + rst, encoding="utf-8")
    for name, data in files.items():
        (src / name).write_bytes(data)
    warning = io.StringIO()
    app = make_app("html", srcdir=src, freshenv=True, warning=warning)
    app.build()
    return SphinxNeedsData(app.env).get_needs_view(), warning.getvalue()


# --- the links: by the project's link types -------------------------------------------


def test_a_report_value_named_like_a_link_type_is_a_link(
    make_app, tmp_path, clean_docutils_registry
):
    """A ``tr_json_mapping`` key that is a link type of the project links the need, as
    when ``add_need`` sorted the keywords itself."""
    needs, warnings = _build(
        make_app,
        tmp_path,
        'needs_links = {"blocks": {}}\n' + JSON_MAPPING.format(key="blocks"),
        CASE.format(file="r.json"),
        {"r.json": _json_report("REQ_1")},
    )
    assert warnings == ""
    assert needs["TC_001"]["blocks"] == ["REQ_1"]


def test_a_property_mapped_to_a_field_sets_the_field(
    make_app, tmp_path, clean_docutils_registry
):
    """A ``tr_property_link_types`` target that the project declares as a field holds
    the property's ids, as a field."""
    needs, warnings = _build(
        make_app,
        tmp_path,
        'needs_fields = {"owner": {"nullable": True}}\n'
        'tr_property_link_types = {"verifies": "owner"}\n',
        CASE.format(file="r.xml"),
        {"r.xml": PROPERTY_REPORT},
    )
    assert warnings == ""
    assert needs["TC_001"]["owner"] == "REQ_1;REQ_2"


def test_a_property_mapped_to_a_link_type_links_the_need(
    make_app, tmp_path, clean_docutils_registry
):
    """The control, unchanged: a target that is a link type other than ``links``."""
    needs, warnings = _build(
        make_app,
        tmp_path,
        'needs_links = {"checks": {}}\ntr_property_link_types = {"verifies": "checks"}\n',
        CASE.format(file="r.xml"),
        {"r.xml": PROPERTY_REPORT},
    )
    assert warnings == ""
    assert needs["TC_001"]["checks"] == ["REQ_1", "REQ_2"]


# --- add_need's own arguments: the creation's arguments --------------------------------

FILE = ".. test-file:: F\n   :id: TF_001\n   :file: r.xml\n{options}\n\n   body {{{{ title }}}}\n"


def test_an_extra_option_jinja_content_renders_the_content(
    make_app, tmp_path, clean_docutils_registry
):
    needs, warnings = _build(
        make_app,
        tmp_path,
        'tr_extra_options = ["jinja_content"]\n',
        FILE.format(options="   :jinja_content: yes"),
        {"r.xml": REPORT},
    )
    assert warnings == ""
    assert needs["TF_001"]["content"] == "body F"
    # the option's string, as add_need recorded it
    assert needs["TF_001"]["jinja_content"] == "yes"


def test_an_extra_option_doctype_sets_it(make_app, tmp_path, clean_docutils_registry):
    needs, warnings = _build(
        make_app,
        tmp_path,
        'tr_extra_options = ["doctype"]\n',
        FILE.format(options="   :doctype: .md"),
        {"r.xml": REPORT},
    )
    assert warnings == ""
    assert needs["TF_001"]["doctype"] == ".md"


#: the core fields no option can set, from the sources the configuration check reads: a
#: Sphinx-Needs core field that is neither a field of the field schema nor an argument of
#: ``create_need`` (those the directives set are refused as theirs)
CORE_ONLY = sorted(
    set(NeedsCoreFields)
    - {
        name
        for name, spec in NeedsCoreFields.items()
        if spec.get("add_to_field_schema")
    }
    - set(inspect.signature(create_need).parameters)
    - set().union(*DIRECTIVE_FIELDS.values())
)

#: the ones of them an extra option built with on master (#2181's round 2): ``add_need``
#: set them (``external_css``, ``is_import``), ignored them, dropped them with a
#: warning (``constraints_passed``), or made the need external (``is_external``)
BUILT_ON_MASTER = (
    "arch",
    "constraints_passed",
    "external_css",
    "external_url",
    "is_external",
    "is_import",
    "sections",
    "signature",
)


def test_the_core_fields_no_option_sets_include_those_that_built_on_master():
    assert set(BUILT_ON_MASTER) <= set(CORE_ONLY)


@pytest.mark.parametrize("name", CORE_ONLY)
def test_an_extra_option_named_like_a_core_field_no_option_sets_is_refused(
    make_app, tmp_path, clean_docutils_registry, name
):
    """A Sphinx-Needs core field that is neither a field of the field schema nor an
    argument of the creation: it set nothing a test report means (``add_need`` bound it
    as its own keyword), so it is refused where the configuration is read."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "conf.py").write_text(
        'extensions = ["sphinx_needs", "sphinx_test_reports"]\n'
        f'tr_extra_options = ["{name}"]\n',
        encoding="utf-8",
    )
    (src / "index.rst").write_text("Probe\n=====\n", encoding="utf-8")
    with pytest.raises(
        InvalidConfigurationError,
        match=f"tr_extra_options holds '{name}', which is a core field of Sphinx-Needs",
    ):
        make_app("html", srcdir=src, freshenv=True)


def test_a_report_value_named_like_a_core_field_no_option_sets_refuses_its_need(
    make_app, tmp_path, clean_docutils_registry
):
    """FR2(ii): the same name as a report value refuses the need, with the directive's
    warning."""
    needs, warnings = _build(
        make_app,
        tmp_path,
        JSON_MAPPING.format(key="external_url"),
        CASE.format(file="r.json"),
        {"r.json": _json_report("http://example.org")},
    )
    assert "TC_001" not in needs
    assert (
        "Need could not be created: {'external_url'} not in 'needs_fields' or "
        "'needs_links'." in warnings
    )


# --- style: a field-schema core field the test-case directive sets ---------------------


@pytest.mark.parametrize("declarative", [False, True])
def test_an_extra_option_style_sets_a_test_file_s_style(
    make_app, tmp_path, clean_docutils_registry, declarative
):
    conf = "" if declarative else 'tr_extra_options = ["style"]\n'
    src_files = {"r.xml": REPORT}
    if declarative:
        src_files["ubproject.toml"] = b'[test_reports]\nextra_options = ["style"]\n'
    needs, warnings = _build(
        make_app,
        tmp_path,
        conf,
        FILE.format(options="   :style: highlight"),
        src_files,
    )
    assert warnings == ""
    assert needs["TF_001"]["style"] == "highlight"


def test_an_extra_option_style_refuses_only_the_case_needs(
    make_app, tmp_path, clean_docutils_registry
):
    """A test-case sets its own ``style``: the option would override it, so its need is
    refused (it crashed the build); the file's and the suites' needs take the style."""
    needs, warnings = _build(
        make_app,
        tmp_path,
        'tr_extra_options = ["style"]\n',
        ".. test-file:: F\n   :id: TF_001\n   :file: r.xml\n   :auto_suites:\n"
        "   :auto_cases:\n   :style: highlight\n",
        {"r.xml": REPORT},
    )
    styles = {need["type"]: need["style"] for need in needs.values()}
    assert styles == {"req": None, "testfile": "highlight", "testsuite": "highlight"}
    assert (
        "Need could not be created: ['style'] given by the report or the "
        "configuration, and set by the directive itself" in warnings
    )


# --- full_title and allow_type_coercion: arguments, and a declared full_title also a field


def _record_arguments(monkeypatch) -> dict[str, dict]:
    """What each need is handed to ``create_need`` with, by need id."""
    handed: dict[str, dict] = {}
    module = sphinx_test_reports.directives.test_common
    real = module.create_need

    def recording(*args, **kwargs):
        handed[kwargs["id"]] = kwargs
        return real(*args, **kwargs)

    monkeypatch.setattr(module, "create_need", recording)
    return handed


@pytest.mark.xfail(
    strict=True, reason="FR7: a declared full_title is also the argument"
)
def test_an_extra_option_full_title_is_the_field_and_the_argument(
    make_app, tmp_path, clean_docutils_registry, monkeypatch
):
    """The extra option registers its field, which holds the value (#2392), and the
    creation is also given it as the full title, as ``add_need`` took it."""
    handed = _record_arguments(monkeypatch)
    needs, warnings = _build(
        make_app,
        tmp_path,
        'tr_extra_options = ["full_title"]\n',
        FILE.format(options="   :full_title: A much longer title"),
        {"r.xml": REPORT},
    )
    assert warnings == ""
    assert needs["TF_001"]["full_title"] == "A much longer title"
    assert (
        handed["TF_001"]["full_title"],
        handed["TF_001"]["fields"]["full_title"],
    ) == (
        "A much longer title",
        "A much longer title",
    )


@pytest.mark.xfail(strict=True, reason="FR8: allow_type_coercion is an argument")
def test_report_values_full_title_and_allow_type_coercion_are_the_arguments(
    make_app, tmp_path, clean_docutils_registry, monkeypatch
):
    """Undeclared, a report's ``full_title`` and ``allow_type_coercion`` are the
    creation's arguments, as written, and no field: the need is built."""
    handed = _record_arguments(monkeypatch)
    needs, warnings = _build(
        make_app,
        tmp_path,
        JSON_MAPPING.format(key="allow_type_coercion")
        + 'tr_json_mapping["cfg"]["testcase"]["full_title"] = (["long"], "")\n',
        CASE.format(file="r.json"),
        {
            "r.json": json.dumps(
                [
                    {
                        "name": "s1",
                        "tests": 1,
                        "errors": 0,
                        "failures": 0,
                        "skips": 0,
                        "passed": 1,
                        "time": 1,
                        "testcase": [
                            {
                                "name": "t1",
                                "classname": "c1",
                                "result": "passed",
                                "extra": "yes",
                                "long": "A much longer title",
                            }
                        ],
                    }
                ]
            ).encode()
        },
    )
    assert warnings == ""
    assert "TC_001" in needs
    kwargs = handed["TC_001"]
    assert (kwargs["allow_type_coercion"], kwargs["full_title"]) == (
        "yes",
        "A much longer title",
    )
    assert not {"allow_type_coercion", "full_title"} & set(kwargs["fields"])
