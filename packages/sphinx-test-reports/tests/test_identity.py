"""Tests for deterministic test-case need IDs (TR-G).

The default auto-ID hashes *(type, title, content)*, and the content of a test
case carries its failure text -- so a need's ID changes when a test starts
failing differently. That breaks anything holding a reference to it: build
caches, pre-authored links from a test specification, and diffs of an exported
needs.json.

The opt-in scheme here is byte-compatible with the ID scheme S-CORE's
``score_source_code_linker`` produces (``testcase__{name}_{shorthash}`` with
five lowercase base32 letters of ``sha256(file + name)``), so a project can
migrate to sphinx-test-reports without any of its need IDs moving.

The expected values below were computed with S-CORE's own implementation
(``score_source_code_linker/xml_parser.py::short_hash``).
"""

import pytest

from sphinxcontrib.test_reports.identity import (
    PLACEHOLDER_FILE,
    case_display_name,
    deterministic_case_id,
    short_hash,
)


class TestShortHash:
    def test_matches_the_score_implementation(self):
        assert short_hash("src/math_test.ccMathTest__Addition") == "hcuyy"

    def test_is_lowercase_letters_only(self):
        digest = short_hash("anything at all")

        assert digest.isalpha()
        assert digest.islower()

    def test_length_is_configurable(self):
        assert len(short_hash("value", length=8)) == 8

    def test_differs_for_different_input(self):
        assert short_hash("a") != short_hash("b")


class TestCaseDisplayName:
    def test_joins_the_last_classname_segment_with_the_case_name(self):
        assert case_display_name("tests.test_cli", "test_help") == "test_cli__test_help"

    def test_without_a_classname_it_is_the_case_name(self):
        assert case_display_name("", "Standalone") == "Standalone"

    def test_unknown_classname_is_treated_as_absent(self):
        """The parser reports "unknown" when the attribute is missing."""
        assert case_display_name("unknown", "Standalone") == "Standalone"


class TestDeterministicCaseId:
    def test_is_score_compatible(self):
        assert (
            deterministic_case_id(
                classname="MathTest", name="Addition", file="src/math_test.cc"
            )
            == "testcase__MathTest__Addition_hcuyy"
        )

    def test_absent_file_uses_the_placeholder(self):
        assert (
            deterministic_case_id(classname="", name="Standalone", file="")
            == "testcase__Standalone_qwnmf"
        )
        assert PLACEHOLDER_FILE == "<placeholder_file>"

    def test_result_details_do_not_take_part_in_the_identity(self):
        """The whole point: a differently failing test keeps its ID."""
        first = deterministic_case_id(
            classname="MathTest", name="Addition", file="src/math_test.cc"
        )
        second = deterministic_case_id(
            classname="MathTest", name="Addition", file="src/math_test.cc"
        )

        assert first == second

    def test_moving_the_source_file_changes_the_id(self):
        moved = deterministic_case_id(
            classname="MathTest", name="Addition", file="src/moved_test.cc"
        )

        assert moved != "testcase__MathTest__Addition_hcuyy"

    def test_prefix_is_configurable(self):
        assert deterministic_case_id(
            classname="MathTest", name="Addition", file="src/math_test.cc", prefix="tc"
        ).startswith("tc__MathTest__Addition_")

    @pytest.mark.parametrize(
        ("classname", "name", "expected_id"),
        [
            # googletest parameterised suites put "/" in both names; a need ID
            # must stay within [A-Za-z0-9_] to be a legal ID and HTML anchor.
            ("ParamTest/0", "Works/0", "testcase__ParamTest_0__Works_0_ugfea"),
            ("ParamTest/0", "Legacy", "testcase__ParamTest_0__Legacy_owuvz"),
        ],
    )
    def test_names_are_sanitised_but_the_hash_uses_the_raw_name(
        self, classname, name, expected_id
    ):
        assert (
            deterministic_case_id(
                classname=classname, name=name, file="src/param_test.cc"
            )
            == expected_id
        )
