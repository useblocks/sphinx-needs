"""``test-env``'s failures are located, typed warnings; its lists and cells say what the file says.

#2141: the file was opened in the locale's encoding with no BOM handling, so a UTF-8 file
with a byte-order mark ended the build (``InvalidJsonFile``, a ``BaseException``), as did
any file that is not JSON. #2052: a file whose JSON is not an object of objects crashed
with a ``TypeError`` / ``IndexError`` from wherever the walk first indexed it. #2140: the
``:env:`` / ``:data:`` lists were tested for emptiness before stripping, a repeated
``:data:`` key was consumed by its first use and then reported missing, a missing key was
reported once per ENVIRONMENT, and no warning carried a location. #2139: a scalar cell was
``str()`` of the value, and every falsy value an empty cell.

Every warning here is pinned located (``index.rst:4:``, the directive's line) and typed
(``suppress_warnings`` naming its subtype empties the stream); the
``[test_reports.<subtype>]`` suffix is not asserted (Sphinx < 8 does not print it).
Files are written as bytes.
"""

import json
from pathlib import Path

import pytest
from docutils import nodes

from sphinx_test_reports.directives.test_env import (
    InvalidEnvRequested,
    InvalidJsonFile,
    JsonFileNotFound,
)

TOX = (Path(__file__).parent / "doc_test" / "utils" / "tox-report.json").read_bytes()
#: The environments of ``TOX``, in file order.
TOX_ENVS = ["flake8", "py35", "pylint"]


def _with_key(key: str, holders: list[str]) -> bytes:
    """``TOX`` with ``key`` added to the environments in ``holders`` only."""
    report = json.loads(TOX)
    for name in holders:
        report[name][key] = "value"
    return json.dumps(report).encode("utf-8")


def _error_boxes(app) -> list[str]:
    return [box.astext() for box in app.env.get_doctree("index").findall(nodes.error)]


def _sections(app) -> list[str]:
    """The titles of the sections ``test-env`` generated (below the page's own)."""
    doctree = app.env.get_doctree("index")
    return [
        section[0].astext()
        for section in doctree.findall(nodes.section)
        if section.parent is not doctree
    ]


def _rows(app) -> list[list[str]]:
    """Every table row's cell texts (the ``Variable`` / ``Data`` header included)."""
    doctree = app.env.get_doctree("index")
    return [
        [entry.astext() for entry in row.findall(nodes.entry)]
        for row in doctree.findall(nodes.row)
    ]


def _src(app, name: str) -> str:
    return str(Path(app.srcdir, name))


# --- E1: reading the file (#2141) --------------------------------------------------------


def test_a_utf8_file_with_a_byte_order_mark_renders_like_one_without(build_page):
    """Master: ``InvalidJsonFile: The given file t.json is not a valid JSON``, rc 1."""
    app, stream = build_page(
        ".. test-env:: plain.json\n\n.. test-env:: bom.json\n",
        files={"plain.json": TOX, "bom.json": b"\xef\xbb\xbf" + TOX},
    )

    assert stream == ""
    rows = _rows(app)
    assert rows[: len(rows) // 2] == rows[len(rows) // 2 :]
    assert _sections(app) == TOX_ENVS * 2


def test_a_file_that_is_not_utf8_is_unreadable(build_page):
    app, stream = build_page(
        ".. test-env:: latin1.json\n", files={"latin1.json": b'{"e": {"k": "caf\xe9"}}'}
    )

    message = (
        f"{_src(app, 'latin1.json')} is not valid UTF-8 "
        "(invalid continuation byte at byte 16)"
    )
    assert app.statuscode == 0
    assert f"index.rst:4: WARNING: {message}" in stream
    assert _error_boxes(app) == [message]
    assert _sections(app) == []


def test_a_file_that_is_not_json_is_unreadable(build_page):
    """Master: ``InvalidJsonFile: The given file bad.json is not a valid JSON``."""
    app, stream = build_page(".. test-env:: bad.json\n", files={"bad.json": b'{"a": '})

    message = f"{_src(app, 'bad.json')} (line 1, column 7): Expecting value"
    assert app.statuscode == 0
    assert f"index.rst:4: WARNING: {message}" in stream
    assert _error_boxes(app) == [message]


def test_a_missing_file_is_report_missing(build_page):
    """Master: ``JsonFileNotFound: The given file does not exist: …``, rc 1."""
    app, stream = build_page(".. test-env:: nope.json\n")

    message = f"Test file not found: {_src(app, 'nope.json')}"
    assert app.statuscode == 0
    assert f"index.rst:4: WARNING: {message}" in stream
    assert _error_boxes(app) == [message]


@pytest.mark.parametrize(
    "report", [b'{"e": {"k": "caf\xe9"}}', b'{"a": '], ids=["latin1", "not-json"]
)
def test_the_unreadable_file_warning_is_typed(build_page, report):
    app, stream = build_page(
        ".. test-env:: e.json\n",
        files={"e.json": report},
        confoverrides={"suppress_warnings": ["test_reports.report_unreadable"]},
    )

    assert stream == ""
    assert len(_error_boxes(app)) == 1


# --- E2: the shape (#2052) ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("body", "kind"),
    [("[]", "an array"), ('["x"]', "an array"), ('"s"', "a string"), ("3", "a number")],
    ids=["empty-array", "array", "string", "number"],
)
@pytest.mark.parametrize("options", ["", "   :raw:\n", "   :raw:\n   :data: k\n"])
def test_a_file_that_is_not_an_object_renders_nothing(build_page, body, kind, options):
    """Master: ``TypeError: list indices must be integers or slices, not str`` /
    ``string indices must be integers, not 'str'`` / ``'int' object is not iterable``
    (rc 2), and ``[]`` rendered nothing without a word."""
    app, stream = build_page(
        ".. test-env:: e.json\n" + options, files={"e.json": body.encode()}
    )

    message = (
        f"{_src(app, 'e.json')}: the file is not a JSON object of environments "
        f"(got {kind})"
    )
    assert app.statuscode == 0
    assert f"index.rst:4: WARNING: {message}" in stream
    assert stream.count("WARNING:") == 1
    assert _error_boxes(app) == [message]
    assert _sections(app) == []


