import os.path
from pathlib import Path

import pytest


@pytest.mark.parametrize("test_app", [{"buildername": "html", "srcdir": "doc_test/doc_needextract"}], indirect=True)
def test_needextract_filter_options(test_app):
    import subprocess

    app = test_app

    srcdir = Path(app.srcdir)
    out_dir = srcdir / "_build"

    out = subprocess.run(["sphinx-build", "-M", "html", srcdir, out_dir], capture_output=True)
    assert out.returncode == 0


@pytest.mark.parametrize("test_app", [{"buildername": "html", "srcdir": "doc_test/doc_needextract"}], indirect=True)
def test_needextract_basic_run(test_app):
    app = test_app
    app.build()

    from lxml import html as html_parser

    def run_checks(checks, html_path):
        html_path = str(Path(app.outdir, html_path))
        tree = html_parser.parse(html_path)
        for check in checks:
            img_src = tree.xpath(f"//table[@id='{check[0]}']//td[@class='need content']//img/@src")[0]
            assert img_src == check[1]
            assert os.path.exists(str(Path(app.outdir, os.path.dirname(html_path), img_src)))

    checks = [
        ("US_SUB_001", "_images/smile.png"),
        ("US_SUB_002", "_images/smile.png"),
        ("US_SUB_003", "_images/smile1.png"),
        ("US_SUB_004", "_images/smile1.png"),
        ("US_SUB_005", "_images/smile1.png"),
        ("US_SUB_005", "_images/smile1.png"),
        ("US_002", "_images/smile.png"),
        ("US_003", "_images/smile.png"),
    ]
    run_checks(checks, "check_images.html")

    checks = [
        ("US_002", "../_images/smile.png"),
        ("US_003", "../_images/smile.png"),
    ]
    run_checks(checks, "subfolder/check_images_2.html")

    index_html = Path(app.outdir, "check_need_refs.html").read_text()
    assert "Awesome Sphinx-Needs" in index_html
