"""Tests for the Sphinx-free ``test-reports convert`` CLI (TR-A).

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

UTILS = Path(__file__).parent / "doc_test" / "utils"
GTEST_XML = UTILS / "gtest_data.xml"
PYTEST_XML = UTILS / "pytest_data.xml"


def _convert(tmp_path, *args, xml=GTEST_XML):
    """Run the converter and return (exit_code, parsed output or None)."""
    from sphinxcontrib.test_reports.cli import main

    output = tmp_path / "needs.json"
    code = main(["convert", str(xml), "--output", str(output), *args])
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
            "import sphinxcontrib.test_reports.cli;"
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
    def test_output_passes_the_sphinx_needs_schema(self, tmp_path):
        """The output must validate against sphinx-needs' own needs.json schema."""
        needsfile = pytest.importorskip("sphinx_needs.needsfile")
        if not hasattr(needsfile, "check_needs_data"):
            # Older sphinx-needs releases do not ship the schema check; the
            # envelope contract itself is version-independent, so skip rather
            # than pin the whole suite to the newest sphinx-needs.
            pytest.skip("sphinx-needs has no check_needs_data")

        code, data = _convert(tmp_path)

        assert code == 0
        assert needsfile.check_needs_data(data).schema == []

    def test_envelope_carries_project_and_current_version(self, tmp_path):
        _, data = _convert(tmp_path, "--project", "Score Docs-as-Code")

        assert data["project"] == "Score Docs-as-Code"
        assert data["current_version"] in data["versions"]

    def test_needs_amount_matches_the_number_of_cases(self, tmp_path):
        _, data = _convert(tmp_path)

        version = data["versions"][data["current_version"]]
        assert version["needs_amount"] == len(version["needs"]) == 5

    def test_no_timestamp_is_written(self, tmp_path):
        """A wall clock would defeat action caching and evidence diffs."""
        _, data = _convert(tmp_path)

        assert "created" not in data
        assert "created" not in data["versions"][data["current_version"]]

    def test_output_is_byte_stable_across_runs(self, tmp_path):
        from sphinxcontrib.test_reports.cli import main

        first = tmp_path / "first.json"
        second = tmp_path / "second.json"
        for output in (first, second):
            assert main(["convert", str(GTEST_XML), "--output", str(output)]) == 0

        assert first.read_bytes() == second.read_bytes()


class TestNeedContent:
    def test_ids_match_the_deterministic_scheme(self, tmp_path):
        from sphinxcontrib.test_reports.identity import deterministic_case_id

        _, data = _convert(tmp_path)

        expected = deterministic_case_id(
            classname="MathTest", name="Addition", file="src/math_test.cc"
        )
        assert expected in _needs(data)

    def test_source_location_is_emitted_verbatim(self, tmp_path):
        _, data = _convert(tmp_path)

        need = _needs(data)["testcase__MathTest__Addition_hcuyy"]
        assert need["file"] == "src/math_test.cc"
        assert need["line"] == "12"

    def test_type_and_title_are_score_shaped(self, tmp_path):
        _, data = _convert(tmp_path)

        need = _needs(data)["testcase__MathTest__Addition_hcuyy"]
        assert need["type"] == "testcase"
        assert need["title"] == "MathTest__Addition"

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

    def test_properties_become_fields(self, tmp_path):
        _, data = _convert(tmp_path)

        need = _needs(data)["testcase__MathTest__Addition_hcuyy"]
        assert need["TestType"] == "requirements-based"

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
        from sphinxcontrib.test_reports.cli import main

        code = main(
            [
                "convert",
                str(GTEST_XML),
                "--output",
                str(tmp_path / "out.json"),
                "--link-property",
                "NoEqualsSign",
            ]
        )

        assert code != 0


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

    def test_without_repo_metadata_the_url_fields_are_empty(self, tmp_path):
        """A hermetic sandbox has no git remote; that must not drop the need."""
        _, data = _convert(tmp_path)

        need = _needs(data)["testcase__MathTest__Addition_hcuyy"]
        assert need["remote_url"] == ""
        assert need["external_url"] == ""


class TestMultipleInputs:
    def test_several_reports_are_merged_into_one_file(self, tmp_path):
        from sphinxcontrib.test_reports.cli import main

        output = tmp_path / "needs.json"
        code = main(
            ["convert", str(GTEST_XML), str(PYTEST_XML), "--output", str(output)]
        )
        data = json.loads(output.read_text(encoding="utf-8"))

        assert code == 0
        assert len(_needs(data)) > 5

    def test_a_missing_input_file_exits_nonzero(self, tmp_path):
        from sphinxcontrib.test_reports.cli import main

        code = main(
            [
                "convert",
                str(tmp_path / "nope.xml"),
                "--output",
                str(tmp_path / "out.json"),
            ]
        )

        assert code != 0


class TestDiagnostics:
    def test_absent_line_attributes_warn_about_junit_family(self, tmp_path, capsys):
        """pytest's default junit_family drops file/line; say so, don't guess."""
        from sphinxcontrib.test_reports.cli import main

        main(
            [
                "convert",
                str(PYTEST_XML),
                "--output",
                str(tmp_path / "out.json"),
            ]
        )

        assert "junit_family" in capsys.readouterr().err

    def test_reports_with_line_attributes_do_not_warn(self, tmp_path, capsys):
        from sphinxcontrib.test_reports.cli import main

        main(["convert", str(GTEST_XML), "--output", str(tmp_path / "out.json")])

        assert "junit_family" not in capsys.readouterr().err


def test_the_cli_is_runnable_as_a_module():
    result = subprocess.run(
        [sys.executable, "-m", "sphinxcontrib.test_reports.cli", "convert", "--help"],
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
        [str(script), "convert", "--help"], capture_output=True, text=True
    )

    assert result.returncode == 0
    assert "--output" in result.stdout


@pytest.mark.parametrize("flag", ["--remote-url", "--commit"])
def test_url_synthesis_needs_both_parts(tmp_path, flag):
    """Half the metadata cannot produce a URL; fail loudly instead of guessing."""
    from sphinxcontrib.test_reports.cli import main

    code = main(
        [
            "convert",
            str(GTEST_XML),
            "--output",
            str(tmp_path / "out.json"),
            flag,
            "value",
        ]
    )

    assert code != 0


class TestResultVocabulary:
    """The export uses the migration-target vocabulary, not the parser's.

    The parser reports ``failure`` and must keep doing so -- it is a documented
    need field value and a CSS class (``tr_failure``). The exported needs.json
    is a new surface with no such obligation, and its consumers' metamodels
    (S-CORE's included) spell it ``failed``.
    """

    def test_failure_is_exported_as_failed(self, tmp_path):
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
