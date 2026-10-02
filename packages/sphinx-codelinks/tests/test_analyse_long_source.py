# @Test that line numbers stay exact far past line 256, TEST_ANA_2, test, [IMPL_LNK_1, IMPL_ONE_1, IMPL_MRST_1, IMPL_JSONC_2]
"""Line numbers far down a long source file, with the analysis in a subprocess.

tree-sitter 0.26.0's ``Point.row`` and ``Point.column`` return a borrowed reference
(py-tree-sitter#472, fixed by #466). Ints up to 256 are CPython's cached small ints, so a
short file never notices; a row above that is freed early and the heap is corrupted. The
analysis then dies with SIGSEGV or reports a wrong line, and every fixture elsewhere in
this suite is too short to reach it. This module is what makes the suite see it: it is the
reason ``tree-sitter`` excludes 0.26.0 in ``pyproject.toml``.

The analysis runs in a child interpreter so that a native crash is a clean failure of one
test, naming the exit code, rather than the death of the whole pytest process.

Two paths read tree-sitter points, and each case below reaches one or both of them:
``analyse.py`` reads ``start_point.row`` for every one-line need, need-id reference and
marked-rst block, whatever the language; ``utils.find_prev_sibling_on_same_row`` reads
``start_point.row`` and ``end_point.row`` to tie an inline comment to its structure, and
only YAML and JSONC reach it.
"""

from __future__ import annotations

import json
import signal
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

# Well past the small-int cache (-5..256) at both ends of every marker: the first marker
# sits at row FIRST_ROW, and the file runs to a few thousand lines so that there are
# hundreds of them, each of whose rows is read more than once.
FIRST_ROW = 300
NUM_BLOCKS = 300
UPSTREAM = (
    "tree-sitter's Point getters return a borrowed reference in 0.26.0 "
    "(https://github.com/tree-sitter/py-tree-sitter/issues/472, "
    "fixed by https://github.com/tree-sitter/py-tree-sitter/pull/466)"
)

# The child: one SourceAnalyse over one file, every extractor on, the result written as
# JSON to a file rather than stdout so that nothing the analysis logs can corrupt it.
CHILD = """
import json
import sys
from pathlib import Path

from sphinx_codelinks.analyse.analyse import SourceAnalyse
from sphinx_codelinks.config import SourceAnalyseConfig
from sphinx_codelinks.source_discover.config import CommentType

src, comment_type, out = Path(sys.argv[1]), CommentType(sys.argv[2]), Path(sys.argv[3])
analyse = SourceAnalyse(
    SourceAnalyseConfig(
        src_files=[src],
        src_dir=src.parent,
        get_need_id_refs=True,
        get_oneline_needs=True,
        get_rst=True,
        comment_type=comment_type,
    )
)
analyse.git_remote_url = None
analyse.git_commit_rev = None
analyse.run()
out.write_text(json.dumps([m.to_dict() for m in analyse.all_marked_content]))
"""


@dataclass(frozen=True)
class Marker:
    """One marker the analysis must report, as ``(kind, 0-based row, key, scope)``."""

    kind: str
    row: int
    key: str
    scope: str | None = None


def _pad(lines: list[str], filler: str) -> None:
    """Pad ``lines`` with ``filler`` (formatted with the 0-based row) up to FIRST_ROW."""
    while len(lines) < FIRST_ROW:
        lines.append(filler.format(n=len(lines)))


def _cpp_source() -> tuple[str, list[Marker]]:
    """A C++ file with a one-line need, a need-id reference and a marked-rst block per
    stanza, some on the first line of their comment and some further down it."""
    lines: list[str] = []
    expected: list[Marker] = []
    _pad(lines, "int filler_{n} = {n};")
    for i in range(NUM_BLOCKS):
        row = len(lines)
        lines.append(f"// @Title {i}, IMPL_CPP_{i}, impl")
        expected.append(Marker("need", row, f"IMPL_CPP_{i}"))
        lines.append(f"int value_{i} = {i};")
        # a block comment: the need-id reference is on its second line, so the row is
        # the comment's start row plus an offset
        lines.append("/* block")
        expected.append(Marker("need-id-refs", len(lines), f"REQ_CPP_{i}"))
        lines.append(f"   @need-ids: REQ_CPP_{i}")
        lines.append("*/")
        # a marked-rst block, reported at the row of its start sequence
        lines.append("/*")
        expected.append(Marker("rst", len(lines), f"rst_{i}"))
        lines.append("@rst")
        lines.append(f"rst_{i}")
        lines.append("@endrst")
        lines.append("*/")
        lines.append(f"void func_{i}() {{}}")
    return "\n".join(lines) + "\n", expected


