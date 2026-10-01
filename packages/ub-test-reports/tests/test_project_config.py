"""Tests for the declarative configuration (``ubproject.toml``, ``[test_reports]``).

The loader validates and normalises the section, and the Sphinx build bridges
its keys onto the ``tr_*`` config values. Both must agree on which file
describes a project, or the build is configured by something other than what
the project declares.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

import ub_project
from ub_project import ProjectConfigError
from ub_test_reports.projectconfig import (
    BRIDGE_KEYS,
    BUILD_TABLE,
    DEFAULT_FIELD_NAMES,
    DEFAULT_TOML_FILENAME,
    TomlConfigError,
    field_names,
    find_project_config,
    load_project_config,
    needs_settings,
)


def _write(tmp_path, toml_source, name=DEFAULT_TOML_FILENAME):
    config = tmp_path / name
    config.write_text(toml_source, encoding="utf-8")
    return config


class TestLoader:
    """The Sphinx-free loader: parsing, normalising, anchoring, rejecting."""

    def test_missing_file_is_none(self, tmp_path):
        assert load_project_config(tmp_path / DEFAULT_TOML_FILENAME) is None

    def test_missing_section_is_empty(self, tmp_path):
        _write(tmp_path, '[project]\nname = "x"\n')
        assert load_project_config(tmp_path / DEFAULT_TOML_FILENAME) == {}

    def test_full_section_round_trips(self, tmp_path):
        _write(
            tmp_path,
            """
            [test_reports]
            file_option = "report_file"
            source_file_option = "file"
            import_encoding = "latin1"
            deterministic_case_ids = true
            suite_id_length = 4
            extra_options = ["more_info"]
            property_link_types = { request = "req" }
            """,
        )
        config = load_project_config(tmp_path / DEFAULT_TOML_FILENAME)
        assert config["file_option"] == "report_file"
        assert config["source_file_option"] == "file"
        assert config["import_encoding"] == "latin1"
        assert config["deterministic_case_ids"] is True
        assert config["suite_id_length"] == 4
        assert config["extra_options"] == ["more_info"]
        assert config["property_link_types"] == {"request": "req"}

    def test_build_needs_table_is_validated_but_never_bridged(self, tmp_path):
        # [test_reports.build.needs] belongs to the command line. The build
        # validates it -- one file, one verdict -- but must not map it onto a
        # tr_* value.
        _write(
            tmp_path,
            """
            [test_reports]
            file_option = "report_file"

            [test_reports.build.needs]
            project = "demo"
            tags = ["ci"]
            """,
        )
        reported = []
        section = load_project_config(tmp_path / DEFAULT_TOML_FILENAME, reported.append)
        assert reported == []
        assert needs_settings(section) == {"project": "demo", "tags": ["ci"]}
        assert BUILD_TABLE not in BRIDGE_KEYS

    @pytest.mark.parametrize(
        ("key", "value"),
        [
            ("project", "42"),
            ("tags", '"ci, unit"'),  # a bare string is not an array
            ("tags", "[1]"),
            ("link_properties", '["a"]'),
            ("link_properties", '{ Verifies = ["verifies"] }'),  # values too
        ],
    )
    def test_build_needs_wrong_types_are_rejected(self, tmp_path, key, value):
        _write(tmp_path, f"[test_reports.build.needs]\n{key} = {value}\n")
        with pytest.raises(TomlConfigError, match=f"build.needs.{key}"):
            load_project_config(tmp_path / DEFAULT_TOML_FILENAME)

    def test_unknown_artifact_under_build_is_reported_but_not_fatal(self, tmp_path):
        # `build` holds one table per artifact the command line produces. A
        # newer command may produce one this version does not know, and a file
        # naming it must not take the build down.
        _write(
            tmp_path,
            """
            [test_reports.build.needs]
            project = "p"

            [test_reports.build.graph]
            format = "svg"
            """,
        )
        reported = []
        section = load_project_config(tmp_path / DEFAULT_TOML_FILENAME, reported.append)
        assert needs_settings(section) == {"project": "p"}
        assert section[BUILD_TABLE] == {"needs": {"project": "p"}}
        assert len(reported) == 1
        assert "graph" in reported[0]
        assert "[test_reports.build]" in reported[0]

    def test_a_non_table_needs_artifact_is_rejected(self, tmp_path):
        _write(tmp_path, '[test_reports.build]\nneeds = "yes"\n')
        with pytest.raises(TomlConfigError, match=r"build.needs"):
            load_project_config(tmp_path / DEFAULT_TOML_FILENAME)

    def test_build_needs_unknown_key_is_reported_but_not_fatal(self, tmp_path):
        _write(tmp_path, "[test_reports.build.needs]\nprojct = 'typo'\nproject = 'p'\n")
        reported = []
        section = load_project_config(tmp_path / DEFAULT_TOML_FILENAME, reported.append)
        assert needs_settings(section) == {"project": "p"}
        assert len(reported) == 1
        assert "projct" in reported[0]
        assert "[test_reports.build.needs]" in reported[0]

    def test_need_type_and_case_type_must_agree(self, tmp_path):
        # The converter takes the need type (and the deterministic-ID prefix)
        # from build.needs.need_type, the build from case's type. Disagreeing
        # produces a needs.json the build neither registers nor cross-links.
        _write(
            tmp_path,
            """
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
        with pytest.raises(TomlConfigError, match="need_type"):
            load_project_config(tmp_path / DEFAULT_TOML_FILENAME)

    def test_a_missing_side_is_compared_at_its_default(self, tmp_path):
        # A customised case next to a convert table without need_type is a
        # disagreement too: the converter would write the default type.
        _write(
            tmp_path,
            """
            [test_reports.build.needs]
            project = "p"

            [test_reports.case]
            directive = "test-case"
            type = "check"
            name = "Check"
            prefix = "CH_"
            color = "#999999"
            style = "rectangle"
            """,
        )
        with pytest.raises(TomlConfigError, match=r"'testcase'.*'check'"):
            load_project_config(tmp_path / DEFAULT_TOML_FILENAME)
        # ... and the mirror: need_type set, case left at its default.
        _write(tmp_path, '[test_reports.build.needs]\nneed_type = "check"\n')
        with pytest.raises(TomlConfigError, match=r"'check'.*'testcase'"):
            load_project_config(tmp_path / DEFAULT_TOML_FILENAME)

    def test_without_a_convert_table_the_case_type_is_free(self, tmp_path):
        # A project that only builds may name its case type as it likes.
        _write(
            tmp_path,
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
        assert (
            load_project_config(tmp_path / DEFAULT_TOML_FILENAME)["case"][1] == "check"
        )

    def test_empty_link_property_names_are_rejected_by_the_loader(self, tmp_path):
        # One verdict for both consumers: the build refuses what the converter
        # would refuse.
        _write(
            tmp_path,
            '[test_reports.build.needs]\nlink_properties = { Verifies = "" }\n',
        )
        with pytest.raises(TomlConfigError, match="link_properties"):
            load_project_config(tmp_path / DEFAULT_TOML_FILENAME)

    def test_field_names_default_to_the_build_s(self, tmp_path):
        _write(tmp_path, "[test_reports]\nsource_file_option = 'src'\n")
        section = load_project_config(tmp_path / DEFAULT_TOML_FILENAME)
        names = field_names(section)
        assert names["source_file_option"] == "src"
        assert names["file_option"] == DEFAULT_FIELD_NAMES["file_option"] == "file"
        assert names["source_line_option"] == "case_line"

    def test_colliding_field_names_are_rejected(self, tmp_path):
        # file (report path) and file (source path) cannot share a field.
        _write(tmp_path, "[test_reports]\nsource_file_option = 'file'\n")
        with pytest.raises(TomlConfigError, match="both name the need field 'file'"):
            load_project_config(tmp_path / DEFAULT_TOML_FILENAME)

    @pytest.mark.parametrize(
        ("key", "name"),
        [
            ("file_option", "case"),
            ("source_file_option", "result"),
            ("source_line_option", "id"),
        ],
    )
    def test_a_rename_onto_a_fixed_field_is_rejected(self, tmp_path, key, name):
        # Every test-case need has these already: the directives would pass
        # the keyword twice, the converter overwrite one value with the other.
        _write(tmp_path, f"[test_reports]\n{key} = '{name}'\n")
        with pytest.raises(TomlConfigError, match=f"{key} = '{name}'"):
            load_project_config(tmp_path / DEFAULT_TOML_FILENAME)

    def test_need_type_and_case_type_agreeing_is_fine(self, tmp_path):
        _write(
            tmp_path,
            """
            [test_reports.build.needs]
            need_type = "check"

            [test_reports.case]
            directive = "test-case"
            type = "check"
            name = "Check"
            prefix = "CH_"
            color = "#999999"
            style = "rectangle"
            """,
        )
        section = load_project_config(tmp_path / DEFAULT_TOML_FILENAME)
        assert section["case"][1] == needs_settings(section)["need_type"] == "check"

    def test_unknown_key_is_reported_but_not_fatal(self, tmp_path):
        # ubproject.toml is shared with tools on independent release cadences,
        # so a key this reader does not model must not take the build down --
        # but a typo has to be visible, and the key must not be passed on.
        _write(tmp_path, "[test_reports]\ndeterministic_id = true\n")
        reported = []
        section = load_project_config(tmp_path / DEFAULT_TOML_FILENAME, reported.append)
        assert section == {}
        assert len(reported) == 1
        assert "deterministic_id" in reported[0]
        assert "deterministic_case_ids" in reported[0]  # supported keys listed

    def test_unknown_key_needs_no_reporter(self, tmp_path):
        _write(tmp_path, "[test_reports]\nnope = 1\nfile_option = 'f'\n")
        assert load_project_config(tmp_path / DEFAULT_TOML_FILENAME) == {
            "file_option": "f"
        }

    @pytest.mark.parametrize(
        ("key", "value"),
        [
            ("property_link_types", '{ request = ["req"] }'),
            ("property_link_types", "{ request = 3 }"),
        ],
    )
    def test_table_values_are_type_checked(self, tmp_path, key, value):
        # Without this the value reaches the directives, which fail with a bare
        # TypeError on an unhashable field name instead of a config error.
        _write(tmp_path, f"[test_reports]\n{key} = {value}\n")
        with pytest.raises(TomlConfigError, match=key):
            load_project_config(tmp_path / DEFAULT_TOML_FILENAME)

    def test_json_mapping_nesting_stays_free_form(self, tmp_path):
        # It mirrors an arbitrary parser mapping, so only the outer table is
        # checked -- validating deeper would reject valid configurations.
        _write(
            tmp_path,
            "[test_reports.json_mapping.json_config.testsuite]\nname = 1\n",
        )
        section = load_project_config(tmp_path / DEFAULT_TOML_FILENAME)
        assert section["json_mapping"] == {"json_config": {"testsuite": {"name": 1}}}

    @pytest.mark.skipif(
        hasattr(os, "geteuid") and os.geteuid() == 0,
        reason="root reads unreadable files",
    )
    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="os.chmod on Windows only sets the read-only attribute; the file stays readable",
    )
    def test_unreadable_file_is_a_config_error(self, tmp_path):
        # is_file() succeeding does not mean the open will; an unwrapped
        # OSError would surface as a traceback instead of a config error.
        config = _write(tmp_path, "[test_reports]\nfile_option = 'f'\n")
        config.chmod(0o000)
        try:
            with pytest.raises(TomlConfigError, match="cannot be read"):
                load_project_config(config)
        finally:
            config.chmod(0o644)

    @pytest.mark.parametrize(
        ("key", "value"),
        [
            ("file_option", "42"),
            ("suite_id_length", '"four"'),  # string for int
            ("suite_id_length", "true"),  # bool must not pass for int
            ("deterministic_case_ids", '"yes"'),  # string for bool
            ("extra_options", '"more_info"'),  # a bare string is not an array
            ("property_link_types", '["a"]'),
        ],
    )
    def test_wrong_types_are_rejected(self, tmp_path, key, value):
        _write(tmp_path, f"[test_reports]\n{key} = {value}\n")
        with pytest.raises(TomlConfigError, match=key):
            load_project_config(tmp_path / DEFAULT_TOML_FILENAME)

    def test_invalid_toml_is_rejected(self, tmp_path):
        _write(tmp_path, "[test-reports\n")
        with pytest.raises(TomlConfigError, match="invalid TOML"):
            load_project_config(tmp_path / DEFAULT_TOML_FILENAME)

    def test_section_must_be_a_table(self, tmp_path):
        _write(tmp_path, "test_reports = 5\n")
        with pytest.raises(TomlConfigError, match="must be a table"):
            load_project_config(tmp_path / DEFAULT_TOML_FILENAME)

    def test_need_type_positional_list_still_works(self, tmp_path):
        # The conf.py spelling, so existing projects can copy their lists over
        # verbatim.
        _write(
            tmp_path,
            '[test_reports]\ncase = ["test-case", "testcase", "Test-Case", "TC_", "#999999", "rectangle"]\n',
        )
        config = load_project_config(tmp_path / DEFAULT_TOML_FILENAME)
        assert config["case"] == [
            "test-case",
            "testcase",
            "Test-Case",
            "TC_",
            "#999999",
            "rectangle",
        ]

    def test_need_type_named_table(self, tmp_path):
        # Six bare strings cannot be told apart; the table spelling names them.
        _write(
            tmp_path,
            """
            [test_reports.case]
            directive = "test-case"
            type = "testcase"
            name = "Test-Case"
            prefix = "TC_"
            color = "#999999"
            style = "rectangle"
            """,
        )
        config = load_project_config(tmp_path / DEFAULT_TOML_FILENAME)
        assert config["case"] == [
            "test-case",
            "testcase",
            "Test-Case",
            "TC_",
            "#999999",
            "rectangle",
        ]

    def test_need_type_table_rejects_partial_and_unknown(self, tmp_path):
        _write(tmp_path, '[test_reports.case]\ndirective = "test-case"\n')
        with pytest.raises(TomlConfigError, match="missing"):
            load_project_config(tmp_path / DEFAULT_TOML_FILENAME)
        _write(
            tmp_path,
            """
            [test_reports.case]
            directive = "test-case"
            type = "testcase"
            name = "Test-Case"
            prefix = "TC_"
            color = "#999999"
            style = "rectangle"
            typo = true
            """,
        )
        with pytest.raises(TomlConfigError, match="unknown typo"):
            load_project_config(tmp_path / DEFAULT_TOML_FILENAME)

    @pytest.mark.parametrize(
        ("toml_source", "problem"),
        [
            # A non-string value inside the named table. Without the check the
            # value is silently stringified and reaches sphinx-needs.
            (
                """
                [test_reports.case]
                directive = "test-case"
                type = "testcase"
                name = "Test-Case"
                prefix = "TC_"
                color = 999999
                style = "rectangle"
                """,
                "non-string color",
            ),
            # A non-string element of the positional list.
            (
                '[test_reports]\ncase = ["test-case", "testcase", "Test-Case", "TC_", 999999, "rectangle"]\n',
                "exactly 6 strings",
            ),
            # Too few elements.
            ('[test_reports]\ncase = ["test-case", "testcase"]\n', "exactly 6 strings"),
        ],
    )
    def test_need_type_values_must_be_strings(self, tmp_path, toml_source, problem):
        _write(tmp_path, toml_source)
        with pytest.raises(TomlConfigError, match=problem):
            load_project_config(tmp_path / DEFAULT_TOML_FILENAME)

    def test_relative_paths_anchor_to_the_toml_directory(self, tmp_path):
        # The file is self-describing: moving it as a unit keeps its relative
        # paths meaningful, and both consumers resolve them identically.
        subdir = tmp_path / "config"
        subdir.mkdir()
        _write(
            subdir,
            '[test_reports]\nrootdir = "docs"\nreport_template = "templates/report.txt"\n',
            name=subdir / DEFAULT_TOML_FILENAME,
        )
        config = load_project_config(subdir / DEFAULT_TOML_FILENAME)
        assert config["rootdir"] == str(subdir / "docs")
        assert config["report_template"] == str(subdir / "templates" / "report.txt")

    @pytest.mark.parametrize(
        "suffix",
        [
            pytest.param("", id="plain"),
            # the two forms ``Path`` normalises away: a round trip through it
            # would return ``/a/b`` for ``/a/b/`` and ``/a/b`` for ``/a//b``,
            # so these are the cases that tell "left as the string it was"
            # from "anchored, and absolute already"
            pytest.param(os.sep, id="trailing-separator"),
            pytest.param(f"{os.sep}{os.sep}x", id="doubled-separator"),
        ],
    )
    def test_absolute_paths_stay_untouched(self, tmp_path, suffix):
        # a TOML literal string: in a basic string a Windows path's backslashes
        # are escape sequences ("\U" starts a unicode escape) and the file is invalid
        value = f"{tmp_path}{suffix}"
        _write(tmp_path, f"[test_reports]\nrootdir = '{value}'\n")
        config = load_project_config(tmp_path / DEFAULT_TOML_FILENAME)
        assert config["rootdir"] == value


