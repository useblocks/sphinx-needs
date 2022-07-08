from pathlib import Path

import pytest
import requests

from sphinx_needs.services.manager import ServiceManager


class MockGetResponse:
    def __init__(self):
        self.status_code = 200
        self.url = "http://127.0.0.1:9595/"
        self.text = "Mocked Get Response"

    @staticmethod
    def json():
        return [
            {
                "key": "NEP_001",
                "type": "Requirement",
                "title": "Build rocket",
                "description": "We finally need to build our Neptune3000 rocket.",
                "format": "txt",
                "project_id": 1,
                "options": {"status": "done", "priority": "high", "costs": 3500000, "approved": 1},
                "references": {},
            },
            {
                "key": "NEP_002",
                "type": "Requirement",
                "title": "Test rocket power",
                "description": "Lets test the rocket on a test bench",
                "format": "txt",
                "project_id": 1,
                "options": {"status": "open", "priority": "high", "costs": 500000, "approved": 0},
                "references": {},
            },
            {
                "key": "NEP_003",
                "type": "Requirement",
                "title": "Rocket painting",
                "description": "Red and blue. No other colors please.",
                "format": "txt",
                "project_id": 1,
                "options": {"status": "open", "priority": "low", "costs": 20000, "approved": 1},
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


class MockPostResponse:
    def __init__(self):
        self.status_code = 200
        self.url = "http://127.0.0.1:9595/"
        self.text = "Mocked Post Response"

    @staticmethod
    def json():
        return {"access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9", "token_type": "bearer"}


@pytest.mark.parametrize(
    "test_app", [{"buildername": "html", "srcdir": "doc_test/doc_open_needs_service"}], indirect=True
)
def test_ons_service(test_app, monkeypatch):
    def mock_get(*args, **kwargs):
        return MockGetResponse()

    def mock_post(*args, **kwargs):
        return MockPostResponse()

    # apply the monkeypatch for requests.get to mock_get
    monkeypatch.setattr(requests, "get", mock_get)
    # apply the monkeypatch for requests.post to mock_post
    monkeypatch.setattr(requests, "post", mock_post)

    test_app.build()
    assert isinstance(test_app.needs_services, ServiceManager)

    manager = test_app.needs_services
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
