"""Tests for the Sphinx-free ``test-reports build needs`` CLI (TR-A).

This is the keystone of the build-system story: a test-XML to needs.json
conversion that runs as a build action *outside* Sphinx, so the docs build only
imports the result. Two properties are load-bearing and therefore tested
explicitly rather than assumed:

* the CLI must not import Sphinx -- otherwise a Bazel action pulls the whole
  documentation toolchain into the test-result conversion;
* the output must be byte-stable, because it is a cached build artifact and
  qualification evidence.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

UTILS = Path(__file__).parent / "fixtures"
GTEST_XML = UTILS / "gtest_data.xml"
PYTEST_XML = UTILS / "pytest_data.xml"


def _convert(tmp_path, *args, xml=GTEST_XML):
    """Run the converter and return (exit_code, parsed output or None)."""
    from ub_test_reports.cli import main

    output = tmp_path / "needs.json"
    code = main(["build", "needs", str(xml), "--output", str(output), *args])
    data = json.loads(output.read_text(encoding="utf-8")) if output.exists() else None
    return code, data


def _needs(data):
    version = data["current_version"]
    return data["versions"][version]["needs"]


class TestNoSphinxImport:
    """The converter has to be usable without the documentation toolchain."""

    def test_importing_the_cli_does_not_import_sphinx(self):
        script = (
            "import sys;"
            "import ub_test_reports.cli;"
            "leaked = sorted(m for m in sys.modules"
            " if m == 'sphinx' or m.startswith(('sphinx.', 'sphinx_needs')));"
            "print(','.join(leaked))"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            check=True,
        )

        assert result.stdout.strip() == ""


class TestEnvelope:
    def test_envelope_carries_project_and_current_version(self, tmp_path):
        _, data = _convert(tmp_path, "--project", "Score Docs-as-Code")

        assert data["project"] == "Score Docs-as-Code"
        assert data["current_version"] in data["versions"]

    def test_needs_amount_matches_the_number_of_cases(self, tmp_path):
        _, data = _convert(tmp_path)

        version = data["versions"][data["current_version"]]
        assert version["needs_amount"] == len(version["needs"]) == 5

    def test_every_written_field_is_declared(self, tmp_path):
        """The file says what its fields are, without a Sphinx build to ask."""
        _, data = _convert(tmp_path)

        version = data["versions"][data["current_version"]]
        declared = set(version["needs_schema"]["properties"])
        written = {key for need in version["needs"].values() for key in need}

        assert written - declared == set()

    def test_no_timestamp_is_written(self, tmp_path):
        """A wall clock would defeat action caching and evidence diffs."""
        _, data = _convert(tmp_path)

        assert "created" not in data
        assert "created" not in data["versions"][data["current_version"]]

    def test_output_is_byte_stable_across_runs(self, tmp_path):
        from ub_test_reports.cli import main

        first = tmp_path / "first.json"
        second = tmp_path / "second.json"
        for output in (first, second):
            assert (
                main(["build", "needs", str(GTEST_XML), "--output", str(output)]) == 0
            )

        assert first.read_bytes() == second.read_bytes()


class TestNeedContent:
    def test_ids_match_the_deterministic_scheme(self, tmp_path):
        from ub_test_reports.identity import deterministic_case_id

        _, data = _convert(tmp_path)

        expected = deterministic_case_id(
            classname="MathTest", name="Addition", file="src/math_test.cc"
        )
        assert expected in _needs(data)

    def test_source_location_is_emitted_verbatim(self, tmp_path):
        _, data = _convert(tmp_path)

        need = _needs(data)["testcase__MathTest__Addition_hcuyy"]
        assert need["case_file"] == "src/math_test.cc"
        assert need["case_line"] == "12"
        # `file` is the report path, as in a locally created test-case need.
        assert need["file"] == str(GTEST_XML)

    def test_type_and_title_match_the_directive_s(self, tmp_path):
        # The directive titles a case need with the case name; a needtable
        # title column must not tell an imported case from a built one.
        _, data = _convert(tmp_path)

        need = _needs(data)["testcase__MathTest__Addition_hcuyy"]
        assert need["type"] == "testcase"
        assert need["title"] == "Addition"

    def test_result_vocabulary_includes_disabled(self, tmp_path):
        _, data = _convert(tmp_path)

        need = _needs(data)["testcase__MathTest__DISABLED_Division_jnyzp"]
        assert need["result"] == "disabled"

    def test_content_keeps_every_failure_part(self, tmp_path):
        """R2: the debug output has to survive the conversion."""
        _, data = _convert(tmp_path)

        content = _needs(data)["testcase__MathTest__Subtraction_srmht"]["content"]
        assert "Expected equality of these values" in content
        assert "Actual: false" in content
        assert "overflow guard hit" in content

    def test_result_text_is_the_first_failure_message(self, tmp_path):
        _, data = _convert(tmp_path)

        need = _needs(data)["testcase__MathTest__Subtraction_srmht"]
        assert need["result_text"].startswith("src/math_test.cc:22")
        assert "\n" not in need["result_text"]

    def test_named_properties_become_fields(self, tmp_path, capsys):
        # Only properties the build would accept (extra_options, or here the
        # flag standing in for it) become fields; the rest is reported once.
        code, data = _convert(tmp_path, "--no-config", "--extra-option", "TestType")
        assert code == 0
        need = _needs(data)["testcase__MathTest__Addition_hcuyy"]
        assert need["TestType"] == "requirements-based"
        assert "PartiallyVerifies" not in need
        message = capsys.readouterr().err
        assert "properties not exported" in message
        assert "PartiallyVerifies" in message
        assert "extra_options" in message

    def test_unexported_properties_are_reported_once_for_all_names(
        self, tmp_path, capsys
    ):
        # One line naming every left-out property -- not one line per name,
        # and not one per case that carries it.
        code, _ = _convert(tmp_path, "--no-config")
        assert code == 0
        lines = [
            line
            for line in capsys.readouterr().err.splitlines()
            if "properties not exported" in line
        ]
        assert len(lines) == 1
        assert "PartiallyVerifies" in lines[0] and "TestType" in lines[0]

    def test_an_exported_property_is_present_on_every_case(self, tmp_path):
        # Null where the case has no such property, as the build leaves a
        # registered field a directive did not set -- so one schema can
        # require the field of imported and locally created needs alike.
        _, data = _convert(tmp_path, "--no-config", "--extra-option", "TestType")
        needs = _needs(data)
        assert needs["testcase__MathTest__Addition_hcuyy"]["TestType"] == (
            "requirements-based"
        )
        assert needs["testcase__MathTest__Subtraction_srmht"]["TestType"] is None
        assert all("TestType" in need for need in needs.values())

    def test_unnamed_properties_are_left_out_quietly_when_none_exist(
        self, tmp_path, capsys
    ):
        code, _ = _convert(tmp_path, "--no-config", xml=PYTEST_XML)
        assert code == 0
        assert "properties not exported" not in capsys.readouterr().err

    def test_tags_are_configurable(self, tmp_path):
        _, data = _convert(tmp_path, "--tags", "TEST")

        assert _needs(data)["testcase__MathTest__Addition_hcuyy"]["tags"] == ["TEST"]


class TestLinkProperties:
    def test_a_property_can_be_promoted_to_a_link_field(self, tmp_path):
        _, data = _convert(
            tmp_path, "--link-property", "PartiallyVerifies=partially_verifies"
        )

        need = _needs(data)["testcase__MathTest__Addition_hcuyy"]
        assert need["partially_verifies"] == ["REQ_1", "REQ_2"]
        assert "PartiallyVerifies" not in need

    def test_link_fields_are_always_present_even_when_empty(self, tmp_path):
        """A converter must emit its fields unconditionally, so schemas can require them."""
        _, data = _convert(
            tmp_path, "--link-property", "PartiallyVerifies=partially_verifies"
        )

        need = _needs(data)["testcase__MathTest__DISABLED_Division_jnyzp"]
        assert need["partially_verifies"] == []

    def test_malformed_link_property_is_rejected(self, tmp_path):
        from ub_test_reports.cli import main

        code = main(
            [
                "build",
                "needs",
                str(GTEST_XML),
                "--output",
                str(tmp_path / "out.json"),
                "--link-property",
                "NoEqualsSign",
            ]
        )

        assert code != 0


#: One case carrying BOTH properties, which share the value ``REQ_2``.
BOTH_PROPERTIES_XML = """<?xml version="1.0" encoding="UTF-8"?>
<testsuites tests="1" failures="0" errors="0" time="0.001" name="AllTests">
  <testsuite name="Both" tests="1" failures="0" errors="0" time="0.001">
    <testcase name="Merged" file="src/both_test.cc" line="3" status="run" result="completed" time="0.001" classname="Both">
      <properties>
        <property name="PartiallyVerifies" value="REQ_1, REQ_2"/>
        <property name="Requirement" value="REQ_2, REQ_3"/>
      </properties>
    </testcase>
  </testsuite>