def _not_utf8(tmp_path):
    """A file saved in Latin-1: ``é`` is the lone byte 0xE9, which UTF-8 refuses."""
    config = tmp_path / DEFAULT_TOML_FILENAME
    config.write_bytes("[test_reports]\nfile_option = 'café'\n".encode("latin-1"))
    return config


class TestSharedReaderBoundary:
    """ub-project reads the file; its exception never leaves this package.

    Both consumers catch :class:`TomlConfigError` and nothing else, so a
    ``ProjectConfigError`` escaping the loader would reach the user as a
    traceback. Each case asserts the exact type and that the message is the
    shared reader's, word for word.
    """

    def _assert_re_raised(self, config):
        with pytest.raises(TomlConfigError) as caught:
            load_project_config(config)
        assert type(caught.value) is TomlConfigError
        cause = caught.value.__cause__
        assert isinstance(cause, ProjectConfigError)
        assert str(caught.value) == str(cause)
        return str(caught.value)

    def test_the_two_exceptions_are_unrelated(self):
        # a subclass either way round would put ub-project's exception on this
        # package's public surface
        assert not issubclass(TomlConfigError, ProjectConfigError)
        assert not issubclass(ProjectConfigError, TomlConfigError)

    def test_the_walk_is_the_shared_reader_s_own(self):
        # re-exported, not copied: a local fork of the walk would pass every
        # discovery test and drift from the reader the other members use
        assert find_project_config is ub_project.find_project_config

    def test_invalid_toml(self, tmp_path):
        message = self._assert_re_raised(_write(tmp_path, "[test-reports\n"))
        assert message.startswith(f"{tmp_path / DEFAULT_TOML_FILENAME}: invalid TOML: ")

    @pytest.mark.skipif(
        hasattr(os, "geteuid") and os.geteuid() == 0,
        reason="root reads unreadable files",
    )
    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="os.chmod on Windows only sets the read-only attribute; the file stays readable",
    )
    def test_unreadable_file(self, tmp_path):
        config = _write(tmp_path, "[test_reports]\nfile_option = 'f'\n")
        config.chmod(0o000)
        try:
            message = self._assert_re_raised(config)
        finally:
            config.chmod(0o644)
        assert message.startswith(f"{config}: cannot be read: ")

    def test_a_file_that_is_not_utf8(self, tmp_path):
        # New with ub-project: before it, the decode error escaped the loader
        # as a bare UnicodeDecodeError.
        config = _not_utf8(tmp_path)
        message = self._assert_re_raised(config)
        assert message.startswith(f"{config}: not valid UTF-8 TOML: ")


