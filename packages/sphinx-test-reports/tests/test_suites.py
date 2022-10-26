from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/testsuites_doc"}],
    indirect=True,
)
def test_doc_env_report_build_html(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert html

    assert "AnotherTest" in html
    assert "test_Another_getCurrentTime" in html

    assert "TimerCounterImplTest" in html
    assert "CheckTimerFunction_Init" in html

    assert "TimerTest" in html
    assert "test_Timer_getdT" in html