@pytest.mark.parametrize(
    ("value", "kind"),
    [("[]", "an array"), ('"s"', "a string"), ("3", "a number"), ("null", "null")],
    ids=["array", "string", "number", "null"],
)
@pytest.mark.parametrize(
    "options",
    [
        "",
        "   :raw:\n   :data: k\n",
        "   :env: a, b\n",
        "   :raw:\n   :env: a, b\n   :data: k\n",
    ],
    ids=["table", "raw-data", "table-env", "raw-env-data"],
)
def test_an_environment_that_is_not_an_object_is_skipped(
    build_page, value, kind, options
):
    """Master, ``"s"`` in the table: ``TypeError: string indices must be integers, not
    'str'``; ``null`` under ``:raw:`` + ``:data:``: ``TypeError: 'NoneType' object is not
    iterable``. The other environment is rendered either way. (``:raw:`` without
    ``:data:`` renders the value instead -- the next test.)"""
    app, stream = build_page(
        ".. test-env:: e.json\n" + options,
        files={"e.json": f'{{"a": {value}, "b": {{"k": "v"}}}}'.encode()},
    )

    message = f"environment 'a' is not a JSON object (got {kind}); skipped"
    assert app.statuscode == 0
    assert f"index.rst:4: WARNING: {message}" in stream
    assert stream.count("WARNING:") == 1
    assert _sections(app) == ["b"]
    assert _error_boxes(app) == []


@pytest.mark.parametrize("value", ["[]", '"s"', "3", "null"])
@pytest.mark.parametrize(
    "options", ["   :raw:\n", "   :raw:\n   :env: a, b\n"], ids=["raw", "raw-env"]
)
def test_under_raw_without_data_a_non_object_environment_is_shown(
    build_page, value, options
):
    """Fix round 1, F8b: ``:raw:`` without ``:data:`` shows a non-object environment's
    value as its JSON block, without a warning -- master did so (it did not crash
    there), and ubCode keeps that rendering (``render_env``). Every other branch skips
    it with ``env_shape`` (the test above)."""
    app, stream = build_page(
        ".. test-env:: e.json\n" + options,
        files={"e.json": f'{{"a": {value}, "b": {{"k": "v"}}}}'.encode()},
    )

    assert stream == ""
    assert _sections(app) == ["a", "b"]
    blocks = [
        block.astext()
        for block in app.env.get_doctree("index").findall(nodes.literal_block)
    ]
    assert blocks == [json.dumps(json.loads(value), indent=4), '{\n    "k": "v"\n}']