class TestDiscovery:
    """The upward search that lets both consumers find the same file.

    The search is bounded by the repository root -- the directory holding
    ``.git``: a ``pyproject.toml`` on the way up marks a Python distribution,
    not the project, and must not end the search. Outside any repository there
    is no such root, so the distribution root bounds it instead -- otherwise
    the walk reaches the filesystem root and adopts a stranger's file.
    """

    def test_finds_the_file_in_the_starting_directory(self, tmp_path):
        config = _write(tmp_path, "[test_reports]\n")
        assert find_project_config(tmp_path) == config

    def test_walks_up_to_the_repository_root(self, tmp_path):
        (tmp_path / ".git").mkdir()
        config = _write(tmp_path, "[test_reports]\n")
        deep = tmp_path / "docs" / "source"
        deep.mkdir(parents=True)
        assert find_project_config(deep) == config

    def test_a_pyproject_toml_beside_conf_py_does_not_end_the_search(self, tmp_path):
        # docs/ carrying its own pyproject.toml (its own dependency set) still
        # belongs to the project whose shared file sits at the repository root.
        (tmp_path / ".git").mkdir()
        config = _write(tmp_path, "[test_reports]\n")
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "pyproject.toml").write_text("", encoding="utf-8")
        assert find_project_config(docs) == config

    def test_walks_past_a_workspace_member_pyproject_toml(self, tmp_path):
        # A uv-workspace member: packages/<dist>/pyproject.toml with the docs
        # below it, and one ubproject.toml at the repository root describing
        # the whole monorepo.
        (tmp_path / ".git").mkdir()
        config = _write(tmp_path, "[test_reports]\n")
        member = tmp_path / "packages" / "dist"
        docs = member / "docs"
        docs.mkdir(parents=True)
        (member / "pyproject.toml").write_text("", encoding="utf-8")
        assert find_project_config(docs) == config

    def test_stops_at_a_nested_repository_without_the_file(self, tmp_path):
        # A checkout nested inside another repository (a vendored tree, a
        # submodule) must not adopt the outer repository's configuration.
        _write(tmp_path, "[test_reports]\n")
        inner = tmp_path / "vendor" / "inner"
        docs = inner / "docs"
        docs.mkdir(parents=True)
        (inner / ".git").write_text("gitdir: elsewhere\n", encoding="utf-8")
        assert find_project_config(docs) is None

    def test_stops_at_the_distribution_root_without_a_repository(self, tmp_path):
        # An unpacked sdist, a CI artefact directory, an exported docs tree:
        # no .git anywhere, so nothing above would end the walk and a
        # stranger's file further up would be adopted. The distribution root
        # bounds the search instead, so it is not.
        _write(tmp_path, "[test_reports]\n")  # a stranger's, two levels up
        dist = tmp_path / "downloads" / "sphinx-test-reports-1.4.0"
        docs = dist / "docs"
        docs.mkdir(parents=True)
        (dist / "pyproject.toml").write_text("", encoding="utf-8")
        assert find_project_config(docs) is None

    def test_the_file_at_the_distribution_root_is_still_found(self, tmp_path):
        # The distribution root bounds the search without hiding a file that
        # sits on it: an sdist shipping its own ubproject.toml is configured
        # by it.
        dist = tmp_path / "sphinx-test-reports-1.4.0"
        docs = dist / "docs"
        docs.mkdir(parents=True)
        (dist / "pyproject.toml").write_text("", encoding="utf-8")
        config = _write(dist, "[test_reports]\n")
        assert find_project_config(docs) == config

    def test_a_repository_marker_outranks_a_distribution_root(self, tmp_path):
        # The distribution root is only the fallback boundary. Inside a
        # repository the walk still passes a pyproject.toml on the way up --
        # the workspace-member layout above depends on it.
        (tmp_path / ".git").mkdir()
        config = _write(tmp_path, "[test_reports]\n")
        member = tmp_path / "packages" / "dist"
        docs = member / "docs"
        docs.mkdir(parents=True)
        (member / "pyproject.toml").write_text("", encoding="utf-8")
        assert find_project_config(docs) == config

    def test_a_fruitless_search_reports_the_distribution_root(self, tmp_path):
        dist = tmp_path / "sphinx-test-reports-1.4.0"
        docs = dist / "docs"
        docs.mkdir(parents=True)
        (dist / "pyproject.toml").write_text("", encoding="utf-8")
        reported = []
        assert find_project_config(docs, report=reported.append) is None
        assert len(reported) == 1
        assert f"distribution root {dist}" in reported[0]
        assert "pyproject.toml" in reported[0]

    def test_the_file_wins_over_the_marker_in_one_directory(self, tmp_path):
        # The root marker only ends a *fruitless* step; a repository root
        # holding the file is the canonical layout and must be found.
        config = _write(tmp_path, "[test_reports]\n")
        (tmp_path / ".git").mkdir()
        assert find_project_config(tmp_path) == config

    def test_missing_file_is_none(self, tmp_path):
        (tmp_path / ".git").mkdir()
        assert find_project_config(tmp_path) is None

    def test_a_fruitless_search_reports_where_it_ended(self, tmp_path):
        # "Not found" must not be silent: the report names the directory whose
        # marker ended the search, so a misplaced file can be diagnosed.
        (tmp_path / ".git").mkdir()
        docs = tmp_path / "docs"
        docs.mkdir()
        reported = []
        assert find_project_config(docs, report=reported.append) is None
        assert len(reported) == 1
        assert str(docs) in reported[0]
        assert f"repository root {tmp_path}" in reported[0]
        assert ".git" in reported[0]

    def test_a_successful_search_reports_nothing(self, tmp_path):
        (tmp_path / ".git").mkdir()
        _write(tmp_path, "[test_reports]\n")
        reported = []
        find_project_config(tmp_path / "docs", report=reported.append)
        assert reported == []

    def test_a_relative_start_is_searched_from_the_working_directory(
        self, tmp_path, monkeypatch
    ):
        # A converter started with a relative path must still see the parents.
        (tmp_path / ".git").mkdir()
        config = _write(tmp_path, "[test_reports]\n")
        docs = tmp_path / "docs"
        docs.mkdir()
        monkeypatch.chdir(docs)
        assert find_project_config(Path(".")) == config

    def test_a_symlinked_start_walks_the_link_s_parents(self, tmp_path):
        # The start is made absolute WITHOUT resolving: a symlinked docs/
        # belongs to the repository it is linked into, not to the one its
        # target lives in. The only case here that tells the two apart --
        # tmp_path is already resolved, so every other start is too.
        repo = tmp_path / "repo"
        (repo / ".git").mkdir(parents=True)
        config = _write(repo, "[test_reports]\n")
        elsewhere = tmp_path / "elsewhere"
        (elsewhere / ".git").mkdir(parents=True)
        target = elsewhere / "docs"
        target.mkdir()
        link = repo / "docs"
        try:
            link.symlink_to(target, target_is_directory=True)
        except OSError:  # Windows without the symlink privilege
            pytest.skip("creating a symlink needs a privilege this account lacks")
        assert find_project_config(link) == config


