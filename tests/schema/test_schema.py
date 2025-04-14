import re
from pathlib import Path

import pytest
import sphinx
from sphinx.testing.util import SphinxTestApp

CURR_DIR = Path(__file__).parent


def rm_ansi_escapes(text: str) -> str:
    """
    Remove ANSI escape sequences from a string.
    """
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", text)


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_schema", "no_plantuml": True}],
    indirect=True,
)
def test_schema_basic(test_app: SphinxTestApp) -> None:
    test_app.builder.build_all()

    warnings_raw = rm_ansi_escapes(test_app.warning.getvalue())
    warnings = [part for part in warnings_raw.split("WARNING: ") if part]

    expected_warnings = [
        (
            "'FEAt' does not match '^[A-Z0-9_]+$'",
            "[sn_schema.validation_fail]",
        ),
        (
            "1 invalid links of type 'links' / nok: FEAT",
            "[sn_schema.unevaluated_additional_links]",
        ),
        (
            "Too few valid links of type 'links' (0 < 1) / nok: REQ_SAFE_UNSAFE_FEAT",
            "[sn_schema.too_few_links]",
        ),
        (
            "1 invalid links of type 'links' / nok: REQ_SAFE_UNSAFE_FEAT",
            "[sn_schema.unevaluated_additional_links]",
        ),
    ]
    for expected in expected_warnings:
        if sphinx.version_info[0] <= 8:
            expected_msg = expected[0]
        else:
            expected_msg = f"{expected[0]} {expected[1]}"
        assert any(expected_msg in warning for warning in warnings), (
            f"Expected warning not found: {expected}"
        )
    assert len(warnings) == len(expected_warnings)
    unexpected_warnings = [
        '"approved" is a required property [sn_schema.validation_fail]',  # severity info too low
    ]
    for unexpected in unexpected_warnings:
        assert all(unexpected not in warning for warning in warnings), (
            f"Unexpected warning found: {unexpected}"
        )

    html = Path(test_app.outdir, "index.html").read_text()
    assert html
