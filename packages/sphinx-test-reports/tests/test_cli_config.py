"""``build needs`` reads ``[test_reports.build.needs]`` from ``ubproject.toml``.

Precedence is flag > TOML table > built-in default, and the file is found the
way the Sphinx build finds it -- searched for upwards to the project root -- so
the two consumers of one project never read different descriptions of it.
"""

import json
import os
from pathlib import Path

import pytest

from sphinxcontrib.test_reports.cli import _DEFAULTS, main
from sphinxcontrib.test_reports.projectconfig import (
    CONVERSION_KEYS,
    DEFAULT_TOML_FILENAME,
)

UTILS = Path(__file__).parent / "doc_test" / "utils"
PYTEST_XML = str(UTILS / "pytest_data.xml")
GTEST_XML = str(UTILS / "gtest_data.xml")  # carries <property> elements


def _write(directory, toml_source, name=DEFAULT_TOML_FILENAME):
    config = directory / name
    config.write_text(toml_source, encoding="utf-8")
    return config


def run_convert(
    tmp_path, arguments, toml=None, config_name=None, subdir=None, xml=PYTEST_XML
):
    """Run ``build needs`` from *tmp_path* (or a subdirectory) and parse the output.

    A project-root marker bounds the upward search, so the outcome never depends
    on what happens to sit above the temporary directory.
    """
    (tmp_path / ".git").mkdir(exist_ok=True)  # bounds the upward search
    if toml is not None:
        _write(tmp_path, toml, name=config_name or DEFAULT_TOML_FILENAME)
    workdir = tmp_path
    if subdir is not None:
        workdir = tmp_path / subdir
        workdir.mkdir(parents=True, exist_ok=True)
    previous = os.getcwd()
    os.chdir(workdir)
    try:
        code = main(["build", "needs", xml, "-o", "needs.json", *arguments])
    finally:
        os.chdir(previous)
    payload = {}
    output = workdir / "needs.json"
    if output.is_file():
        payload = json.loads(output.read_text(encoding="utf-8"))
    return code, payload


def _first_need(payload):
    return next(iter(payload["versions"][payload["current_version"]]["needs"].values()))


class TestPrecedence:
    """Flag > TOML > built-in default."""

    def test_table_provides_the_conversion_settings(self, tmp_path):
        code, payload = run_convert(
            tmp_path,
            [],
            toml="""
            [test_reports.build.needs]
            project = "My Project"
            version = "2.0"
            tags = ["ci", "unit"]
            link_properties = { PartiallyVerifies = "partially_verifies" }
            """,
        )
        assert code == 0
        assert payload["project"] == "My Project"
        assert payload["current_version"] == "2.0"
        need = _first_need(payload)
        assert need["tags"] == ["ci", "unit"]
        assert need["partially_verifies"] == []

    def test_flag_overrides_the_table(self, tmp_path):
        code, payload = run_convert(
            tmp_path,
            ["--version", "9.9"],
            toml="[test_reports.build.needs]\nversion = '2.0'\n",
        )
        assert code == 0
        assert payload["current_version"] == "9.9"

    def test_table_overrides_the_builtin_default(self, tmp_path):
        # A need type other than the default has to be the build's too -- so
        # the file also names it as the case type.
        code, payload = run_convert(
            tmp_path,
            [],
            toml="[test_reports.build.needs]\nneed_type = 'check'\n"
            """
            [test_reports.case]
            directive = "test-case"
            type = "check"
            name = "Check"
            prefix = "CH_"
            color = "#999999"
            style = "rectangle"
            """,
        )
        assert code == 0
        assert _first_need(payload)["type"] == "check"

    def test_no_file_uses_the_defaults(self, tmp_path):
        code, payload = run_convert(tmp_path, [])
        assert code == 0
        assert payload["project"] == ""
        assert payload["current_version"] == "1.0"

    def test_an_explicit_empty_flag_beats_the_table(self, tmp_path):
        # "" is a value, not "not given": the flag clears the file's tags.
        code, payload = run_convert(
            tmp_path, ["--tags", ""], toml="[test_reports.build.needs]\ntags = ['x']\n"
        )
        assert code == 0
        assert _first_need(payload)["tags"] == []

    def test_link_property_flag_replaces_the_table(self, tmp_path):
        code, payload = run_convert(
            tmp_path,
            ["--link-property", "Verifies=verifies"],
            toml='[test_reports.build.needs]\nlink_properties = { Other = "other_field" }\n',
        )
        assert code == 0
        need = _first_need(payload)
        assert "verifies" in need
        assert "other_field" not in need

    def test_field_names_from_the_section_shape_the_output(self, tmp_path):
        # The same file configures the build. Its field-name keys are read on
        # purpose -- the output has to have the shape of the build's needs --
        # while its other bridge keys are none of the converter's business.
        code, payload = run_convert(
            tmp_path,
            [],
            toml="""
            [test_reports]
            file_option = "report_file"
            source_file_option = "file"
            source_line_option = "line"
            extra_options = ["more_info"]

            [test_reports.build.needs]
            project = "p"
            """,
        )
        assert code == 0
        assert payload["project"] == "p"
        need = _first_need(payload)
        assert need["report_file"].endswith("pytest_data.xml")
        assert "file" in need and "line" in need
        assert "case_file" not in need
        # Listed, so the field is there -- null, as no case carries it.
        assert need["more_info"] is None


