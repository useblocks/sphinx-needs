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
        from sphinxcontrib.test_reports.exceptions import InvalidConfigurationError
        from sphinxcontrib.test_reports.test_reports import check_field_name_collisions

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
        from sphinxcontrib.test_reports.exceptions import InvalidConfigurationError
        from sphinxcontrib.test_reports.test_reports import check_field_name_collisions

        config = self._Config(
            tr_file_option="report_file",
            tr_source_file_option="location",
            tr_source_line_option="location",
        )

        with pytest.raises(InvalidConfigurationError):
            check_field_name_collisions(config)

    def test_distinct_names_are_accepted(self):
        from sphinxcontrib.test_reports.test_reports import check_field_name_collisions

        config = self._Config(
            tr_file_option="report_file",
            tr_source_file_option="file",
            tr_source_line_option="line",
        )

        assert check_field_name_collisions(config) is None
