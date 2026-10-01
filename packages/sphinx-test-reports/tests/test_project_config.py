"""Tests for the declarative configuration (``ubproject.toml``, ``[test_reports]``).

The loader validates and normalises the section, and the Sphinx build bridges
its keys onto the ``tr_*`` config values. Both must agree on which file
describes a project, or the build is configured by something other than what
the project declares.

This is the half that needs Sphinx: the bridge onto the ``tr_*`` values, its precedence
and Sphinx's confval type check. The loader's half is ub-test-reports',
``packages/ub-test-reports/tests/test_project_config.py``.
"""

from io import StringIO
from pathlib import Path
from shutil import copytree

import pytest

from ub_test_reports.projectconfig import (
    DEFAULT_TOML_FILENAME,
    SECTION,
)


def _write(tmp_path, toml_source, name=DEFAULT_TOML_FILENAME):
    config = tmp_path / name
    config.write_text(toml_source, encoding="utf-8")
    return config


def _not_utf8(tmp_path):
    """A file saved in Latin-1: ``é`` is the lone byte 0xE9, which UTF-8 refuses."""
    config = tmp_path / DEFAULT_TOML_FILENAME
    config.write_bytes("[test_reports]\nfile_option = 'café'\n".encode("latin-1"))
    return config


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

        from sphinx_test_reports.exceptions import InvalidConfigurationError

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

    def test_bridge_rejects_a_file_that_is_not_utf8(self, tmp_path):
        """The shared reader's refusal aborts the build like any other."""
        copytree(Path(__file__).parent / "doc_test" / "basic_doc", tmp_path / "docs")
        docs = tmp_path / "docs"
        _not_utf8(docs)

        from sphinx.application import Sphinx

        from sphinx_test_reports.exceptions import InvalidConfigurationError

        with pytest.raises(InvalidConfigurationError, match="not valid UTF-8 TOML"):
            Sphinx(
                srcdir=docs,
                confdir=docs,
                outdir=docs / "_build" / "html",
                doctreedir=docs / "_build" / "doctrees",
                buildername="html",
                freshenv=True,
            )


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

    def test_build_needs_table_is_not_applied_to_the_build(self, tmp_path):
        docs = _basic_doc(
            tmp_path,
            "[test_reports]\nfile_option = 'ok'\n\n[test_reports.build.needs]\nproject = 'p'\n",
        )
        app, warnings = _build(docs)
        # Only this table's fate is under test; other builds in the process may
        # already have emitted unrelated Sphinx warnings.
        assert "convert" not in warnings
        assert app.config.tr_file_option == "ok"
        assert not hasattr(app.config, "tr_convert")

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
