import re
from pathlib import Path

import memray
import pytest
import responses

from tests.test_basic_doc import random_data_callback


@responses.activate
@pytest.mark.parametrize("test_app", [{"buildername": "html", "srcdir": "../docs"}], indirect=True)
def test_official_time(test_app, benchmark):
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


@responses.activate
@pytest.mark.parametrize("test_app", [{"buildername": "html", "srcdir": "../docs", "parallel": 1}], indirect=True)
def test_official_memory(test_app):
    responses.add_callback(
        responses.GET,
        re.compile(r"https://api.github.com/.*"),
        callback=random_data_callback,
        content_type="application/json",
    )
    responses.add(responses.GET, re.compile(r"https://avatars.githubusercontent.com/.*"), body="")

    app = test_app

    # Okay, that's really ugly.
    # There seems to be a bug in matplotlib for copying css-files when used with "../docs" (relative path!) as
    # app source. I don't know why. But we do not need the function for the test, so it gets removed from the listener.
    for index, listener in enumerate(app.events.listeners["build-finished"]):
        if "_copy_css_file" in listener[1].__name__:
            del app.events.listeners["build-finished"][index]

    mem_path = Path(__file__).parent / ".." / ".." / "mem_out.bin"
    file_dest = memray.FileDestination(mem_path, overwrite=True)

    with memray.Tracker(destination=file_dest):
        app.build()

    # Check if static files got copied correctly.
    build_dir = Path(app.outdir) / "_static" / "sphinx-needs" / "libs" / "html"
    files = [f for f in build_dir.glob("**/*") if f.is_file()]
    assert build_dir / "sphinx_needs_collapse.js" in files