class TestFileLookup:
    """Where the file comes from, and what happens when it does not."""

    def test_walks_up_to_the_project_root(self, tmp_path):
        # The canonical layout: ubproject.toml at the root, the converter run
        # from a build directory below it.
        code, payload = run_convert(
            tmp_path,
            [],
            toml='[test_reports.build.needs]\nproject = "from the root"\n',
            subdir="build/testlogs",
        )
        assert code == 0
        assert payload["project"] == "from the root"

    def test_explicit_config_by_path(self, tmp_path):
        code, payload = run_convert(
            tmp_path,
            ["--config", "staging.toml"],
            toml='[test_reports.build.needs]\nproject = "staged"\n',
            config_name="staging.toml",
        )
        assert code == 0
        assert payload["project"] == "staged"

    def test_explicit_missing_config_is_an_error(self, tmp_path, capsys):
        code, _ = run_convert(tmp_path, ["--config", "other.toml"])
        assert code == 2
        assert "other.toml" in capsys.readouterr().err

    def test_no_config_ignores_the_file(self, tmp_path):
        code, payload = run_convert(
            tmp_path,
            ["--no-config"],
            toml='[test_reports.build.needs]\nproject = "from toml"\n',
        )
        assert code == 0
        assert payload["project"] == ""

    def test_config_and_no_config_are_mutually_exclusive(self):
        with pytest.raises(SystemExit):
            main(
                [
                    "build",
                    "needs",
                    PYTEST_XML,
                    "-o",
                    "n.json",
                    "--no-config",
                    "--config",
                    "x",
                ]
            )


class TestVerbosity:
    """A config-less run is quiet, a discovered file is named, ``-v`` says more.

    The file the search adopts may sit directories above the invocation and it
    shapes the bytes written, so it is named on every run, as the build logs it
    at INFO. ``-v`` adds where a fruitless search ended, so a misplaced file can
    be placed right, and names a file given with ``--config``.
    """

    def test_a_discovered_file_is_named_without_verbose(self, tmp_path, capsys):
        code, _ = run_convert(
            tmp_path,
            [],
            toml='[test_reports.build.needs]\nproject = "p"\n',
            subdir="build/testlogs",
        )
        assert code == 0
        err = capsys.readouterr().err
        assert "reading [test_reports] from" in err
        assert str(tmp_path / DEFAULT_TOML_FILENAME) in err

    def test_an_explicit_config_file_is_named_only_with_verbose(self, tmp_path, capsys):
        # The user typed the path; repeating it is noise unless asked for.
        toml = '[test_reports.build.needs]\nproject = "p"\n'
        code, _ = run_convert(
            tmp_path,
            ["--config", "staging.toml"],
            toml=toml,
            config_name="staging.toml",
        )
        assert code == 0
        assert "reading [test_reports]" not in capsys.readouterr().err
        code, _ = run_convert(
            tmp_path,
            ["--config", "staging.toml", "-v"],
            toml=toml,
            config_name="staging.toml",
        )
        assert code == 0
        assert "reading [test_reports] from staging.toml" in capsys.readouterr().err

    def test_a_configless_run_is_quiet_by_default(self, tmp_path, capsys):
        # Nothing about the search on stderr -- other diagnostics (here the
        # fixture's missing source lines) are not what is under test.
        code, _ = run_convert(tmp_path, [])
        assert code == 0
        err = capsys.readouterr().err
        assert DEFAULT_TOML_FILENAME not in err
        assert "repository root" not in err

    def test_verbose_reports_where_the_search_ended(self, tmp_path, capsys):
        # The same message the loader gives the Sphinx bridge at -v: the
        # directory whose marker ended the search, so a misplaced file can be
        # placed right.
        code, _ = run_convert(tmp_path, ["-v"], subdir="build/testlogs")
        assert code == 0
        err = capsys.readouterr().err
        assert f"no {DEFAULT_TOML_FILENAME} in" in err
        assert "repository root" in err and str(tmp_path) in err

    def test_verbose_names_the_file_used(self, tmp_path, capsys):
        code, _ = run_convert(
            tmp_path, ["--verbose"], toml='[test_reports.build.needs]\nproject = "p"\n'
        )
        assert code == 0
        err = capsys.readouterr().err
        assert "reading [test_reports] from" in err
        assert DEFAULT_TOML_FILENAME in err


