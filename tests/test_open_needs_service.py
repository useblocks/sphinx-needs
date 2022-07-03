from pathlib import Path

import pytest

from sphinx_needs.services.manager import ServiceManager


@pytest.mark.parametrize(
    "test_app", [{"buildername": "html", "srcdir": "doc_test/docs_open_needs_service"}], indirect=True
)
def test_ons_service(test_app):
    test_app.build()
    assert isinstance(test_app.needs_services, ServiceManager)

    manager = test_app.needs_services
    service = manager.get("open-needs")
    assert hasattr(service, "content")

    assert service.content

    html = Path(test_app.outdir, "index.html").read_text()

    assert "Test rocket power" in html
    assert "ONS_NEP_001" in html
    assert "NEP_002" in html

    assert "done" in html
    assert "Debug data" in html
    assert "Red and blue. No other colors please" in html
    assert "ONS_MARS_REQ_001" not in html