def test_under_raw_with_an_empty_data_a_non_object_environment_is_skipped(build_page):
    """Fix round 2, V1-F8c: ``:data: ,`` names no variable but IS a ``:data:`` -- the
    ``:raw:`` exception above does not apply (ubCode: ``Some([])`` is not ``None``). The
    object environment shows no variable, the other is skipped with ``env_shape``;
    extending the exception to an empty ``:data:`` would reach ``.items()`` on ``3``."""
    app, stream = build_page(
        ".. test-env:: e.json\n   :raw:\n   :data: ,\n",
        files={"e.json": b'{"a": {"k": 1}, "b": 3}'},
    )

    assert app.statuscode == 0
    assert stream.count("WARNING:") == 1
    assert (
        "index.rst:4: WARNING: environment 'b' is not a JSON object (got a number); "
        "skipped"
    ) in stream
    assert _sections(app) == ["a"]
    blocks = [
        block.astext()
        for block in app.env.get_doctree("index").findall(nodes.literal_block)
    ]
    assert blocks == ["{}"]


def test_the_shape_warning_is_typed(build_page):
    _, stream = build_page(
        ".. test-env:: e.json\n",
        files={"e.json": b'{"a": null, "b": {"k": "v"}}'},
        confoverrides={"suppress_warnings": ["test_reports.env_shape"]},
    )

    assert stream == ""


# --- E3: the lists (#2140 items 1-2) ------------------------------------------------------


def test_a_blank_env_element_is_dropped(build_page):
    """Master: ``environment '' is not present in JSON file``."""
    app, stream = build_page(
        ".. test-env:: t.json\n   :env: py35, ,flake8\n", files={"t.json": TOX}
    )

    assert stream == ""
    assert _sections(app) == ["py35", "flake8"]


def test_a_blank_data_element_is_dropped(build_page):
    """Master: ``option '' is not present in JSON file`` three times."""
    app, stream = build_page(
        ".. test-env:: t.json\n   :data: host,, ,name\n", files={"t.json": TOX}
    )

    assert stream == ""
    assert [row[0] for row in _rows(app)] == ["Variable", "host", "name"] * 3


def test_a_repeated_data_key_is_one_row_and_no_warning(build_page):
    """Master: one ``host`` row, then ``option 'host' is not present in JSON file`` three
    times -- the first use consumed the key."""
    app, stream = build_page(
        ".. test-env:: t.json\n   :data: host, host\n", files={"t.json": TOX}
    )

    assert stream == ""
    assert [row[0] for row in _rows(app)] == ["Variable", "host"] * 3


def test_a_repeated_env_is_one_section(build_page):
    """Master: two ``py35`` sections (the second with the id ``id1``)."""
    app, stream = build_page(
        ".. test-env:: t.json\n   :env: py35, py35\n", files={"t.json": TOX}
    )

    assert stream == ""
    assert _sections(app) == ["py35"]


def test_a_data_value_with_no_key_shows_no_variable(build_page):
    """``:data: ,`` names no variable, so none is shown -- as on master and in ubCode, and
    as ``:env: ,`` shows no environment (fix round 1, F8a; this row asserted every
    variable before)."""
    app, stream = build_page(
        ".. test-env:: t.json\n   :data: ,\n", files={"t.json": TOX}
    )

    assert stream == ""
    assert _sections(app) == TOX_ENVS
    assert _rows(app) == [["Variable", "Data"]] * 3


def test_an_env_value_with_no_name_shows_nothing(build_page):
    """``:env: ,`` names no environment: nothing is shown, and nothing is warned."""
    app, stream = build_page(
        ".. test-env:: t.json\n   :env: ,\n", files={"t.json": TOX}
    )

    assert stream == ""
    assert _sections(app) == []


def test_a_repeated_env_keeps_its_first_position(build_page):
    app, stream = build_page(
        ".. test-env:: t.json\n   :env: py35, flake8, py35\n", files={"t.json": TOX}
    )

    assert stream == ""
    assert _sections(app) == ["py35", "flake8"]


def test_a_repeated_data_key_keeps_its_first_position(build_page):
    """The missing-key warnings come in ``:data:`` order, a repeat at its first place."""
    _, stream = build_page(
        ".. test-env:: t.json\n   :raw:\n   :data: nope2, nope1, nope2\n",
        files={"t.json": TOX},
    )

    assert stream.count("WARNING:") == 2
    assert stream.index("'nope2'") < stream.index("'nope1'")


# --- E4: the warnings (#2140 items 3-4) ---------------------------------------------------


@pytest.mark.parametrize("raw", ["", "   :raw:\n"], ids=["table", "raw"])
def test_a_key_no_environment_holds_warns_once(build_page, raw):
    """Master: ``option 'nope' is not present in JSON file`` three times, unlocated."""
    _, stream = build_page(
        ".. test-env:: t.json\n" + raw + "   :data: host, nope\n", files={"t.json": TOX}
    )

    assert stream.count("WARNING:") == 1
    assert "index.rst:4: WARNING: option 'nope' is not present in JSON file" in stream