class TestDiagnostics:
    """Errors name what the user wrote, and warnings do not stop the run."""

    def test_wrong_type_in_the_table_is_an_error(self, tmp_path, capsys):
        code, _ = run_convert(
            tmp_path, [], toml="[test_reports.build.needs]\ntags = 'ci'\n"
        )
        assert code == 2
        assert "build.needs.tags" in capsys.readouterr().err

    def test_wrong_type_elsewhere_in_the_section_is_an_error_too(
        self, tmp_path, capsys
    ):
        # One file, one verdict: the converter rejects what the build rejects,
        # even for a key it does not itself use.
        code, _ = run_convert(
            tmp_path, [], toml="[test_reports]\nsuite_id_length = 'four'\n"
        )
        assert code == 2
        assert "suite_id_length" in capsys.readouterr().err

    def test_unknown_key_in_the_table_warns_but_converts(self, tmp_path, capsys):
        code, payload = run_convert(
            tmp_path,
            [],
            toml='[test_reports.build.needs]\nproject = "p"\nno_such_key = 1\n',
        )
        assert code == 0
        assert payload["project"] == "p"
        err = capsys.readouterr().err
        assert "no_such_key" in err
        assert "[test_reports.build.needs]" in err

    def test_half_remote_pair_from_the_table_names_the_table(self, tmp_path, capsys):
        # The value came from the file, so naming only the flags would point at
        # options that appear nowhere in the invocation.
        code, _ = run_convert(
            tmp_path,
            [],
            toml='[test_reports.build.needs]\nremote_url = "https://gh.com/o/r"\n',
        )
        assert code == 2
        message = capsys.readouterr().err
        assert "remote_url and --commit" in message
        assert "[test_reports.build.needs]" in message
        assert DEFAULT_TOML_FILENAME in message

    def test_half_remote_pair_from_flags_names_the_flags(self, tmp_path, capsys):
        code, _ = run_convert(tmp_path, ["--commit", "abc"])
        assert code == 2
        message = capsys.readouterr().err
        assert "--remote-url and --commit" in message
        assert "[test_reports.build.needs]" not in message

    def test_need_type_disagreeing_with_the_case_type_is_an_error(
        self, tmp_path, capsys
    ):
        # The build takes its need type from case.type; a needs.json written
        # with another type would neither register nor cross-link there.
        code, _ = run_convert(
            tmp_path,
            [],
            toml="""
            [test_reports.build.needs]
            need_type = "testcase"

            [test_reports.case]
            directive = "test-case"
            type = "check"
            name = "Check"
            prefix = "CH_"
            color = "#999999"
            style = "rectangle"
            """,
        )
        assert code == 2
        assert "need_type" in capsys.readouterr().err

    def test_malformed_link_property_value_is_an_error(self, tmp_path, capsys):
        code, _ = run_convert(
            tmp_path,
            [],
            toml='[test_reports.build.needs]\nlink_properties = { Verifies = ["v"] }\n',
        )
        assert code == 2
        assert "link_properties" in capsys.readouterr().err

    def test_need_type_flag_disagreeing_with_the_case_type_is_an_error(
        self, tmp_path, capsys
    ):
        # The loader only sees the file. A flag is not in the file, so the
        # merged value has to be checked again, or the flag bypasses the rule.
        code, _ = run_convert(
            tmp_path,
            ["--need-type", "testcase"],
            toml="""
            [test_reports.case]
            directive = "test-case"
            type = "check"
            name = "Check"
            prefix = "CH_"
            color = "#999999"
            style = "rectangle"
            """,
        )
        assert code == 2
        message = capsys.readouterr().err
        assert "--need-type is 'testcase'" in message
        assert "'check'" in message

    def test_the_default_need_type_disagreeing_with_the_case_type_is_an_error(
        self, tmp_path, capsys
    ):
        code, _ = run_convert(
            tmp_path,
            [],
            toml="""
            [test_reports.case]
            directive = "test-case"
            type = "check"
            name = "Check"
            prefix = "CH_"
            color = "#999999"
            style = "rectangle"
            """,
        )
        assert code == 2
        assert "the default need_type is 'testcase'" in capsys.readouterr().err

    def test_need_type_flag_without_a_case_entry_is_checked_against_the_default(
        self, tmp_path, capsys
    ):
        # A side that is not set is compared at its default, as in the loader:
        # a file that leaves case alone configures the build with 'testcase',
        # so a flag asking for anything else writes needs the build drops.
        code, payload = run_convert(
            tmp_path, ["--need-type", "check"], toml="[test_reports]\n"
        )
        assert code == 2
        assert payload == {}
        message = capsys.readouterr().err
        assert "--need-type is 'check'" in message
        assert "does not set case" in message
        assert "'testcase'" in message

    def test_need_type_flag_without_a_config_file_is_free(self, tmp_path):
        # Without a file there is nothing to hold the flag against; the output
        # depends on the arguments alone, as with --no-config.
        code, payload = run_convert(tmp_path, ["--need-type", "check"])
        assert code == 0
        assert _first_need(payload)["type"] == "check"
        code, payload = run_convert(
            tmp_path,
            ["--no-config", "--need-type", "check"],
            toml="[test_reports]\n",
        )
        assert code == 0
        assert _first_need(payload)["type"] == "check"

    def test_a_matching_need_type_flag_is_fine(self, tmp_path):
        code, payload = run_convert(
            tmp_path,
            ["--need-type", "check"],
            toml="""
            [test_reports.case]
            directive = "test-case"
            type = "check"
            name = "Check"
            prefix = "CH_"
            color = "#999999"
            style = "rectangle"
            """,
        )
        assert code == 0
        assert _first_need(payload)["type"] == "check"


