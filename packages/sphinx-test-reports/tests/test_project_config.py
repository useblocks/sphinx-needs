"""Tests for the declarative configuration (``ubproject.toml``, ``[test_reports]``).

The loader validates and normalises the section, and the Sphinx build bridges
its keys onto the ``tr_*`` config values. Both must agree on which file
describes a project, or the build is configured by something other than what
the project declares.
"""

import os
import subprocess
import sys
from io import StringIO
from pathlib import Path
from shutil import copytree

import pytest

from sphinxcontrib.test_reports.exceptions import InvalidConfigurationError
from sphinxcontrib.test_reports.projectconfig import (
    BRIDGE_KEYS,
    DEFAULT_TOML_FILENAME,
    FOREIGN_TABLES,
    SECTION,
    TomlConfigError,
    find_project_config,
    load_project_config,
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

    def test_foreign_sub_table_is_kept_without_a_warning(self, tmp_path):
        # [test_reports.build] belongs to the command line. This reader must
        # neither complain about it nor apply it to a tr_* value -- the section
        # describes the project, not just this extension.
        _write(
            tmp_path,
            """
            [test_reports]
            file_option = "report_file"

            [test_reports.build.needs]
            project = "demo"
            need_type = "check"
            """,
        )
        reported = []
        section = load_project_config(tmp_path / DEFAULT_TOML_FILENAME, reported.append)
        assert reported == []
        assert section["build"] == {"needs": {"project": "demo", "need_type": "check"}}
        assert not set(FOREIGN_TABLES) & set(BRIDGE_KEYS)

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

    def test_absolute_paths_stay_untouched(self, tmp_path):
        _write(tmp_path, f'[test_reports]\nrootdir = "{tmp_path}"\n')
        config = load_project_config(tmp_path / DEFAULT_TOML_FILENAME)
        assert config["rootdir"] == str(tmp_path)


class TestSphinxBridge:
    """The build reads the same section and honours the same precedence."""

    @pytest.mark.parametrize(
        "test_app",
        [{"buildername": "html", "srcdir": "doc_test/ubproject_toml"}],
        indirect=True,
    )
    def test_build_succeeds(self, test_app):
        test_app.build()
        assert test_app.statuscode == 0

    @pytest.mark.parametrize(
        "test_app",
        [{"buildername": "html", "srcdir": "doc_test/ubproject_toml"}],
        indirect=True,
    )
    def test_toml_beats_conf_py(self, test_app):
        """conf.py names one field, ubproject.toml another; TOML must win."""
        test_app.build()
        html = Path(test_app.outdir, "index.html").read_text(encoding="utf-8")
        # file_option = "report_file" (TOML) won over "confpy_report_file".
        assert "needs_report_file" in html
        # The report path lands on the renamed field, the source location on
        # file/line -- the rename took effect end to end.
        assert "gtest_data.xml" in html

    @pytest.mark.parametrize(
        "test_app",
        [{"buildername": "html", "srcdir": "doc_test/ubproject_toml"}],
        indirect=True,
    )
    def test_extra_options_from_toml_are_accepted(self, test_app):
        """:more_info: is only valid because tr_extra_options came from TOML."""
        test_app.build()
        html = Path(test_app.outdir, "index.html").read_text(encoding="utf-8")
        assert "accepted because tr_extra_options came from ubproject.toml" in html

    def test_bridge_rejects_a_broken_section(self, tmp_path):
        """A malformed section aborts the build as a configuration error.

        The bridge runs on ``config-inited``, so the error surfaces while the
        application is set up -- before any document is read.
        """
        copytree(Path(__file__).parent / "doc_test" / "basic_doc", tmp_path / "docs")
        _write(tmp_path / "docs", "[test_reports]\nsuite_id_length = 'four'\n")

        from sphinx.application import Sphinx

        docs = tmp_path / "docs"
        with pytest.raises(InvalidConfigurationError, match="suite_id_length"):
            Sphinx(
                srcdir=docs,
                confdir=docs,
                outdir=docs / "_build" / "html",
                doctreedir=docs / "_build" / "doctrees",
                buildername="html",
                freshenv=True,
            )


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


def _build(srcdir, **kwargs):
    """Set up a Sphinx application, returning it with its warning output.

    Pass ``status=StringIO()`` (and ``verbosity=1``) to capture the
    informational output as well; it is discarded by default.
    """
    from sphinx.application import Sphinx

    kwargs.setdefault("status", None)
    warnings = StringIO()
    app = Sphinx(
        srcdir=srcdir,
        confdir=srcdir,
        outdir=srcdir / "_build" / "html",
        doctreedir=srcdir / "_build" / "doctrees",
        buildername="html",
        freshenv=True,
        warning=warnings,
        **kwargs,
    )
    return app, warnings.getvalue()


def _basic_doc(tmp_path, toml=None, conf_extra=""):
    docs = tmp_path / "docs"
    copytree(Path(__file__).parent / "doc_test" / "basic_doc", docs)
    # Bound the upward search so the outcome cannot depend on the sandbox.
    (tmp_path / ".git").mkdir()
    if toml is not None:
        _write(docs, toml)
    if conf_extra:
        with (docs / "conf.py").open("a", encoding="utf-8") as handle:
            handle.write("\n" + conf_extra + "\n")
    return docs


class TestBridgePrecedence:
    """``-D`` > TOML > conf.py, and the diagnostics for a file that is missing."""

    def test_command_line_override_beats_toml(self, tmp_path):
        # -D is the per-invocation escape hatch. Sphinx applies it before
        # config-inited, so the bridge has to leave those keys alone.
        docs = _basic_doc(tmp_path, "[test_reports]\nfile_option = 'from_toml'\n")
        app, _ = _build(docs, confoverrides={"tr_file_option": "from_command_line"})
        assert app.config.tr_file_option == "from_command_line"

    def test_toml_beats_conf_py_without_an_override(self, tmp_path):
        docs = _basic_doc(
            tmp_path,
            "[test_reports]\nfile_option = 'from_toml'\n",
            conf_extra="tr_file_option = 'from_conf_py'",
        )
        app, _ = _build(docs)
        assert app.config.tr_file_option == "from_toml"

    def test_disabling_toml_reading_is_not_a_type_warning(self, tmp_path):
        # The documented opt-out must not trip Sphinx's own confval check --
        # a project building with -W would fail on it.
        docs = _basic_doc(
            tmp_path,
            "[test_reports]\nfile_option = 'from_toml'\n",
            conf_extra="tr_config_from_toml = None",
        )
        app, warnings = _build(docs)
        assert "tr_config_from_toml" not in warnings
        assert app.config.tr_file_option == "file"

    def test_missing_explicit_config_warns(self, tmp_path):
        docs = _basic_doc(tmp_path, conf_extra="tr_config_from_toml = 'nope.toml'")
        _, warnings = _build(docs)
        assert "does not exist" in warnings

    def test_missing_default_config_is_silent(self, tmp_path):
        docs = _basic_doc(tmp_path)
        _, warnings = _build(docs)
        assert "ubproject.toml" not in warnings

    def test_unknown_key_warns_but_builds(self, tmp_path):
        docs = _basic_doc(
            tmp_path, "[test_reports]\nfile_option = 'ok'\nno_such_key = 1\n"
        )
        app, warnings = _build(docs)
        assert "no_such_key" in warnings
        assert app.config.tr_file_option == "ok"

    def test_walks_up_from_the_confdir(self, tmp_path):
        # ubproject.toml at the repo root, conf.py in docs/ -- the layout the
        # shared file exists for.
        docs = _basic_doc(tmp_path)
        _write(tmp_path, "[test_reports]\nfile_option = 'from_the_root'\n")
        app, _ = _build(docs)
        assert app.config.tr_file_option == "from_the_root"

    def test_walks_past_a_pyproject_toml_beside_conf_py(self, tmp_path):
        # The docs directory being a distribution of its own does not make it
        # the project root; the shared file above it must still be found.
        docs = _basic_doc(tmp_path)
        (docs / "pyproject.toml").write_text("", encoding="utf-8")
        _write(tmp_path, "[test_reports]\nfile_option = 'from_the_root'\n")
        app, _ = _build(docs)
        assert app.config.tr_file_option == "from_the_root"

    def test_a_fruitless_search_says_where_it_ended(self, tmp_path):
        # Not an error and not a warning -- most projects have no file -- but
        # visible with -v, so a misplaced file can be diagnosed.
        docs = _basic_doc(tmp_path)
        status = StringIO()
        _build(docs, status=status, verbosity=1)
        assert f"repository root {tmp_path}" in status.getvalue()


def _documented_toml_example():
    """The ``[test_reports]`` example of ``docs/configuration.rst``, verbatim.

    Read from the docs rather than copied, so the test fails when the example
    and the code drift apart -- the example is what a project copies.
    """
    text = (Path(__file__).parents[1] / "docs" / "configuration.rst").read_text(
        encoding="utf-8"
    )
    section = text[text.index("Declarative configuration (ubproject.toml)") :]
    directive = ".. code-block:: toml\n"
    body = section[section.index(directive) + len(directive) :].splitlines()
    block = []
    for line in body[1:]:  # skip the blank line after the directive
        if line and not line.startswith("   "):
            break
        block.append(line[3:])
    return "\n".join(block) + "\n"


class TestConfvalTypes:
    """The bridged values must pass Sphinx's own confval type check.

    ``check_confval_types`` runs at ``config-inited`` after the bridge and
    compares each value's type with its default's. ``tr_rootdir`` defaults to
    Sphinx's ``confdir`` -- a ``_StrPath`` -- so a plain string, the only thing
    TOML (or a string literal in ``conf.py``) can supply, drew a warning, and a
    project building with ``-W`` failed on the documented example.
    """

    def test_rootdir_from_toml_is_not_a_type_warning(self, tmp_path):
        docs = _basic_doc(tmp_path)
        _write(tmp_path, '[test_reports]\nrootdir = "docs"\n')
        app, warnings = _build(docs)
        assert "tr_rootdir" not in warnings
        assert app.config.tr_rootdir == str(tmp_path / "docs")

    def test_rootdir_as_a_string_in_conf_py_is_not_a_type_warning(self, tmp_path):
        docs = _basic_doc(tmp_path, conf_extra='tr_rootdir = "."')
        _, warnings = _build(docs)
        assert "tr_rootdir" not in warnings

    def test_the_documented_example_applies_without_warnings(self, tmp_path):
        docs = _basic_doc(tmp_path)
        _write(tmp_path, _documented_toml_example())
        app, warnings = _build(docs)
        own = [
            line
            for line in warnings.splitlines()
            if "tr_" in line or "ubproject" in line or f"[{SECTION}]" in line
        ]
        assert own == []
        assert app.config.tr_file_option == "report_file"
        assert app.config.tr_rootdir == str(tmp_path / "docs")
        assert app.config.tr_case[0] == "test-case"


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
            "import sphinxcontrib.test_reports.projectconfig\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True
        )
        assert result.returncode == 0, result.stderr

    def test_a_missing_sphinx_needs_is_an_extension_error(self):
        # The lazy `setup` owns the message Sphinx would have produced for a
        # broken extension import, because Sphinx fetches `setup` with
        # getattr() and would otherwise show a raw traceback. Sphinx renders
        # the wrapped exception itself, so the message must not carry it a
        # second time. Checked in a subprocess: sphinx_needs is importable
        # here.
        code = (
            "import sys\n"
            "sys.modules['sphinx_needs'] = None\n"  # `from sphinx_needs...` fails
            "import sphinxcontrib.test_reports as pkg\n"
            "from sphinx.errors import ExtensionError\n"
            "try:\n"
            "    pkg.setup\n"
            "except ExtensionError as error:\n"
            "    print(error)\n"
            "else:\n"
            "    raise AssertionError('no ExtensionError')\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True
        )
        assert result.returncode == 0, result.stderr
        message = result.stdout.strip()
        assert message.startswith(
            "Could not import extension sphinxcontrib.test_reports"
        )
        assert message.count("(exception:") == 1
        assert "sphinx_needs" in message
