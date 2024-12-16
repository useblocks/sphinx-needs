import hashlib
import os
from pathlib import Path

import pytest

json_path = os.path.join(os.path.dirname(__file__), "doc_test/utils", "json_data.json")


def test_init_json_parser():
    from sphinxcontrib.test_reports.jsonparser import JsonParser

    parser = JsonParser(json_path)
    assert parser is not None


def test_parse_json_data():
    from sphinxcontrib.test_reports.jsonparser import JsonParser

    json_mapping = {
        "json_config": {
            "testsuite": {
                "name": (["name"], "unknown"),
                "tests": (["tests"], "unknown"),
                "errors": (["errors"], "unknown"),
                "failures": (["failures"], "unknown"),
                "skips": (["skips"], "unknown"),
                "passed": (["passed"], "unknown"),
                "time": (["time"], "unknown"),
                "testcases": (["testcase"], "unknown"),
            },
            "testcase": {
                "name": (["name"], "unknown"),
                "classname": (["classname"], "unknown"),
                "file": (["file"], "unknown"),
                "line": (["line"], "unknown"),
                "time": (["time"], "unknown"),
                "result": (["result"], "unknown"),
                "type": (["type"], "unknown"),
                "text": (["text"], "unknown"),
                "message": (["message"], "unknown"),
                "system-out": (["system-out"], "unknown"),
            },
        }
    }

    mapping = list(json_mapping.values())[0]
    parser = JsonParser(json_path, json_mapping=mapping)
    results = parser.parse()
    assert results is not None
    assert len(results) == 1
    assert len(results[0]["testcases"]) == 3
    assert results[0]["testcases"][1]["result"] == "passed"


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/json_parser"}],
    indirect=True,
)
def test_json_parser_build_html(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    # Check TestFile need object
    test_id = "PARSER_JSON_001"
    assert '<span class="needs_data">Test-File</span>' in html
    assert "JSON Parser Test" in html
    assert "PARSER_JSON_001" in html
    assert html.count('<span class="needs_data">Test-File</span>') == 1

    # Check TestSuite need object(s)
    suite_name = "test suite 1"
    hash_s = hashlib.sha1(suite_name.encode("UTF-8")).hexdigest()
    suite_id = f"{test_id}_{hash_s.upper()[: app.config.tr_suite_id_length]}"

    assert '<span class="needs_data">Test-Suite</span>' in html
    assert suite_name in html
    assert suite_id in html
    assert html.count('<span class="needs_data">Test-Suite</span>') == 1

    # Check TestCase need object(s)
    case_name = "test case 2"
    case_classname = "class name 2"
    hash_c = hashlib.sha1(case_classname.encode("UTF-8") + case_name.encode("UTF-8")).hexdigest()
    case_id = f"{suite_id}_{hash_c.upper()[: app.config.tr_case_id_length]}"

    assert '<span class="needs_data">Test-Case</span>' in html
    assert case_name in html
    assert case_id in html
    # Check number of testcases
    assert html.count('<span class="needs_data">Test-Case</span>') == 3


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/json_parser_complex"}],
    indirect=True,
)
def test_json_complex_parser_build_html(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()

    assert '<span class="needs_data">Test-File</span>' in html
    assert "JSON Parser Test" in html
    assert "PARSER_JSON_001" in html

    assert "test case 2" in html