class TestExtraOptionFlag:
    """The flag adds to the section's list; a name the list lacks is reported.

    A repeatable flag reads as additive, so it is one -- ``--no-config`` is the
    way to leave the file's list out. The build registers exactly the section's
    ``extra_options`` as fields, so a field exported under any other name is
    dropped by ``needimport`` as an unknown key -- the flag may stand in for a
    build configured elsewhere, but the mismatch must not be silent.
    """

    def test_the_flag_adds_to_the_section_s_list(self, tmp_path):
        code, payload = run_convert(
            tmp_path,
            ["--extra-option", "Requirement"],
            toml='[test_reports]\nextra_options = ["TestType"]\n',
            xml=GTEST_XML,
        )
        assert code == 0
        needs = payload["versions"][payload["current_version"]]["needs"]
        assert all(
            "TestType" in need and "Requirement" in need for need in needs.values()
        )
        declared = payload["versions"][payload["current_version"]]["needs_schema"]
        assert {"TestType", "Requirement"} <= set(declared["properties"])

    def test_a_name_outside_the_section_s_list_warns(self, tmp_path, capsys):
        code, payload = run_convert(
            tmp_path,
            ["--extra-option", "Requirement"],
            toml='[test_reports]\nextra_options = ["TestType"]\n',
            xml=GTEST_XML,
        )
        assert code == 0
        needs = payload["versions"][payload["current_version"]]["needs"]
        assert all("Requirement" in need for need in needs.values())
        err = capsys.readouterr().err
        assert "--extra-option Requirement" in err
        assert "extra_options" in err and DEFAULT_TOML_FILENAME in err
        assert "needimport" in err

    def test_a_name_from_the_section_s_list_is_quiet(self, tmp_path, capsys):
        code, _ = run_convert(
            tmp_path,
            ["--extra-option", "TestType"],
            toml='[test_reports]\nextra_options = ["TestType", "Requirement"]\n',
            xml=GTEST_XML,
        )
        assert code == 0
        assert "--extra-option" not in capsys.readouterr().err

    def test_without_a_config_file_there_is_nothing_to_compare_against(
        self, tmp_path, capsys
    ):
        code, _ = run_convert(
            tmp_path, ["--extra-option", "Requirement"], xml=GTEST_XML
        )
        assert code == 0
        assert "--extra-option" not in capsys.readouterr().err


def test_every_conversion_key_has_a_builtin_default():
    # The import-time guard says the same; this keeps saying it under -O.
    assert set(_DEFAULTS) == set(CONVERSION_KEYS)