class TestPathAnchoring:
    """Relative paths anchor at the TOML file's directory, as given."""

    def test_anchoring_does_not_resolve_the_given_directory(self, tmp_path):
        # The loader leaves the form of the directory it was handed alone -- a
        # symlinked path stays symlinked. Whether to resolve it is the
        # consumer's call (Sphinx resolves its confdir before the bridge runs),
        # not something the loader decides behind its back.
        real = tmp_path / "real"
        real.mkdir()
        link = tmp_path / "link"
        link.symlink_to(real, target_is_directory=True)
        config = _write(link, "[test_reports]\nrootdir = 'reports'\n")
        section = load_project_config(config)
        assert section["rootdir"] == str(link / "reports")


class TestSphinxFree:
    """A consumer without the documentation toolchain can read the section."""

    def test_projectconfig_imports_without_sphinx(self):
        # Importing the module runs the package __init__, so the package must
        # not import Sphinx eagerly either -- or a build action that turns
        # reports into a needs.json dies with ModuleNotFoundError wherever
        # Sphinx is not installed. Checked in a subprocess: this process has
        # Sphinx imported already.
        code = (
            "import sys\n"
            "sys.modules['sphinx'] = None\n"  # any `import sphinx...` now fails
            "import ub_test_reports.projectconfig\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True
        )
        assert result.returncode == 0, result.stderr
