"""Tests for JUnit XML <properties> extraction and sphinx-needs integration."""

import os
from pathlib import Path

import pytest

xml_properties_path = os.path.join(
    os.path.dirname(__file__), "doc_test/utils", "xml_data_properties.xml"
)
xml_no_properties_path = os.path.join(
    os.path.dirname(__file__), "doc_test/utils", "xml_data.xml"
)
xml_empty_properties_path = os.path.join(
    os.path.dirname(__file__), "doc_test/utils", "xml_data_empty_properties.xml"
)


# ---------------------------------------------------------------------------
# Parser-level unit tests
# ---------------------------------------------------------------------------


class TestParserExtractsTestcaseProperties:
    """JUnitParser must extract <properties> from <testcase> elements."""

    def test_testcase_with_properties_returns_dict(self):
        from sphinxcontrib.test_reports.junitparser import JUnitParser

        parser = JUnitParser(xml_properties_path)
        results = parser.parse()

        # First suite, first testcase has verifies + priority
        tc = results[0]["testcases"][0]
        assert tc["name"] == "test_login_valid"
        assert isinstance(tc["properties"], dict)
        assert tc["properties"]["verifies"] == "REQ_AUTH_001,REQ_AUTH_002"
        assert tc["properties"]["priority"] == "high"

    def test_testcase_with_single_property(self):
        from sphinxcontrib.test_reports.junitparser import JUnitParser

        parser = JUnitParser(xml_properties_path)
        results = parser.parse()

        # First suite, second testcase has only verifies
        tc = results[0]["testcases"][1]
        assert tc["name"] == "test_login_invalid"
        assert tc["properties"] == {"verifies": "REQ_AUTH_003"}

    def test_testcase_without_properties_returns_empty_dict(self):
        from sphinxcontrib.test_reports.junitparser import JUnitParser

        parser = JUnitParser(xml_properties_path)
        results = parser.parse()

        # First suite, third testcase (test_logout) has failure but no properties
        tc = results[0]["testcases"][2]
        assert tc["name"] == "test_logout"
        assert tc["properties"] == {}

    def test_testcase_skipped_without_properties_returns_empty_dict(self):
        from sphinxcontrib.test_reports.junitparser import JUnitParser

        parser = JUnitParser(xml_properties_path)
        results = parser.parse()

        # First suite, fourth testcase (test_session_timeout) is skipped, no properties
        tc = results[0]["testcases"][3]
        assert tc["name"] == "test_session_timeout"
        assert tc["result"] == "skipped"
        assert tc["properties"] == {}

    def test_multiple_suites_testcase_properties(self):
        from sphinxcontrib.test_reports.junitparser import JUnitParser

        parser = JUnitParser(xml_properties_path)
        results = parser.parse()

        # Second suite, first testcase has verifies + category
        tc = results[1]["testcases"][0]
        assert tc["name"] == "test_get_users"
        assert tc["properties"]["verifies"] == "REQ_API_010,REQ_API_011,REQ_API_012"
        assert tc["properties"]["category"] == "integration"

    def test_testcase_without_any_properties_element(self):
        from sphinxcontrib.test_reports.junitparser import JUnitParser

        parser = JUnitParser(xml_properties_path)
        results = parser.parse()

        # Second suite, second testcase has no properties at all
        tc = results[1]["testcases"][1]
        assert tc["name"] == "test_create_user"
        assert tc["properties"] == {}


class TestParserExtractsTestsuiteProperties:
    """JUnitParser must extract <properties> from <testsuite> elements."""

    def test_testsuite_with_properties(self):
        from sphinxcontrib.test_reports.junitparser import JUnitParser

        parser = JUnitParser(xml_properties_path)
        results = parser.parse()

        # First suite has environment + build_id properties
        suite = results[0]
        assert suite["name"] == "acceptance_tests"
        assert isinstance(suite["properties"], dict)
        assert suite["properties"]["environment"] == "staging"
        assert suite["properties"]["build_id"] == "build-7742"

    def test_testsuite_without_properties(self):
        from sphinxcontrib.test_reports.junitparser import JUnitParser

        parser = JUnitParser(xml_properties_path)
        results = parser.parse()

        # Second suite has no properties
        suite = results[1]
        assert suite["name"] == "api_tests"
        assert suite["properties"] == {}