@pytest.mark.parametrize("raw", ["", "   :raw:\n"], ids=["table", "raw"])
@pytest.mark.parametrize(
    ("holders", "lacking"),
    [(["py35", "pylint"], "flake8"), (["py35"], "flake8, pylint")],
    ids=["one-lacks", "two-lack"],
)
def test_a_key_some_environments_lack_names_them_once(
    build_page, raw, holders, lacking
):
    """Master: ``option 'x' is not present in JSON file`` once per lacking environment,
    naming none (the ``:raw:`` + ``:env:`` branch alone named it, once per environment)."""
    _, stream = build_page(
        ".. test-env:: t.json\n" + raw + "   :data: host, x\n",
        files={"t.json": _with_key("x", holders)},
    )

    assert stream.count("WARNING:") == 1
    assert (
        f"index.rst:4: WARNING: option 'x' is not present in '{lacking}' environment file"
        in stream
    )


def test_an_env_the_file_lacks_warns_located(build_page):
    """Master: ``WARNING: environment 'nope' is not present in JSON file`` -- no
    ``docname:line``."""
    app, stream = build_page(
        ".. test-env:: t.json\n   :env: py35, nope\n", files={"t.json": TOX}
    )

    assert stream.count("WARNING:") == 1
    assert (
        "index.rst:4: WARNING: environment 'nope' is not present in JSON file" in stream
    )
    assert _sections(app) == ["py35"]


@pytest.mark.parametrize(
    ("options", "subtype"),
    [
        ("   :data: host, nope\n", "env_key_not_present"),
        ("   :env: nope\n", "env_not_present"),
    ],
    ids=["key", "env"],
)
def test_the_selection_warnings_are_typed(build_page, options, subtype):
    _, stream = build_page(
        ".. test-env:: t.json\n" + options,
        files={"t.json": TOX},
        confoverrides={"suppress_warnings": [f"test_reports.{subtype}"]},
    )

    assert stream == ""


# --- E5: scalars (#2139) ------------------------------------------------------------------


def test_scalar_cells_are_spelled_as_json(build_page):
    """Master: ``True``, an empty cell for ``false`` / ``null`` / ``0`` / ``0.0`` / ``""``,
    and ``"True"`` indistinguishable from ``true``."""
    report = (
        b'{"e": {"t": true, "f": false, "n": null, "z": 0, "zf": 0.0, "i": 3, '
        b'"fl": 1.5, "two": 2.0, "big": 1e16, "es": "", "sT": "True"}}'
    )
    app, stream = build_page(".. test-env:: s.json\n", files={"s.json": report})

    assert stream == ""
    assert _rows(app)[1:] == [
        ["t", "true"],
        ["f", "false"],
        ["n", "null"],
        ["z", "0"],
        ["zf", "0.0"],
        ["i", "3"],
        ["fl", "1.5"],
        ["two", "2.0"],
        ["big", "1e+16"],
        ["es", ""],
        ["sT", "True"],
    ]


def test_a_non_ascii_string_cell_is_shown_as_written(build_page):
    app, stream = build_page(
        ".. test-env:: s.json\n", files={"s.json": '{"e": {"k": "café"}}'.encode()}
    )

    assert stream == ""
    assert _rows(app)[1:] == [["k", "café"]]


# --- E6: the exception classes ------------------------------------------------------------


@pytest.mark.parametrize(
    "cls", [InvalidJsonFile, JsonFileNotFound, InvalidEnvRequested]
)
def test_the_env_exception_classes_are_ordinary_exceptions(cls):
    """Kept (public), no longer raised by the directive, and catchable as ``Exception``."""
    assert issubclass(cls, Exception)


def test_a_test_env_in_an_included_file_is_located_there(build_page):
    """Fix round 1, F2: located in the file the directive is written in."""
    app, stream = build_page(
        "x\n\ny\n\n.. include:: part.rst\n",
        files={"part.rst": b"Part\n----\n\nText.\n\n.. test-env:: nope.json\n"},
        confoverrides={"exclude_patterns": ["part.rst"]},
    )

    # One form for both sides: the stream names the file as docutils resolved the
    # include, which on Windows is a forward-slash path (`C:/…/src/part.rst`).
    expected = f"{_src(app, 'part.rst')}:6: WARNING: Test file not found: "
    assert expected.replace("\\", "/") in stream.replace("\\", "/")
    assert "index.rst:" not in stream
