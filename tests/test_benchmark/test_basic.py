import os
import re
import time
from pathlib import Path

import pytest
import responses

from tests.test_basic_doc import random_data_callback


@responses.activate
@pytest.mark.parametrize("test_app", [{"buildername": "html", "srcdir": "doc_test/doc_basic"}], indirect=True)
def test_benchmark_build_html(test_app, benchmark):
    responses.add_callback(
        responses.GET,
        re.compile(r"https://api.github.com/.*"),
        callback=random_data_callback,
        content_type="application/json",
    )
    responses.add(responses.GET, re.compile(r"https://avatars.githubusercontent.com/.*"), body="")

    app = test_app
    benchmark.pedantic(app.builder.build_all, rounds=1, iterations=1)

    # Check if static files got copied correctly.
    build_dir = Path(app.outdir) / "_static" / "sphinx-needs" / "libs" / "html"
    files = [f for f in build_dir.glob("**/*") if f.is_file()]
    assert build_dir / "sphinx_needs_collapse.js" in files
    assert build_dir / "datatables_loader.js" in files
    assert build_dir / "DataTables-1.10.16" / "js" / "jquery.dataTables.min.js" in files

    time.sleep(5)  # Just a test, remove it!


@responses.activate
@pytest.mark.parametrize("test_app", [{"buildername": "html", "srcdir": "../docs"}], indirect=True)
def test_benchmark_official_docs(test_app, benchmark):
    responses.add_callback(
        responses.GET,
        re.compile(r"https://api.github.com/.*"),
        callback=random_data_callback,
        content_type="application/json",
    )
    responses.add(responses.GET, re.compile(r"https://avatars.githubusercontent.com/.*"), body="")

    os.environ["ON_CI"] = "true"
    os.environ["FAST_BUILD"] = "true"

    app = test_app
    benchmark.pedantic(app.builder.build_all, rounds=1, iterations=1)

    # Check if static files got copied correctly.
    build_dir = Path(app.outdir) / "_static" / "sphinx-needs" / "libs" / "html"
    files = [f for f in build_dir.glob("**/*") if f.is_file()]
    assert build_dir / "sphinx_needs_collapse.js" in files
