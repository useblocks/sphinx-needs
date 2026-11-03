"""Tests for the test-case source location as need fields (TR-D).

The JUnit/googletest ``<testcase>`` attributes ``file`` and ``line`` point at
the *test source*. They were parsed but never reached ``add_need``, because the
need field ``file`` already carries the path of the XML *report* -- and
``tr_file_option``, which exists to rename that field, was only half wired: the
registration honoured it while the directives kept passing ``file=``.
"""

from pathlib import Path

import pytest


def _field_values(html, field):
    """All rendered values of a sphinx-needs meta field."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    return [
        span.get_text(strip=True)
        for span in soup.select(f"span.needs_{field} span.needs_data")
    ]


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/source_location"}],
    indirect=True,
)
class TestSourceLocationDefaultFieldNames:
    """Out of the box the source location lands on ``case_file``/``case_line``."""

    def test_build_succeeds(self, test_app):
        app = test_app
        app.build()
        assert app.statuscode == 0

    def test_source_file_is_a_need_field(self, test_app):
        app = test_app
        app.build()
        html = Path(app.outdir, "index.html").read_text(encoding="utf-8")

        assert "src/math_test.cc" in _field_values(html, "case_file")

    def test_source_line_is_a_need_field(self, test_app):
        app = test_app
        app.build()
        html = Path(app.outdir, "index.html").read_text(encoding="utf-8")

        assert "12" in _field_values(html, "case_line")

    def test_report_path_stays_on_the_file_field(self, test_app):
        """The existing meaning of ``file`` is unchanged by default."""
        app = test_app
        app.build()
        html = Path(app.outdir, "index.html").read_text(encoding="utf-8")

        assert any(
            value.endswith("gtest_data.xml") for value in _field_values(html, "file")
        )

    def test_missing_line_attribute_renders_empty_not_the_sentinel(self, test_app):
        """pytest's default junit_family drops file/line; -1 must not leak."""
        app = test_app
        app.build()
        html = Path(app.outdir, "index.html").read_text(encoding="utf-8")

        assert "-1" not in _field_values(html, "case_line")


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/source_location_renamed"}],
    indirect=True,
)
class TestSourceLocationRenamedFieldNames:
    """``tr_file_option`` frees ``file``/``line`` for the source location."""

    def test_build_succeeds(self, test_app):
        app = test_app
        app.build()
        assert app.statuscode == 0

    def test_source_location_uses_the_configured_names(self, test_app):
        app = test_app
        app.build()
        html = Path(app.outdir, "index.html").read_text(encoding="utf-8")

        assert "src/math_test.cc" in _field_values(html, "file")
        assert "12" in _field_values(html, "line")

    def test_report_path_moved_to_the_renamed_field(self, test_app):
        """The half-wired rename: directives must honour tr_file_option too."""
        app = test_app
        app.build()
        html = Path(app.outdir, "index.html").read_text(encoding="utf-8")

        assert any(
            value.endswith("gtest_data.xml")
            for value in _field_values(html, "report_file")
        )


class TestFieldNameCollisionIsRejected:
    """Two options resolving to one field name must fail loudly, not crash.

    Without the check, ``add_need`` is called with the same keyword twice and
    raises a bare ``TypeError`` from deep inside a directive.
    """

    class _Config:
        def __init__(self, **values):
            self.__dict__.update(values)

    def test_report_and_source_file_sharing_a_name_is_an_error(self):
        from sphinx_test_reports.exceptions import InvalidConfigurationError
        from sphinx_test_reports.test_reports import check_field_name_collisions

        config = self._Config(
            tr_file_option="file",
            tr_source_file_option="file",
            tr_source_line_option="line",
        )

        with pytest.raises(InvalidConfigurationError) as exc:
            check_field_name_collisions(config)

        assert "tr_file_option" in str(exc.value)
        assert "tr_source_file_option" in str(exc.value)

    def test_source_file_and_source_line_sharing_a_name_is_an_error(self):
        from sphinx_test_reports.exceptions import InvalidConfigurationError
        from sphinx_test_reports.test_reports import check_field_name_collisions

        config = self._Config(
            tr_file_option="report_file",
            tr_source_file_option="location",
            tr_source_line_option="location",
        )

        with pytest.raises(InvalidConfigurationError):
            check_field_name_collisions(config)

    def test_a_rename_onto_a_fixed_field_is_an_error(self):
        # The same failure as two options sharing a name: every test-case
        # directive passes `case` to add_need already.
        from sphinx_test_reports.exceptions import InvalidConfigurationError
        from sphinx_test_reports.test_reports import check_field_name_collisions

        config = self._Config(
            tr_file_option="case",
            tr_source_file_option="case_file",
            tr_source_line_option="case_line",
        )

        with pytest.raises(InvalidConfigurationError) as exc:
            check_field_name_collisions(config)

        assert "tr_file_option" in str(exc.value)
        assert "'case'" in str(exc.value)

    def test_distinct_names_are_accepted(self):
        from sphinx_test_reports.test_reports import check_field_name_collisions

        config = self._Config(
            tr_file_option="report_file",
            tr_source_file_option="file",
            tr_source_line_option="line",
        )

        assert check_field_name_collisions(config) is None


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "needs", "srcdir": "doc_test/source_location"}],
    indirect=True,
)
def test_an_absent_location_or_parameter_is_null(test_app):
    """A case the report gives no ``file``/``line`` for (pytest's default
    ``junit_family``), and one without a parameter, hold null in ``case_file``,
    ``case_line`` and ``case_parameter``, never ``""`` (#2372); a location the
    report gives is kept. ``Works/0``, the one case with a parameter (Google
    Test's ``value_param`` / ``type_param``), holds it (#2390)."""
    import json

    app = test_app
    app.build()
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    needs = data["versions"][data["current_version"]]["needs"].values()
    cases = [need for need in needs if need["type"] == "testcase"]
    pytest_cases = [n for n in cases if n["id"].startswith("SRCLOC_TF_2")]
    gtest_cases = [n for n in cases if n["id"].startswith("SRCLOC_TF_1")]
    assert pytest_cases and gtest_cases
    # pytest's report gives a file but no line
    for need in pytest_cases:
        assert need["case_line"] is None, need["id"]
    # gtest's type and value, type first; the name keeps its /0
    (works,) = [n for n in gtest_cases if n["case"] == "Works/0"]
    assert (works["case_name"], works["case_parameter"]) == ("Works/0", "int, 42")
    for need in cases:
        if need is not works:
            assert need["case_parameter"] is None, need["id"]
        assert "" not in (need["case_file"], need["case_line"]), need["id"]
    assert {(n["case_file"], n["case_line"]) for n in gtest_cases} >= {
        ("src/math_test.cc", "12")
    }
