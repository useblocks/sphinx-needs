from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/testsuites_doc"}],
    indirect=True,
)
def test_doc_testsuites_html(test_app):
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

    assert "more_info" in html  # 'tr_extra_options'
    assert "More content inside the new option" in html  # 'tr_extra_options'


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/many_testsuites_doc"}],
    indirect=True,
)
def test_doc_many_testsuites_html(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert html
    assert "TEST_001_FFDBD67" in html  # suite id
    assert "TEST_001_FFDBD67_81152CFAF6" in html  # case id
    assert "more_info" in html  # 'tr_extra_options'
    assert "More content inside the new option" in html  # 'tr_extra_options'