</testsuites>
"""


class TestLinkPropertiesOntoOneField:
    """Several properties mapped onto ONE link field merge (#2058).

    Each mapped property used to ASSIGN the field, so the last one in the mapping won
    -- and a case without that last property was left with the empty list it was
    assigned, losing the links the first property gave it.
    """

    def test_the_issue_command_keeps_the_first_property_links(self, tmp_path):
        _, data = _convert(
            tmp_path,
            "--link-property",
            "PartiallyVerifies=links",
            "--link-property",
            "Requirement=links",
        )
        needs = _needs(data)
        assert needs["testcase__MathTest__Addition_hcuyy"]["links"] == [
            "REQ_1",
            "REQ_2",
        ]
        assert needs["testcase__ParamTest_0__Legacy_owuvz"]["links"] == ["REQ_9"]
        # a case carrying neither property still gets the field, empty
        assert needs["testcase__MathTest__DISABLED_Division_jnyzp"]["links"] == []

    @pytest.mark.parametrize(
        ("mapping", "expected"),
        [
            (["PartiallyVerifies", "Requirement"], ["REQ_1", "REQ_2", "REQ_3"]),
            # the mapping-order control: swapping the flags swaps the merged order
            (["Requirement", "PartiallyVerifies"], ["REQ_2", "REQ_3", "REQ_1"]),
        ],
        ids=["mapping-order", "swapped"],
    )
    def test_a_case_with_both_properties_gets_the_merged_list(
        self, tmp_path, mapping, expected
    ):
        """In mapping order, each value once, at its first appearance."""
        xml = tmp_path / "both.xml"
        xml.write_text(BOTH_PROPERTIES_XML, encoding="utf-8")
        flags = [
            arg for name in mapping for arg in ("--link-property", f"{name}=links")
        ]
        _, data = _convert(tmp_path, *flags, xml=xml)
        need = _only_need(data)
        assert need["links"] == expected

    def test_a_value_repeated_in_one_property_is_written_once(self, tmp_path):
        """The edge of the same rule: a field's list names each id once."""
        xml = tmp_path / "both.xml"
        xml.write_text(
            BOTH_PROPERTIES_XML.replace("REQ_2, REQ_3", "REQ_3, REQ_3"),
            encoding="utf-8",
        )
        _, data = _convert(tmp_path, "--link-property", "Requirement=links", xml=xml)
        need = _only_need(data)
        assert need["links"] == ["REQ_3"]

    def test_properties_onto_different_fields_stay_apart(self, tmp_path):
        xml = tmp_path / "both.xml"
        xml.write_text(BOTH_PROPERTIES_XML, encoding="utf-8")
        _, data = _convert(
            tmp_path,
            "--link-property",
            "PartiallyVerifies=links",
            "--link-property",
            "Requirement=verifies",
            xml=xml,
        )
        need = _only_need(data)
        assert need["links"] == ["REQ_1", "REQ_2"]
        assert need["verifies"] == ["REQ_2", "REQ_3"]


def _only_need(data):
    """The one need of a single-case report (its id's hash suffix is not this test's subject)."""
    (need,) = _needs(data).values()
    return need


class TestRemoteUrls:
    def test_external_url_and_remote_url_are_synthesized(self, tmp_path):
        _, data = _convert(
            tmp_path,
            "--remote-url",
            "https://github.com/org/repo",
            "--commit",
            "abc123",
        )

        need = _needs(data)["testcase__MathTest__Addition_hcuyy"]
        expected = "https://github.com/org/repo/blob/abc123/src/math_test.cc#L12"
        assert need["external_url"] == expected
        assert need["remote_url"] == expected

    def test_scp_style_remote_is_normalised(self, tmp_path):
        _, data = _convert(
            tmp_path,
            "--remote-url",
            "git@github.com:org/repo.git",
            "--commit",
            "abc123",
        )

        need = _needs(data)["testcase__MathTest__Addition_hcuyy"]
        assert need["remote_url"].startswith("https://github.com/org/repo/blob/abc123/")

    def test_url_pattern_is_configurable(self, tmp_path):
        _, data = _convert(
            tmp_path,
            "--remote-url",
            "https://gitlab.com/org/repo",
            "--commit",
            "abc123",
            "--url-pattern",
            "{base}/-/blob/{commit}/{file}#L{line}",
        )

        need = _needs(data)["testcase__MathTest__Addition_hcuyy"]
        assert need["remote_url"] == (
            "https://gitlab.com/org/repo/-/blob/abc123/src/math_test.cc#L12"
        )

    def test_credentials_in_the_remote_url_are_not_written(self, tmp_path):
        # GitLab's CI_REPOSITORY_URL embeds the job token; the base lands in
        # every need of a cached artifact and, imported, in published HTML.
        from ub_test_reports.cli import main

        output = tmp_path / "needs.json"
        code = main(
            [
                "build",
                "needs",
                str(GTEST_XML),
                "--output",
                str(output),
                "--no-config",
                "--remote-url",
                "https://gitlab-ci-token:glcbt-secret@gitlab.example.com/org/repo.git",
                "--commit",
                "abc123",
            ]
        )
        assert code == 0
        text = output.read_text(encoding="utf-8")
        assert "glcbt-secret" not in text and "gitlab-ci-token" not in text
        need = _needs(json.loads(text))["testcase__MathTest__Addition_hcuyy"]
        assert need["remote_url"] == (
            "https://gitlab.example.com/org/repo/blob/abc123/src/math_test.cc#L12"
        )

    def test_without_repo_metadata_the_url_fields_are_empty(self, tmp_path):
        """A hermetic sandbox has no git remote; that must not drop the need."""
        _, data = _convert(tmp_path)

        need = _needs(data)["testcase__MathTest__Addition_hcuyy"]
        assert need["remote_url"] == ""
        assert need["external_url"] == ""


class TestUrlPatternErrors:
    """A bad template is a configuration error at the start, not a traceback."""

    def test_an_unknown_placeholder_is_an_error(self, tmp_path, capsys):
        code, data = _convert(
            tmp_path,
            "--no-config",
            "--remote-url",
            "https://github.com/o/r",
            "--commit",
            "abc",
            "--url-pattern",
            "{base}/blob/{ref}/{file}#L{line}",
        )
        assert code == 2
        assert data is None
        message = capsys.readouterr().err
        assert "--url-pattern" in message
        assert "{ref}" in message

    def test_an_unbalanced_brace_is_an_error(self, tmp_path, capsys):
        code, _ = _convert(
            tmp_path, "--no-config", "--url-pattern", "{base/blob/{commit}/{file}"
        )
        assert code == 2
        assert "malformed" in capsys.readouterr().err

    def test_an_attribute_lookup_is_an_error_not_a_traceback(self, tmp_path, capsys):
        # str.format resolves {base.__class__}; only KeyError was caught.
        code, data = _convert(
            tmp_path,
            "--no-config",
            "--remote-url",
            "https://github.com/o/r",
            "--commit",
            "abc",
            "--url-pattern",
            "{base.__class__}/{file}",
        )
        assert code == 2
        assert data is None
        message = capsys.readouterr().err
        assert "unknown placeholder {base.__class__}" in message
        assert "Traceback" not in message

    def test_the_pattern_is_checked_before_any_report_is_read(self, tmp_path, capsys):
        # A missing report and a bad pattern: the pattern error wins, because
        # the template is checked before the first file is opened.
        code, data = _convert(
            tmp_path,
            "--no-config",
            "--url-pattern",
            "{base}/blob/{ref}/{file}",
            xml=tmp_path / "does-not-exist.xml",
        )
        assert code == 2
        assert data is None
        message = capsys.readouterr().err
        assert "{ref}" in message
        assert "no such file" not in message


class TestMultipleInputs:
    def test_several_reports_are_merged_into_one_file(self, tmp_path):
        from ub_test_reports.cli import main

        output = tmp_path / "needs.json"
        code = main(
            ["build", "needs", str(GTEST_XML), str(PYTEST_XML), "--output", str(output)]
        )
        data = json.loads(output.read_text(encoding="utf-8"))

        assert code == 0
        assert len(_needs(data)) > 5

    def test_the_same_report_given_twice_is_refused(self, tmp_path, capsys):
        # Silently collapsing the repeats would produce a valid file that has
        # lost half its evidence -- the worst outcome for a cached artifact.
        from ub_test_reports.cli import main

        output = tmp_path / "needs.json"
        code = main(
            [
                "build",
                "needs",
                str(GTEST_XML),
                str(GTEST_XML),
                "--no-config",
                "-o",
                str(output),
            ]
        )
        assert code == 2
        assert not output.exists()
        message = capsys.readouterr().err
        assert "more than once" in message
        assert "testcase__" in message

    def test_a_missing_input_file_exits_nonzero(self, tmp_path):
        from ub_test_reports.cli import main

        code = main(
            [
                "build",
                "needs",
                str(tmp_path / "nope.xml"),
                "--output",
                str(tmp_path / "out.json"),
            ]
        )

        assert code != 0


class TestDiagnostics:
    def test_absent_line_attributes_warn_about_junit_family(self, tmp_path, capsys):
        """pytest's default junit_family drops file/line; say so, don't guess."""
        from ub_test_reports.cli import main

        main(
            [
                "build",
                "needs",
                str(PYTEST_XML),
                "--output",
                str(tmp_path / "out.json"),
            ]
        )

        assert "junit_family" in capsys.readouterr().err

    def test_nested_suites_get_the_hint_too(self, tmp_path, capsys):
        # The parser files the cases of a nested report under testsuite_nested;
        # a hint that only looked at the top level went quiet on exactly the
        # Ant/Maven-shaped reports that most often lack source locations.
        code, data = _convert(
            tmp_path, "--no-config", xml=UTILS / "pytest_nested_example.xml"
        )
        assert code == 0
        assert all(need["case_line"] == "" for need in _needs(data).values())
        assert "junit_family" in capsys.readouterr().err

    def test_reports_with_line_attributes_do_not_warn(self, tmp_path, capsys):
        from ub_test_reports.cli import main

        main(["build", "needs", str(GTEST_XML), "--output", str(tmp_path / "out.json")])

        assert "junit_family" not in capsys.readouterr().err

    def test_a_report_without_test_cases_warns(self, tmp_path, capsys):
        # A pom.xml parses as one empty suite: a valid, empty needs.json with
        # exit 0 is the one outcome a cached build action must never get
        # silently.
        pom = tmp_path / "pom.xml"
        pom.write_text(
            "<project><modelVersion>4.0.0</modelVersion></project>\n", encoding="utf-8"
        )
        code, data = _convert(tmp_path, "--no-config", xml=pom)
        assert code == 0
        assert data["versions"][data["current_version"]]["needs_amount"] == 0
        message = capsys.readouterr().err
        assert "pom.xml" in message and "no test cases" in message

    def test_a_report_with_test_cases_does_not_get_the_empty_warning(
        self, tmp_path, capsys
    ):
        code, _ = _convert(tmp_path, "--no-config")
        assert code == 0
        assert "no test cases" not in capsys.readouterr().err


class TestUnreadableReports:
    """A report the reader refuses is one ``error:`` line naming it, exit 1 (#2052)."""

    def test_malformed_xml_names_the_report_and_the_position(self, tmp_path, capsys):
        # Master printed lxml's sentence with lxml's own `(file, line 1)` suffix; the
        # reader's typed error now leads with the path and the position, and the
        # converter does not prefix the path a second time.
        bad = tmp_path / "bad.xml"
        bad.write_bytes(b"<testsuite><testcase></testsuite>")
        code, data = _convert(tmp_path, "--no-config", xml=bad)
        assert code == 1
        assert data is None
        err = capsys.readouterr().err
        assert (
            f"error: {bad} (line 1, column 34): Opening and ending tag mismatch" in err
        )
        assert f"{bad}: {bad}" not in err

    @pytest.mark.parametrize("report", [b"<testsuites/>", b"<testsuites></testsuites>"])
    def test_an_empty_testsuites_is_an_empty_report(self, tmp_path, capsys, report):
        # Master: exit 1 with `error: …: no such child: testsuite`. An empty report is
        # converted like any report without cases: written, empty, and warned about.
        empty = tmp_path / "empty.xml"
        empty.write_bytes(report)
        code, data = _convert(tmp_path, "--no-config", xml=empty)
        assert code == 0
        assert data["versions"][data["current_version"]]["needs_amount"] == 0
        message = capsys.readouterr().err
        assert "no such child" not in message
        assert f"warning: {empty}: no test cases found" in message


def test_the_cli_is_runnable_as_a_module():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ub_test_reports.cli",
            "build",
            "needs",
            "--help",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--output" in result.stdout


def test_console_script_is_installed():
    """The name that goes into a BUILD file has to be a real entry point."""
    script = Path(sys.executable).parent / "test-reports"
    if not script.exists():
        pytest.skip("package not installed into this environment")

    result = subprocess.run(
        [str(script), "build", "needs", "--help"], capture_output=True, text=True
    )

    assert result.returncode == 0
    assert "--output" in result.stdout


@pytest.mark.parametrize("flag", ["--remote-url", "--commit"])
def test_url_synthesis_needs_both_parts(tmp_path, flag):
    """Half the metadata cannot produce a URL; fail loudly instead of guessing."""
    from ub_test_reports.cli import main

    code = main(
        [
            "build",
            "needs",
            str(GTEST_XML),
            "--output",
            str(tmp_path / "out.json"),
            flag,
            "value",
        ]
    )

    assert code != 0


class TestResultVocabulary:
    """The export uses the parser's vocabulary, which is the build's.

    ``failed`` is a documented need field value and a CSS class
    (``tr_failed``), and the shipped report template filters on it. A project
    that mixes imported and locally created test-case needs filters both with
    one expression only if the two writers spell the result alike.
    """

    def test_failure_is_exported_as_the_build_spells_it(self, tmp_path):
        _, data = _convert(tmp_path)

        assert (
            _needs(data)["testcase__MathTest__Subtraction_srmht"]["result"] == "failed"
        )

    @pytest.mark.parametrize(
        ("need_id", "expected"),
        [
            ("testcase__MathTest__Addition_hcuyy", "passed"),
            ("testcase__MathTest__DISABLED_Division_jnyzp", "disabled"),
            ("testcase__ParamTest_0__Legacy_owuvz", "skipped"),
        ],
    )
    def test_other_results_are_unchanged(self, tmp_path, need_id, expected):
        _, data = _convert(tmp_path)

        assert _needs(data)[need_id]["result"] == expected


class TestContentIsNotDuplicated:
    """googletest repeats the failure text in the message attribute.

    Emitting both verbatim shows the same stack trace twice in the rendered
    need; the message block is only worth its space when it says something the
    body does not.
    """

    def test_a_message_contained_in_the_body_is_not_repeated(self, tmp_path):
        _, data = _convert(tmp_path)

        content = _needs(data)["testcase__MathTest__Subtraction_srmht"]["content"]
        assert content.count("Expected equality of these values") == 1
        assert "message" not in content

    def test_a_message_absent_from_the_body_is_kept(self, tmp_path):
        _, data = _convert(tmp_path)

        content = _needs(data)["testcase__ParamTest_0__Legacy_owuvz"]["content"]
        assert "Skipped via GTEST_SKIP" in content
        assert "not applicable on this platform" in content


def test_direct_cases_of_a_suite_with_nested_suites_are_exported(tmp_path):
    """#2050: the cases of a suite that ALSO holds nested suites are exported, with that
    suite's name -- the parser used to drop them, so the converter never saw them. The
    nested suite's case and the second top-level suite's case are exported as before."""
    code, data = _convert(tmp_path, "--no-config", xml=UTILS / "nested_mixed.xml")
    assert code == 0

    by_case = {need["case"]: need for need in _needs(data).values()}
    assert sorted(by_case) == [
        "test_first",
        "test_nested",
        "test_second",
        "test_top_level",
    ]
    assert by_case["test_first"]["suite"] == "outer"
    assert by_case["test_second"]["suite"] == "outer"
    assert by_case["test_second"]["result"] == "failed"
    assert by_case["test_nested"]["suite"] == "inner"
    assert by_case["test_top_level"]["suite"] == "inner"
