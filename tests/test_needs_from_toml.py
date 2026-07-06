import json
from pathlib import Path

import pytest
from syrupy.filters import props


def _remove_json_paths(data):
    """Remove json_path from external_sources to avoid platform-specific path differences."""
    if isinstance(data, dict):
        if "versions" in data:
            for version_data in data["versions"].values():
                if "external_sources" in version_data:
                    for source in version_data["external_sources"]:
                        source.pop("json_path", None)
        return {k: _remove_json_paths(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_remove_json_paths(item) for item in data]
    return data


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/needs_from_toml",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_needs_from_toml(test_app, snapshot):
    app = test_app
    app.build()
    assert not app._warning.getvalue()
    data = json.loads(Path(app.outdir, "needs.json").read_text("utf8"))
    # Remove json_path from external_sources as it contains platform-specific absolute paths
    data = _remove_json_paths(data)
    assert data == snapshot(
        exclude=props("created", "project", "creator", "needs_schema")
    )


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/needs_from_toml",
            "no_plantuml": True,
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
