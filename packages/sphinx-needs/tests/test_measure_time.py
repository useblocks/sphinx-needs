from pathlib import Path

import pytest

from tests.conftest import build_warnings


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_measure_time"}],
    indirect=True,
)
def test_measure_time(test_app):
    app = test_app
    app.build()
    warning_records = build_warnings(app)
    assert warning_records == [
        "<srcdir>/index.rst:49: WARNING: The 'export_id' option is deprecated, instead use the `needs_debug_filters` configuration. [needs.deprecated]"
    ]
    outdir = Path(str(app.outdir))
    assert outdir.joinpath("debug_measurement.json").exists()
    assert outdir.joinpath("debug_filters.jsonl").exists()
