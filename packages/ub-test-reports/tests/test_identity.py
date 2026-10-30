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

from ub_test_reports.identity import (
    PLACEHOLDER_FILE,
    case_display_name,
    case_name_and_parameter,
    deterministic_case_id,
    short_hash,
    split_case_name,
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


class TestSplitCaseName:
    """``name[param]`` as pytest spells it, split for both writers alike.

    The one definition the directives and the converter share; the shapes
    pinned here are the ones a report can carry, so a change to the pattern
    shows up as a failing test rather than as two writers disagreeing.
    """

    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            # No parameter: None, so the field is null, not "" (#2372).
            ("test_x", ("test_x", None)),
            ("test_x[a-b]", ("test_x", "a-b")),
            ("tests.test_cli.test_help[1-2]", ("tests.test_cli.test_help", "1-2")),
            # An empty parameter list is a parameter of "".
            ("test_x[]", ("test_x", "")),
            # The parameter is greedy: brackets inside it survive.
            ("test_x[a[0]-b]", ("test_x", "a[0]-b")),
            # googletest's parameterised spelling carries no brackets at all.
            ("Works/0", ("Works/0", None)),
            # Not the pytest shape: the name is kept whole, never cut at a
            # bracket -- an unclosed one, text after the closing one, or a
            # name that starts with one.
            ("test_x[abc", ("test_x[abc", None)),
            ("test_x[a]b", ("test_x[a]b", None)),
            ("[only]", ("[only]", None)),
        ],
    )
    def test_splits_pytest_s_shape_and_only_that(self, name, expected):
        assert split_case_name(name) == expected


class TestCaseNameAndParameter:
    """A case's ``case_name`` and ``case_parameter``, from its name and, where the
    name carries no ``[…]``, from Google Test's ``value_param`` / ``type_param``
    (#2390).

    The one rule the converter, the ``test-case`` directive and the report hop's
    ``parameter`` extra share. The cases are the shapes gtest writes (measured on
    googletest 1.17.0) and the parser's ``""`` for an absent attribute.
    """

    @pytest.mark.parametrize(
        ("case", "expected"),
        [
            # TEST_P: the value, verbatim; the name keeps gtest's /N.
            (
                {"name": "Value/0", "value_param": "1", "type_param": ""},
                ("Value/0", "1"),
            ),
            (
                {"name": "Pair/0", "value_param": "(1, 2)", "type_param": ""},
                ("Pair/0", "(1, 2)"),
            ),
            # Quotes and angle brackets are kept as gtest prints them.
            (
                {"name": "Str/0", "value_param": '"a \\"b\\" <c>"', "type_param": ""},
                ("Str/0", '"a \\"b\\" <c>"'),
            ),
            # An empty std::string is printed as its two quote characters.
            (
                {"name": "Str/1", "value_param": '""', "type_param": ""},
                ("Str/1", '""'),
            ),
            # TYPED_TEST / TYPED_TEST_P: the type, verbatim.
            ({"name": "T1", "value_param": "", "type_param": "int"}, ("T1", "int")),
            (
                {"name": "Each", "type_param": "std::basic_string<char>"},
                ("Each", "std::basic_string<char>"),
            ),
            # Both (testing::RegisterTest): the type, then the value, gtest's order.
            (
                {"name": "Works/0", "value_param": "42", "type_param": "int"},
                ("Works/0", "int, 42"),
            ),
            # A pytest bracket wins over the attributes, an empty one too.
            (
                {"name": "test_x[3]", "value_param": "1", "type_param": "int"},
                ("test_x", "3"),
            ),
            (
                {"name": "test_x[]", "value_param": "1", "type_param": ""},
                ("test_x", ""),
            ),
            # Empty or missing attributes: no parameter, a null field.
            (
                {"name": "Addition", "value_param": "", "type_param": ""},
                ("Addition", None),
            ),
            ({"name": "test_x"}, ("test_x", None)),
            ({"name": "test_x", "value_param": None}, ("test_x", None)),
            # The parsers' "unknown" placeholder is absent too: a tr_json_mapping
            # that defaults the two keys to it, as the docs' example does every key.
            (
                {"name": "test_x", "value_param": "unknown", "type_param": "unknown"},
                ("test_x", None),
            ),
            (
                {"name": "T1", "value_param": "unknown", "type_param": "int"},
                ("T1", "int"),
            ),
        ],
    )
    def test_the_name_s_bracket_then_the_value_then_the_type(self, case, expected):
        assert case_name_and_parameter(case) == expected

    def test_a_name_the_caller_spells_otherwise_is_the_one_split(self):
        """The converter writes ``""`` for the parser's ``"unknown"`` name; the
        report's parameter still comes from the case."""
        case = {"name": "unknown", "value_param": "1", "type_param": ""}
        assert case_name_and_parameter(case, name="") == ("", "1")
        assert case_name_and_parameter(case, name="t[2]") == ("t", "2")


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
