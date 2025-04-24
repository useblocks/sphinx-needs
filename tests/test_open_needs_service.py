from pathlib import Path

import pytest
import responses

from sphinx_needs.services.manager import ServiceManager

MOCK_NEEDS = [
    {
        "key": "NEP_001",
        "type": "Requirement",
        "title": "Build rocket",
        "description": "We finally need to build our Neptune3000 rocket.",
        "format": "txt",
        "project_id": 1,
        "options": {
            "status": "done",
            "priority": "high",
            "costs": 3500000,
            "approved": 1,
        },
        "references": {},
    },
    {
        "key": "NEP_002",
        "type": "Requirement",
        "title": "Test rocket power",
        "description": "Lets test the rocket on a test bench",
        "format": "txt",
        "project_id": 1,
        "options": {
            "status": "open",
            "priority": "high",
            "costs": 500000,
            "approved": 0,
        },
        "references": {},
    },
    {
        "key": "NEP_003",
        "type": "Requirement",
        "title": "Rocket painting",
        "description": "Red and blue. No other colors please.",
        "format": "txt",
        "project_id": 1,
        "options": {
            "status": "open",
            "priority": "low",
            "costs": 20000,
            "approved": 1,
        },
        "references": {"links": ["NEP_001", "NEP_002"]},
    },
    {
        "key": "NEP_004",
        "type": "Requirement",
        "title": "Pumps from company AwesomePumps",
        "description": "We simply reuse the pump system ABC-Pumps from AwesomePumps Inc.",
        "format": "txt",
        "project_id": 1,
        "options": {"status": "open", "links": "req_1"},
        "references": {"links": ["NEP_003"]},
    },
]


@responses.activate
@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_open_needs_service"}],
    indirect=True,
)
def test_ons_service(test_app):
    responses.post(
        "http://127.0.0.1:9595/auth/jwt/login",
        status=200,
        json={
            "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9",
            "token_type": "bearer",
        },
    )
    responses.get(
        "http://127.0.0.1:9595/api/needs/?skip=0&limit=2",
        status=200,
        json=MOCK_NEEDS[:2],
    )
    responses.get(
        "http://127.0.0.1:9595/api/needs/?skip=0&limit=4",
        status=200,
        json=MOCK_NEEDS[:],
    )

    test_app.build()
    assert isinstance(test_app._needs_services, ServiceManager)

    manager = test_app._needs_services
    service = manager.get("open-needs")
    assert hasattr(service, "content")

    assert service.content

    html = Path(test_app.outdir, "index.html").read_text()

    assert "Test rocket power" in html
    assert "ONS_TEST_NEP_004" in html
    assert "NEP_003" in html

    assert "open" in html
    assert "Debug data" in html
    assert "Red and blue. No other colors please" in html
    assert "ONS_TEST_MARS_REQ_001" not in html
