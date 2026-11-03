import contextlib
import json
import re
import sys
import uuid
from pathlib import Path
from random import randrange

import pytest
import responses

from sphinx_needs_testkit import make_plantuml_inert
from tests.benchmarks._builds import time_html_builds, unfenced
from tests.data.service_github import (
    GITHUB_ISSUE_SEARCH_ANSWER,
    GITHUB_SEARCH_COMMIT_ANSWER,
    GITHUB_SPECIFIC_COMMIT_ANSWER,
    GITHUB_SPECIFIC_ISSUE_ANSWER,
)

with contextlib.suppress(ImportError):
    # not available for Windows
    import memray


def random_data_callback(request):
    """
    Response data callback, which injects random ids, so that the generated needs get always a unique id and no
    exceptions get thrown.
    """
    if re.match(r"/search/issues", request.path_url):
        data = GITHUB_ISSUE_SEARCH_ANSWER
        data["items"][0]["number"] = randrange(10000)
    elif re.match(r"/.+/issue/.+", request.path_url) or re.match(
        r"/.+/pulls/.+", request.path_url
    ):
        data = GITHUB_SPECIFIC_ISSUE_ANSWER
        data["number"] = randrange(10000)
    elif re.match(r"/search/commits", request.path_url):
        data = GITHUB_SEARCH_COMMIT_ANSWER
        data["number"] = randrange(10000)
    elif re.match(r"/.*/commits/*", request.path_url):
        data = GITHUB_SPECIFIC_COMMIT_ANSWER
        data["sha"] = uuid.uuid4().hex
    else:
        print(request.path_url)
    return 200, [], json.dumps(data)


def _mock_github() -> None:
    responses.add_callback(
        responses.GET,
        re.compile(r"https://api.github.com/.*"),
        callback=random_data_callback,
        content_type="application/json",
    )
    responses.add(
        responses.GET, re.compile(r"https://avatars.githubusercontent.com/.*"), body=""
    )


def _drop_copy_css_file(app) -> None:
    # Okay, that's really ugly.
    # There seems to be a bug in matplotlib for copying css-files when used with "../docs" (relative path!) as
    # app source. I don't know why. But we do not need the function for the test, so it gets removed from the listener.
    for index, listener in enumerate(app.events.listeners["build-finished"]):
        if "_copy_css_file" in listener[1].__name__:
            del app.events.listeners["build-finished"][index]


def _assert_static_files(app) -> None:
    build_dir = Path(app.outdir) / "_static" / "sphinx-needs" / "libs" / "html"
    files = [f for f in build_dir.glob("**/*") if f.is_file()]
    assert build_dir / "sphinx_needs_collapse.js" in files


@responses.activate
@pytest.mark.parametrize(
    "test_app", [{"buildername": "html", "srcdir": "../docs"}], indirect=True
)
def test_official_time(test_app, make_app, benchmark):
    _mock_github()
    # 15-20 s a build once nothing renders; the fastest of three is the number reported
    app = time_html_builds(benchmark, make_app, Path(test_app.srcdir), rounds=3)
    _assert_static_files(app)


@responses.activate
@pytest.mark.parametrize(
    "test_app", [{"buildername": "html", "srcdir": "../docs"}], indirect=True
)
@pytest.mark.skipif(
    sys.platform.startswith("win"), reason="memray not available on Windows"
)
def test_official_memory(test_app, make_app, benchmark):
    """The peak heap of one build, as memray records it, and its flamegraph.

    Unlike a duration, the peak barely depends on the machine, so it is the steadiest
    number this workflow tracks. It travels in the benchmark's ``extra_info``; the
    duration pytest-benchmark records beside it is memray's, and nothing reads it.
    """
    _mock_github()
    with unfenced():
        app = make_app(buildername="html", srcdir=Path(test_app.srcdir), freshenv=True)
    make_plantuml_inert(app)
    _drop_copy_css_file(app)

    mem_path = Path(__file__).parent / ".." / ".." / "mem_out.bin"

    def build() -> None:
        file_dest = memray.FileDestination(mem_path, overwrite=True)
        with memray.Tracker(destination=file_dest):
            app.build()

    benchmark.pedantic(build, rounds=1, iterations=1)
    with memray.FileReader(mem_path) as reader:
        benchmark.extra_info["peak_memory_bytes"] = reader.metadata.peak_memory

    _assert_static_files(app)
