import json
from pathlib import Path

import pytest
from syrupy.filters import props


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/needs_from_toml",
        }
    ],
    indirect=True,
)
def test_needs_from_toml(test_app, snapshot):
    app = test_app
    app.build()
    assert not app._warning.getvalue()
    data = json.loads(Path(app.outdir, "needs.json").read_text("utf8"))
    assert data == snapshot(
        exclude=props("created", "project", "creator", "needs_schema")
    )


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/needs_from_toml",
            "confoverrides": {"needs_reproducible_json": False},
        }
    ],
    indirect=True,
)
def test_needs_from_toml_respects_overrides(test_app):
    app = test_app
    app.build()
    assert not app._warning.getvalue()
    assert app.config.needs_reproducible_json is False


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/needs_from_toml_service_class",
        }
    ],
    indirect=True,
)
def test_needs_from_toml_warns_and_ignores_service_class(test_app):
    app = test_app
    app.build()

    warning = app._warning.getvalue()
    assert "needs_services.foo.class" in warning
    assert "cannot be set in 'needs_from_toml'" in warning
    assert "register the service class in conf.py" in warning
    assert app.config.needs_services["foo"] == {
        "class_init": {},
        "url": "https://example.invalid",
    }