class TestParserBackwardCompatibility:
    """Adding properties extraction must not break existing XML without properties."""

    def test_existing_xml_still_parses(self):
        from sphinxcontrib.test_reports.junitparser import JUnitParser

        parser = JUnitParser(xml_no_properties_path)
        results = parser.parse()

        assert len(results) == 1
        assert results[0]["name"] == "unknown"
        assert results[0]["tests"] == 3
        assert results[0]["properties"] == {}

        for tc in results[0]["testcases"]:
            assert tc["properties"] == {}

    def test_existing_testcase_fields_unchanged(self):
        from sphinxcontrib.test_reports.junitparser import JUnitParser

        parser = JUnitParser(xml_no_properties_path)
        results = parser.parse()

        tc = results[0]["testcases"][0]
        assert tc["name"] == "ASuccessfulTest"
        assert tc["classname"] == "foo1"
        assert tc["result"] == "passed"

    def test_existing_failure_testcase_unchanged(self):
        from sphinxcontrib.test_reports.junitparser import JUnitParser

        parser = JUnitParser(xml_no_properties_path)
        results = parser.parse()

        tc = results[0]["testcases"][2]
        assert tc["name"] == "AFailingTest"
        assert tc["result"] == "failure"
        assert tc["text"] == " details about failure "


# ---------------------------------------------------------------------------
# Integration tests: Sphinx build with properties linking
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/properties_linking"}],
    indirect=True,
)
class TestPropertiesLinkingIntegration:
    """Full Sphinx build that uses JUnit properties for sphinx-needs linking."""

    def test_build_succeeds(self, test_app):
        app = test_app
        app.build()
        assert app.statuscode == 0

    def test_html_contains_test_cases(self, test_app):
        app = test_app
        app.build()
        html = Path(app.outdir, "index.html").read_text(encoding="utf-8")

        # Test case names from the XML should appear in the output
        assert "test_login_valid" in html
        assert "test_login_invalid" in html
        assert "test_get_users" in html

    def test_verifies_field_rendered(self, test_app):
        """The 'verifies' property should appear as a sphinx-needs field value."""
        app = test_app
        app.build()
        html = Path(app.outdir, "index.html").read_text(encoding="utf-8")

        # The verifies values should be rendered somewhere in the output
        assert "REQ_AUTH_001" in html
        assert "REQ_AUTH_003" in html
        assert "REQ_API_010" in html

    def test_links_created_from_properties(self, test_app):
        """tr_property_link_types should create sphinx-needs links to requirement needs."""
        from bs4 import BeautifulSoup

        app = test_app
        app.build()
        html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")

        # Find links to requirement needs -- sphinx-needs renders outgoing links
        # as anchor tags with the target need ID
        req_links = soup.find_all("a", string=lambda s: s and s.startswith("REQ_"))
        req_link_texts = [a.get_text(strip=True) for a in req_links]

        # Test cases with verifies property should link to requirement needs
        assert "REQ_AUTH_001" in req_link_texts
        assert "REQ_AUTH_002" in req_link_texts
        assert "REQ_AUTH_003" in req_link_texts
        assert "REQ_API_010" in req_link_texts
        assert "REQ_API_011" in req_link_texts
        assert "REQ_API_012" in req_link_texts

    def test_requirement_needs_present(self, test_app):
        """Requirement needs defined in RST should be rendered."""
        app = test_app
        app.build()
        html = Path(app.outdir, "index.html").read_text(encoding="utf-8")

        assert "Authentication Login" in html
        assert "API Get Users" in html

    def test_testcases_without_properties_still_render(self, test_app):
        """Test cases that have no properties should render without errors."""
        app = test_app
        app.build()
        html = Path(app.outdir, "index.html").read_text(encoding="utf-8")

        # test_logout has a failure but no properties
        assert "test_logout" in html
        # test_create_user has no properties and no failure
        assert "test_create_user" in html

    def test_priority_field_rendered(self, test_app):
        """Non-link properties should be surfaced as sphinx-needs fields."""
        app = test_app
        app.build()
        html = Path(app.outdir, "index.html").read_text(encoding="utf-8")

        # The priority property from test_login_valid should appear
        assert "high" in html

    def test_category_field_rendered(self, test_app):
        """The category property from test_get_users should appear."""
        app = test_app
        app.build()
        html = Path(app.outdir, "index.html").read_text(encoding="utf-8")

        assert "integration" in html


