import os
import re
from pathlib import Path

import pytest
import responses

from tests.test_basic_doc import random_data_callback


@responses.activate
@pytest.mark.parametrize("test_app", [{"buildername": "html", "srcdir": "../docs"}], indirect=True)
def test_official(test_app, benchmark):
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
