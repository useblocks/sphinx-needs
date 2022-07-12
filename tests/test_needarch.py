from pathlib import Path

import pytest


@pytest.mark.parametrize("test_app", [{"buildername": "html", "srcdir": "doc_test/doc_needarch"}], indirect=True)
def test_doc_needarch(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text(encoding="utf8")
    assert html


@pytest.mark.parametrize(
    "test_app", [{"buildername": "html", "srcdir": "doc_test/doc_needarch_negative_tests"}], indirect=True
)
def test_doc_needarch_negative(test_app):
    import subprocess

    app = test_app

    srcdir = Path(app.srcdir)
    out_dir = srcdir / "_build"

    out = subprocess.run(["sphinx-build", "-M", "html", srcdir, out_dir], capture_output=True)

    assert out.returncode == 1
    assert (
        "sphinx_needs.directives.needarch.NeedArchException: Directive needarch "
        "can only be used inside a need." in out.stderr.decode("utf-8")
    )