# ---------------------------------------------------------------------------
# Parser: empty <properties> element (no <property> children)
# ---------------------------------------------------------------------------


class TestParserHandlesEmptyProperties:
    """JUnitParser must not crash on empty <properties/> elements."""

    def test_empty_testsuite_properties_element(self):
        from sphinxcontrib.test_reports.junitparser import JUnitParser

        parser = JUnitParser(xml_empty_properties_path)
        results = parser.parse()

        suite = results[0]
        assert suite["name"] == "empty_props_suite"
        assert suite["properties"] == {}

    def test_empty_testcase_properties_element(self):
        from sphinxcontrib.test_reports.junitparser import JUnitParser

        parser = JUnitParser(xml_empty_properties_path)
        results = parser.parse()

        tc = results[0]["testcases"][0]
        assert tc["name"] == "test_with_empty_properties"
        assert tc["properties"] == {}

    def test_testcase_without_properties_alongside_empty(self):
        from sphinxcontrib.test_reports.junitparser import JUnitParser

        parser = JUnitParser(xml_empty_properties_path)
        results = parser.parse()

        tc = results[0]["testcases"][1]
        assert tc["name"] == "test_without_properties_element"
        assert tc["properties"] == {}


# ---------------------------------------------------------------------------
# Integration: precise DOM assertions for property fields
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/properties_linking"}],
    indirect=True,
)
class TestPropertyFieldsDomRendering:
    """Verify property values are rendered as sphinx-needs fields using DOM checks."""

    def test_priority_field_in_needs_data_span(self, test_app):
        """The 'priority' property must appear inside a needs_data span."""
        from bs4 import BeautifulSoup

        app = test_app
        app.build()
        html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")

        priority_spans = soup.select("span.needs_priority span.needs_data")
        priority_values = [s.get_text(strip=True) for s in priority_spans]
        assert "high" in priority_values

    def test_category_field_in_needs_data_span(self, test_app):
        """The 'category' property must appear inside a needs_data span."""
        from bs4 import BeautifulSoup

        app = test_app
        app.build()
        html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")

        category_spans = soup.select("span.needs_category span.needs_data")
        category_values = [s.get_text(strip=True) for s in category_spans]
        assert "integration" in category_values

    def test_verifies_field_in_needs_data_span(self, test_app):
        """The 'verifies' property must appear inside a needs_data span."""
        from bs4 import BeautifulSoup

        app = test_app
        app.build()
        html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")

        verifies_spans = soup.select("span.needs_verifies span.needs_data")
        verifies_values = [s.get_text(strip=True) for s in verifies_spans]
        # test_login_valid has verifies="REQ_AUTH_001,REQ_AUTH_002"
        assert any("REQ_AUTH_001" in v for v in verifies_values)
        assert any("REQ_AUTH_002" in v for v in verifies_values)


# ---------------------------------------------------------------------------
# Integration: XML without any properties still builds successfully
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/basic_doc"}],
    indirect=True,
)
class TestNoPropertiesStillWorks:
    """Sphinx build with JUnit XML that has no <properties> must still succeed."""

    def test_build_succeeds_without_properties(self, test_app):
        app = test_app
        app.build()
        assert app.statuscode == 0

    def test_testcases_rendered_without_properties(self, test_app):
        app = test_app
        app.build()
        html = Path(app.outdir, "index.html").read_text(encoding="utf-8")

        # The existing XML fixture (xml_data.xml) has these test case names
        assert "ASuccessfulTest" in html
        assert "AFailingTest" in html
