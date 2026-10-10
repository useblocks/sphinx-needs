"""``build_content``'s literal blocks keep every line of the report's text inside them.

The converter writes a case's failure message, failure text and captured output into
``needs.json``'s ``content`` as indented reStructuredText literal blocks, which a build
importing the file parses. docutils' lines end at more than ``\\n`` -- a carriage return,
VT, FF, FS, GS, RS, NEL, LINE SEPARATOR, PARAGRAPH SEPARATOR (``str.splitlines``) -- so
text split only on ``\\n`` and indented piece by piece left the part after any of those at
column 0, outside its block. The property pinned: read as docutils reads it, every line of
the content is empty, a block's ``**title**::`` line, or indented.
"""

import re
from pathlib import Path

import pytest

from ub_test_reports.junitparser import JUnitParser
from ub_test_reports.needs_export import build_content

BOUNDARIES = {
    "CR": "\r",
    "CRLF": "\r\n",
    "VT": "\x0b",
    "FF": "\x0c",
    "FS": "\x1c",
    "GS": "\x1d",
    "RS": "\x1e",
    "NEL": "\x85",
    "LS": "\u2028",
    "PS": "\u2029",
}
TITLE = re.compile(r"\*\*[^*]+\*\*::")


def _assert_every_line_inside_a_block(content: str) -> None:
    for line in content.splitlines():
        assert line == "" or TITLE.fullmatch(line) or line.startswith("   "), (
            f"{line!r} is outside its block"
        )


def _smuggler(boundary: str) -> str:
    return (
        f"before{boundary}.. raw:: html{boundary}{boundary}   <b>M</b>{boundary}after"
    )


def _case(block: str, text: str) -> dict:
    part = {"kind": "failure", "message": "", "text": ""}
    case: dict = {"parts": [part], "system-out": "", "system-err": ""}
    if block in ("message", "text"):
        part[block] = text
    else:
        case[block] = text
    return case


@pytest.mark.parametrize("boundary", BOUNDARIES)
@pytest.mark.parametrize("block", ["message", "text", "system-out", "system-err"])
def test_a_block_keeps_every_line_inside_it(block, boundary):
    content = build_content(_case(block, _smuggler(BOUNDARIES[boundary])))
    assert "<b>M</b>" in content
    _assert_every_line_inside_a_block(content)


@pytest.mark.parametrize(
    "body",
    ["\rleading", "trailing\r", "\u2028\u2029both\x85"],
    ids=["lead", "trail", "both"],
)
def test_a_boundary_at_either_end_leaves_no_stray_line(body):
    """``strip`` then split: a boundary at the start or the end of the text does not
    survive as an empty first or last line of the block."""
    content = build_content(_case("system-out", body))
    lines = content.splitlines()
    start = lines.index("**System-out**::") + 2
    assert lines[start].strip()
    assert lines[-1].strip()


CASES = {
    case["name"]: case
    for case in JUnitParser(
        str(Path(__file__).parent / "fixtures" / "line_breaks.xml")
    ).parse()[0]["testcases"]
}


@pytest.mark.parametrize("name", ["CR", "CRLF", "NEL", "LS", "PS"])
def test_a_report_s_blocks_keep_every_line_inside_them(name):
    """The XML route: ``line_breaks.xml`` holds one case per character an XML report can
    carry (CR, CR+LF, NEL, LINE SEPARATOR, PARAGRAPH SEPARATOR) in its failure message,
    text and captured output."""
    content = build_content(CASES[f"t_{name}"])
    assert f"M_OUT_{name}" in content
    _assert_every_line_inside_a_block(content)