def _yaml_source() -> tuple[str, list[Marker]]:
    """A YAML mapping with an inline marker on every other key, and a marker on a line of
    its own between them, so that both the same-row match and the early exit of the
    sibling walk run."""
    lines: list[str] = []
    expected: list[Marker] = []
    _pad(lines, "filler_{n}: {n}")
    for i in range(NUM_BLOCKS):
        row = len(lines)
        lines.append(f"key_{i}: value_{i}  # @Title {i}, IMPL_YAML_{i}, impl")
        expected.append(Marker("need", row, f"IMPL_YAML_{i}", f"key_{i}: value_{i}"))
        expected.append(
            Marker("need", row + 1, f"IMPL_YAML_OWN_{i}", f"other_{i}: {i}")
        )
        lines.append(f"# @Own line {i}, IMPL_YAML_OWN_{i}, impl")
        lines.append(f"other_{i}: {i}")
    return "\n".join(lines) + "\n", expected


def _jsonc_source() -> tuple[str, list[Marker]]:
    """A JSONC object with an inline marker after every other pair, and a marker on a
    line of its own between them."""
    lines: list[str] = ["{"]
    expected: list[Marker] = []
    _pad(lines, '  "filler_{n}": {n},')
    for i in range(NUM_BLOCKS):
        row = len(lines)
        lines.append(f'  "key_{i}": {i}, // @Title {i}, IMPL_JSONC_{i}, impl')
        expected.append(Marker("need", row, f"IMPL_JSONC_{i}", f'"key_{i}": {i}'))
        expected.append(
            Marker("need", row + 1, f"IMPL_JSONC_OWN_{i}", f'"other_{i}": {i}')
        )
        lines.append(f"  // @Own line {i}, IMPL_JSONC_OWN_{i}, impl")
        lines.append(f'  "other_{i}": {i},')
    lines.append('  "last": 0')
    lines.append("}")
    return "\n".join(lines) + "\n", expected


def _describe_exit(returncode: int) -> str:
    """Name a child's exit: a negative code is the signal that killed it (POSIX)."""
    if returncode < 0:
        try:
            return f"exit code {returncode} ({signal.Signals(-returncode).name})"
        except ValueError:
            pass
    return f"exit code {returncode} ({returncode & 0xFFFFFFFF:#010x})"


def _reported(record: dict, with_scope: bool) -> Marker:
    """The Marker a ``to_dict()`` record from the child describes; the scope only when
    ``with_scope``, since it is tree-sitter point arithmetic only for YAML and JSONC."""
    start, end = record["source_map"]["start"], record["source_map"]["end"]
    assert start["row"] == end["row"], record
    kind = record["type"]
    if kind == "need":
        key = record["need"]["id"]
    elif kind == "need-id-refs":
        (key,) = record["need_ids"]
    else:
        key = record["rst"].strip()
    scope = record["tagged_scope"] if with_scope else None
    return Marker(kind, start["row"], key, scope)


@pytest.mark.parametrize(
    ("comment_type", "suffix", "make_source"),
    [
        pytest.param("cpp", "cpp", _cpp_source, id="cpp"),
        pytest.param("yaml", "yaml", _yaml_source, id="yaml"),
        pytest.param("jsonc", "jsonc", _jsonc_source, id="jsonc"),
    ],
)
def test_line_numbers_past_row_256(
    tmp_path: Path, comment_type: str, suffix: str, make_source
) -> None:
    text, expected = make_source()
    assert min(marker.row for marker in expected) > 256
    source = tmp_path / f"long.{suffix}"
    source.write_text(text, encoding="utf-8")
    out = tmp_path / "marked_content.json"

    result = subprocess.run(
        [sys.executable, "-c", CHILD, str(source), comment_type, str(out)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    if result.returncode != 0:
        pytest.fail(
            f"the {comment_type} analysis of a {len(text.splitlines())}-line file "
            f"crashed with {_describe_exit(result.returncode)}; the likeliest cause is "
            f"that {UPSTREAM}.\nstderr (tail):\n{result.stderr[-2000:]}"
        )
    with_scope = comment_type != "cpp"
    reported = [_reported(record, with_scope) for record in json.loads(out.read_text())]
    wrong = sorted(set(reported) ^ set(expected), key=lambda m: (m.row, m.key))
    assert len(reported) == len(expected) and not wrong, (
        f"the {comment_type} analysis reported {len(reported)} markers for "
        f"{len(expected)} expected; the ones that differ (reported XOR expected, first "
        f"10): {wrong[:10]}. If the rows are wrong, the likeliest cause is that {UPSTREAM}."
    )
