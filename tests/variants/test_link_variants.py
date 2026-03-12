from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from sphinx.testing.util import SphinxTestApp

from sphinx_needs.api import get_needs_view

CURR_DIR = Path(__file__).parent


@pytest.mark.fixture_file(
    "variants/fixtures/link_variants.yml",
)
def test_link_variants(
    tmpdir: Path,
    content: dict[str, Any],
    make_app: Callable[[], SphinxTestApp],
    write_fixture_files: Callable[[Path, dict[str, Any]], None],
) -> None:
    write_fixture_files(tmpdir, content)

    app: SphinxTestApp = make_app(srcdir=Path(tmpdir), freshenv=True)
    app.build()
    assert app.statuscode == 0

    view = get_needs_view(app)

    expect: dict[str, dict[str, Any]] = content["expect"]
    for need_id, expected_fields in expect.items():
        need = view[need_id]
        for field, expected_value in expected_fields.items():
            actual = need[field]
            if isinstance(expected_value, list):
                actual = list(actual)
            assert actual == expected_value, (
                f"Need {need_id!r} field {field!r}: expected {expected_value}, got {actual}"
            )
    app.cleanup()
