"""The libclang engine reads a file its unit entered once without a location lookup
(the twin of useblocks/ubcode#4982).

``clang_getLocation`` and ``clang_getLocationForOffset`` (``SourceLocation.from_position``
and ``from_offset``) map the location they find through the macro-argument table of the
file's first entry, which libclang builds on the first lookup: a walk of every macro
expansion in it, about two minutes for Zephyr's ``ctf_top.h``. These tests fence the
lookups: how many a cold analysis makes, and where in the source a call may be written.
"""

import ast
import ctypes
import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("clang.cindex")

import sphinx_codelinks
from sphinx_codelinks.analyse.preproc import compile_db, libclang_parser, loader

from .test_extraction_fixtures import LINE_ENDINGS, _extract, _load_cases
from .test_preproc_includer import _db, _run, _write

SOURCE_ROOT = Path(sphinx_codelinks.__file__).parent

LOOKUPS = (
    "from_position",
    "from_offset",
    "clang_getLocation",
    "clang_getLocationForOffset",
)
"""The calls that look a location up (``clang.cindex`` and libclang spellings)."""


@contextmanager
def _counted() -> Iterator[list[str]]:
    """Every ``SourceLocation.from_position`` / ``from_offset`` call made inside,
    by name, counted at ``clang.cindex`` itself: a call that bypasses the engine's
    own helper is counted too."""
    cx = loader.load_clang_cindex()
    calls: list[str] = []
    originals = {name: cx.SourceLocation.__dict__[name] for name in LOOKUPS[:2]}

    def counting(name: str, original: staticmethod) -> staticmethod:
        def call(*args: object) -> object:
            calls.append(name)
            return original.__func__(*args)

        return staticmethod(call)

    for name, original in originals.items():
        setattr(cx.SourceLocation, name, counting(name, original))
    try:
        yield calls
    finally:
        for name, original in originals.items():
            setattr(cx.SourceLocation, name, original)


ONCE = {
    # a unit's main file with its own entry, which includes a guarded header that
    # includes another
    "main.cpp": '#include "a.h"\n// @Main, IMPL_MAIN, impl\nint m;\n',
    "a.h": (
        '#ifndef A_H\n#define A_H\n#include "b.h"\n'
        "// @A, IMPL_A, impl\nint a;\n#endif\n"
    ),
    "b.h": "// @B, IMPL_B, impl\nint b;\n",
    # a source with no entry of its own, read through the unity entry that includes it
    "unity.cpp": '#include "inc.cpp"\n#include "a.h"\n',
    "inc.cpp": "// @Inc, IMPL_INC, impl\nint inc;\n",
}


def test_files_entered_once_are_read_with_no_location_lookup(tmp_path: Path) -> None:
    """A cold analysis of a main file, a source read through its includer and two
    headers read through the units that include them, each entered once: no lookup.
    (Every route: the own entry, ``included_files`` and the includer read, the header
    pass's units and its reader.)"""
    _write(tmp_path, ONCE)
    db = _db(
        tmp_path, [{"file": "main.cpp", "args": []}, {"file": "unity.cpp", "args": []}]
    )
    before = loader.slow_lookups()
    with _counted() as calls:
        analyse = _run(tmp_path, ["main.cpp", "inc.cpp", "a.h", "b.h"], db)
    assert {n.need["id"] for n in analyse.oneline_needs} == {
        "IMPL_MAIN",
        "IMPL_INC",
        "IMPL_A",
        "IMPL_B",
    }
    assert calls == []
    assert loader.slow_lookups() == before


def test_a_file_entered_twice_is_looked_up(tmp_path: Path) -> None:
    """A header without a guard, included twice: its first entry's start
    (``first_entry_base``), the extent of its code (``_code_offsets``) and the range
    its comments are read in are looked up, as before, so the count above is not
    vacuous."""
    _write(
        tmp_path,
        {
            "main.cpp": '#include "twice.h"\n#include "twice.h"\n',
            "twice.h": "// @T, IMPL_T, impl\nextern int t;\n",
        },
    )
    db = _db(tmp_path, [{"file": "main.cpp", "args": []}])
    before = loader.slow_lookups()
    with _counted() as calls:
        analyse = _run(tmp_path, ["twice.h"], db)
    assert {n.need["id"] for n in analyse.oneline_needs} == {"IMPL_T"}
    assert sorted(calls) == ["from_position"] * 5
    # each of them through the helper, which counts it
    assert loader.slow_lookups() - before == 5


@contextmanager
def _costs() -> Iterator[dict[str, int]]:
    """What finding the starts costs inside: ``loader.inclusions`` calls, counted from
    outside the engine, and the walks of a unit's top-level cursors
    ``loader.entry_starts`` makes (the (d) anchors) with the cursors they took, from
    the engine's own count (``loader.costs``)."""
    costs = {"inclusions": 0}
    inclusions = loader.inclusions
    before = loader.costs()

    def counting_inclusions(*args: Any) -> Any:
        costs["inclusions"] += 1
        return inclusions(*args)

    loader.inclusions = counting_inclusions
    try:
        yield costs
    finally:
        loader.inclusions = inclusions
        after = loader.costs()
        costs["walks"] = after["walks"] - before["walks"]
        costs["cursors"] = after["cursors"] - before["cursors"]


def test_a_unit_read_for_many_headers_finds_its_starts_once(tmp_path: Path) -> None:
    """The header pass reads many headers through one reader unit: the unit's inclusions
    are listed once, and its cursors walked at most once, for all of them, not once per
    header read (a leaf header has no ``#include`` and no skipped range, so only the
    walk anchors it)."""
    leaves = {f"h{i}.h": f"// @H{i}, IMPL_H{i}, impl\nint h{i};\n" for i in range(6)}
    _write(
        tmp_path,
        {**leaves, "main.cpp": "".join(f'#include "{name}"\n' for name in leaves)},
    )
    db = _db(tmp_path, [{"file": "main.cpp", "args": []}])
    with _costs() as costs:
        analyse = _run(tmp_path, list(leaves), db)
    assert len(analyse.oneline_needs) == len(leaves)
    assert costs["inclusions"] == 1
    assert costs["walks"] <= 1


def test_an_empty_file_costs_no_walk(tmp_path: Path) -> None:
    """A file with no bytes has no location to anchor it, and its lookup walks no macro
    expansion: when the only files without an anchor are empty, the cursors are not
    walked."""
    _write(
        tmp_path,
        {
            "main.c": '#include "a.h"\n#include "empty.h"\nint m;\n',
            "a.h": '#include "empty2.h"\nint a;\n',
            "empty.h": "",
            "empty2.h": "",
        },
    )
    tu = libclang_parser.parse_translation_unit(
        tmp_path / "main.c", [f"-working-directory={tmp_path}"]
    )
    files = [inclusion.file for inclusion in loader.inclusions(tu)]
    with _costs() as costs:
        starts = loader.entry_starts(tu, files)
    assert len(starts) == 2  # main.c (the unit's extent) and a.h (its #include)
    assert costs["walks"] == 0


def test_the_walk_stops_once_every_file_has_a_start(tmp_path: Path) -> None:
    """The walk of the top-level cursors stops at the first cursor of the last file it
    seeks: a leaf header included first is found long before the main file's 300
    declarations."""
    _write(
        tmp_path,
        {
            "main.c": '#include "leaf.h"\n'
            + "".join(f"int v{i};\n" for i in range(300)),
            "leaf.h": "int leaf;\n",
        },
    )
    tu = libclang_parser.parse_translation_unit(
        tmp_path / "main.c", [f"-working-directory={tmp_path}"]
    )
    leaf = tu.get_file(str(tmp_path / "leaf.h"))
    children = len(list(tu.cursor.get_children()))
    with _costs() as costs:
        starts = loader.entry_starts(tu, [leaf])
    assert list(starts) == [loader.file_id(leaf)]
    assert costs["walks"] == 1
    assert costs["cursors"] < children - 250


def _lookup_sites() -> list[str]:
    """Each place under ``src/sphinx_codelinks`` that names a location lookup, as
    ``file:line in function``: an attribute (``cx.SourceLocation.from_position``) or a
    string (``lib["clang_getLocation"]``)."""
    sites = []
    for path in sorted(SOURCE_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        functions: list[tuple[int, int, str]] = [
            (node.lineno, node.end_lineno or node.lineno, node.name)
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                named = node.attr in LOOKUPS
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                named = node.value in LOOKUPS
            else:
                continue
            if not named:
                continue
            # the innermost function around it
            around = [f for f in functions if f[0] <= node.lineno <= f[1]]
            name = max(around, key=lambda f: f[0])[2] if around else "<module>"
            relative = path.relative_to(SOURCE_ROOT).as_posix()
            sites.append(f"{relative}:{node.lineno} in {name}")
    return sites


def test_no_location_is_looked_up_outside_the_helper() -> None:
    """Every location lookup is written in ``loader.looked_up``, which counts it: a
    call written anywhere else would make a lookup no count sees."""
    sites = _lookup_sites()
    outside = [
        site
        for site in sites
        if not site.startswith("analyse/preproc/loader.py:")
        or not site.endswith(" in looked_up")
    ]
    assert outside == []
    assert sites, "the helper itself names the lookups"


def _comments(tu: Any, extent: Any) -> list[tuple[int, int, str]]:
    return [
        (t.extent.start.offset, t.extent.end.offset, t.kind.name)
        for t in tu.get_tokens(extent=extent)
    ]


def _file_location(location: Any) -> tuple[Any, int]:
    """Where ``location`` is in a file (``clang_getFileLocation``), macro or not."""
    file, offset = ctypes.c_void_p(), ctypes.c_uint()
    loader._call("clang_getFileLocation")(
        location, ctypes.byref(file), None, None, ctypes.byref(offset)
    )
    return loader.file_id(file.value), offset.value


def _check_unit(tu: Any, working: Path) -> tuple[int, list[str]]:
    """Assert that every file ``tu`` entered once and has a start for reads as the
    lookup reads it: the same start (raw encoding), the same system-header answer, and
    the same range for ``_active_comments``, made from the unit's starts and the file's
    bytes as it reads them (both ends, every token by kind and offsets); and that a
    file entered once with no start holds no token but comments. A relative name is
    taken against ``working``, the unit's working directory. Returns how many files had
    a start and the non-empty files entered once that had none."""
    cx = loader.load_clang_cindex()
    entered = loader.inclusions(tu)
    counts: dict[Any, int] = {}
    files: dict[Any, Any] = {}
    for inclusion in entered:
        key = loader.file_id(inclusion.file)
        counts[key] = counts.get(key, 0) + 1
        files.setdefault(key, inclusion.file)
    starts = loader.entry_starts(tu, list(files.values()), entered)
    without = []
    for key, file in files.items():
        start = starts.get(key)
        if counts[key] > 1:
            assert start is None, f"{file.name} entered {counts[key]} times has a start"
            continue
        if start is None:
            if loader.file_contents(tu, file):
                without.append(file.name)
                # no location in it: comments only
                kinds = {
                    kind
                    for _, _, kind in _comments(
                        tu,
                        cx.SourceRange.from_locations(
                            cx.SourceLocation.from_position(tu, file, 1, 1),
                            cx.SourceLocation.from_offset(
                                tu, file, len(loader.file_contents(tu, file) or b"")
                            ),
                        ),
                    )
                }
                assert kinds <= {"COMMENT"}, f"{file.name} has {kinds} but no start"
            continue
        looked = cx.SourceLocation.from_offset(tu, file, 0)
        assert int(start.int_data) == int(looked.int_data), file.name
        assert bool(start.is_in_system_header) == bool(looked.is_in_system_header)
        # the range _active_comments reads, its end line as it counts it
        raw = (working / file.name).read_bytes()
        line = len(raw.decode("utf-8", errors="replace").splitlines()) + 1
        made = libclang_parser._whole_file(tu, file, line, starts, raw)
        reference = cx.SourceRange.from_locations(
            cx.SourceLocation.from_position(tu, file, 1, 1),
            cx.SourceLocation.from_position(tu, file, line, 1),
        )
        # the same file bounds (the raw encodings can differ: where the file's last
        # bytes are a macro argument its includer closes, the looked-up end is a macro
        # location there, which decodes to the same file location)
        assert int(made.start.int_data) == int(reference.start.int_data), file.name
        assert _file_location(made.end) == _file_location(reference.end), file.name
        assert _comments(tu, made) == _comments(tu, reference), file.name
    return len(starts), without


@contextmanager
def _every_unit_checked() -> Iterator[list[tuple[int, list[str]]]]:
    """Run :func:`_check_unit` on every unit the engine parses inside."""
    checked: list[tuple[int, list[str]]] = []
    parse: Callable[..., Any] = loader.parse_translation_unit

    def checking(main: Path, args: list[str], *rest: Any) -> Any:
        tu = parse(main, args, *rest)
        checked.append(_check_unit(tu, compile_db.working_directory(args)))
        return tu

    loader.parse_translation_unit = checking
    try:
        yield checked
    finally:
        loader.parse_translation_unit = parse


HAND_CASES = {
    "lf.h": b"// a\nint lf;\n",
    "no_final_eol.h": b"int nofinal;\n// last",
    "crlf.h": b"// a\r\nint crlf;\r\n// b\r\n",
    "cr.h": b"// a\rint cr;\r// b\r",
    "form_feed.h": b"// a\fb\nint ff;\n// c\n",
    "nel.h": "// a\u0085b\nint nel;\n// c".encode(),
    "invalid_utf8.h": b"// \xff\xfe\nint bad;\n",
    "empty.h": b"",
    "comments_only.h": b"// only a comment\n/* and a block */\n",
    "if0_first.h": b"#if 0\n// dead\n#endif\nint if0;\n",
    "define_only.h": b"#define ONLY 1\n",
    "outer.h": b'#include "inner.h"\nint outer;\n',
    "inner.h": b"// inner\nint inner;\n",
    # its last bytes are a macro argument the includer closes
    "macro_end.h": b"// c\nint me = F(1, 2",
}


def test_a_made_range_is_the_looked_up_one(tmp_path: Path) -> None:
    """For every file of the unit entered once (no final EOL, CRLF, lone CR, a form
    feed and NEL that only ``splitlines`` breaks on, invalid UTF-8, empty, comments
    only, ``#if 0`` first, a ``#define`` as the only anchor, a header included from a
    header, a macro argument closed by the includer, and the main file): the start,
    the system-header answer, the range's ends and its tokens are the lookup's. Only
    the empty file and the comment-only one have no start; a header entered twice has
    none either."""
    for name, raw in HAND_CASES.items():
        (tmp_path / name).write_bytes(raw)
    (tmp_path / "twice.h").write_bytes(b"// t\n")
    main = tmp_path / "main.c"
    includes = [n for n in HAND_CASES if n not in ("inner.h", "macro_end.h")]
    main.write_bytes(
        "".join(f'#include "{n}"\n' for n in includes).encode()
        + b'#define F(a, b) (a + b)\n#include "macro_end.h"\n);\n'
        + b'#include "twice.h"\n#include "twice.h"\n// main\n'
    )
    tu = libclang_parser.parse_translation_unit(
        main, [f"-working-directory={tmp_path}"]
    )
    started, without = _check_unit(tu, tmp_path)
    assert sorted(Path(n).name for n in without) == ["comments_only.h"]
    # every file but twice.h, empty.h and comments_only.h, and the main file
    assert started == len(HAND_CASES) - 2 + 1


@pytest.mark.parametrize(
    "case",
    [
        param
        for param in _load_cases()
        if param.values[0].get("engine") == "libclang"
        and param.id.startswith("preproc_")
    ],
)
def test_every_preproc_case_reads_its_made_ranges_as_looked_up(
    case: dict, tmp_path: Path
) -> None:
    """Every unit the engine parses for a libclang case of the shared corpus
    (``tests/data/extraction/preproc_*.yaml``) passes :func:`_check_unit`: a file
    entered once without a start holds comments only."""
    source = case["source"].replace("\n", LINE_ENDINGS[case.get("line_endings", "lf")])
    # a case whose every parse is refused parses no unit; the next test counts them
    with _every_unit_checked():
        _extract(case, tmp_path, source)


def test_the_corpus_has_units_and_starts(tmp_path: Path) -> None:
    """The corpus check above is not vacuous: its cases parse units, and the units'
    files have starts."""
    cases = [
        param.values[0]
        for param in _load_cases()
        if param.values[0].get("engine") == "libclang"
        and param.id.startswith("preproc_")
    ]
    assert len(cases) > 50
    total_units = total_started = 0
    for i, case in enumerate(cases):
        root = tmp_path / str(i)
        root.mkdir()
        source = case["source"].replace(
            "\n", LINE_ENDINGS[case.get("line_endings", "lf")]
        )
        with _every_unit_checked() as checked:
            _extract(case, root, source)
        total_units += len(checked)
        total_started += sum(started for started, _ in checked)
    assert total_units > 50
    assert total_started > total_units


def _system_header_project(root: Path) -> Any:
    (root / "usr").mkdir()
    (root / "sys").mkdir()
    # the line that makes the rest of the file a system header comes first, so
    # every location in the file but its first bytes is in a system header
    (root / "usr" / "pragma.h").write_text(
        "#pragma GCC system_header\n#define AFTER 1\n"
    )
    (root / "usr" / "marker.h").write_text('# 7 "marker.h" 3\n#define AFTER2 1\n')
    (root / "sys" / "s.h").write_text('#define S 1\n#include "sib.h"\n')
    (root / "sys" / "sib.h").write_text("#define SIB 1\n")
    (root / "main.c").write_text(
        '#include "usr/pragma.h"\n#include "usr/marker.h"\n#include <s.h>\n'
    )
    return libclang_parser.parse_translation_unit(
        root / "main.c", [f"-working-directory={root}", "-isystem", "sys"]
    )


def test_a_system_header_is_told_at_the_start_of_its_entry(tmp_path: Path) -> None:
    """clang tells a system header by its entry's characteristic, unless a line in it
    changes it (``#pragma GCC system_header``, a line marker with flag 3): every
    anchor after such a line says "system", the file's start does not. So the answer is
    asked at the made start, as the lookup at offset 0 asks it; a header found through
    ``-isystem``, and a quoted sibling of it, are system headers."""
    tu = _system_header_project(tmp_path)
    cx = loader.load_clang_cindex()
    after = {
        c.spelling: c.location
        for c in tu.cursor.get_children()
        if c.kind == cx.CursorKind.MACRO_DEFINITION
        and c.spelling in ("AFTER", "AFTER2")
    }
    assert all(bool(loc.is_in_system_header) for loc in after.values())
    work = tmp_path.resolve()
    assert libclang_parser.included_files(tu, work) == {
        work / "usr" / "pragma.h",
        work / "usr" / "marker.h",
    }
    started, without = _check_unit(tu, tmp_path)
    assert (started, without) == (5, [])


@pytest.mark.parametrize(
    "raw",
    [
        b"// a\nint x;\n",
        b"int x;\n// a",
        b"// a\r\nint x;\r\n",
        b"// a\rint x;\r// b\r",
        b"// a\r\n\r\n\n\r// b",
        b"",
        b"/",
        b"// a\fb\nint x;\n// c\n",
        b"// a\x0bb\n// c",
        "// a\u0085b\n// c\n".encode(),
        "// a\u2028b\n// c".encode(),
        b"// \xff\xfe\n// c\n",
        b"// a\x1cb\n/* c */",
        b"\xef\xbb\xbf// bom\nint x;\n// c\n",
        # a CRLF across clang's 8-byte word scan of the buffer
        b"1234567\r\n89\r\n1234\r\n// c\r\n",
        b"// 345678901234\r\n/* c */\r",
    ],
)
def test_a_line_is_where_clang_places_it(raw: bytes, tmp_path: Path) -> None:
    """``line_offset`` is clang's ``translateLineCol(line, 1)`` for every line of the
    file and the two past its last, which ``_active_comments``' end can be (``splitlines``
    counts at least clang's line breaks)."""
    cx = loader.load_clang_cindex()
    (tmp_path / "x.h").write_bytes(raw)
    (tmp_path / "main.c").write_text('#include "x.h"\n')
    tu = libclang_parser.parse_translation_unit(
        tmp_path / "main.c", [f"-working-directory={tmp_path}"]
    )
    file = tu.get_file(str(tmp_path / "x.h"))
    lines = len(raw.decode("utf-8", errors="replace").splitlines())
    for line in range(1, lines + 3):
        expected = cx.SourceLocation.from_position(tu, file, line, 1).offset
        assert loader.line_offset(raw, line) == expected, line


def test_the_inclusion_stacks_are_copied(tmp_path: Path) -> None:
    """``loader.inclusions`` copies each location while libclang hands it out: every
    entry's innermost location is the ``#include`` line that made it, in its includer.
    (``clang.cindex``'s ``FileInclusion.location`` is a view of a buffer libclang reuses
    and frees, so read after the call it is no such location.)"""
    (tmp_path / "a.h").write_text('// a\n#include "b.h"\n')
    (tmp_path / "b.h").write_text("int b;\n")
    (tmp_path / "main.c").write_text('// main\n\n#include "a.h"\n#include "b.h"\n')
    tu = libclang_parser.parse_translation_unit(
        tmp_path / "main.c", [f"-working-directory={tmp_path}"]
    )
    seen = [
        (Path(i.file.name).name, [(Path(s.file.name).name, s.line) for s in i.stack])
        for i in loader.inclusions(tu)
    ]
    assert seen == [
        ("main.c", []),
        ("a.h", [("main.c", 3)]),
        ("b.h", [("a.h", 2), ("main.c", 3)]),
        ("b.h", [("main.c", 4)]),
    ]


def test_a_unit_that_loaded_an_ast_file_knows_no_start(tmp_path: Path) -> None:
    """In a unit that loaded a precompiled header, ``clang_getInclusions`` does not list
    the header's files, so no file's count of entries is known: none has a start, and
    every location is looked up. A unit that loaded none is told apart."""
    cx = loader.load_clang_cindex()
    (tmp_path / "h.h").write_text("#ifdef SECOND\nint second;\n#endif\nint z;\n")
    (tmp_path / "p.h").write_text('#include "h.h"\nint in_pch;\n')
    (tmp_path / "pch.c").write_text('#define SECOND\n#include "h.h"\nint m;\n')
    header = cx.Index.create().parse(str(tmp_path / "p.h"), args=["-xc-header"])
    pch = tmp_path / "p.pch"
    header.save(str(pch))
    tu = libclang_parser.parse_translation_unit(
        tmp_path / "pch.c",
        [f"-working-directory={tmp_path}", "-include-pch", str(pch)],
    )
    assert loader.loads_an_ast_file(tu)
    files = [i.file for i in loader.inclusions(tu)]
    assert files
    assert loader.entry_starts(tu, files) == {}
    plain = libclang_parser.parse_translation_unit(
        tmp_path / "p.h", [f"-working-directory={tmp_path}", "-xc"]
    )
    assert not loader.loads_an_ast_file(plain)
    assert loader.entry_starts(plain, [i.file for i in loader.inclusions(plain)])


def test_a_location_that_is_not_the_files_is_no_start(tmp_path: Path) -> None:
    """A made location is kept only when it decodes to its file at offset 0: a macro
    location (``D`` expands a declaration in ``m.c``) is never an anchor, and an end
    made past the file (bytes that are not the bytes clang read) is not taken."""
    cx = loader.load_clang_cindex()
    (tmp_path / "m.c").write_text("#define D int d;\nD\n")
    tu = libclang_parser.parse_translation_unit(
        tmp_path / "m.c", [f"-working-directory={tmp_path}"]
    )
    declaration = next(
        c for c in tu.cursor.get_children() if c.kind == cx.CursorKind.VAR_DECL
    )
    assert int(declaration.location.int_data) & 0x80000000
    assert loader._decoded(declaration.location) is None
    file = tu.get_file(str(tmp_path / "m.c"))
    start = loader.entry_starts(tu, [file])[loader.file_id(file)]
    size = len((tmp_path / "m.c").read_bytes())
    assert loader.made_at(start, size) is not None
    assert loader.made_at(start, size + 10) is None


def test_an_unreadable_entry_makes_no_start(tmp_path: Path) -> None:
    """An exception while ``loader.inclusions`` copies an entry (inside a ctypes
    callback, where it would be printed and swallowed) marks the list incomplete: no
    file's count of entries is known, so no start is made, every location is looked up,
    and ``included_files`` gives the same answer."""
    cx = loader.load_clang_cindex()
    (tmp_path / "a.h").write_text("int a;\n")
    (tmp_path / "main.c").write_text('#include "a.h"\n')
    tu = libclang_parser.parse_translation_unit(
        tmp_path / "main.c", [f"-working-directory={tmp_path}"]
    )
    files = [i.file for i in loader.inclusions(tu)]
    work = tmp_path.resolve()
    assert loader.entry_starts(tu, files)
    copy = cx.SourceLocation.from_buffer_copy

    def failing(*_args: Any) -> Any:
        raise RuntimeError("an entry that cannot be read")

    cx.SourceLocation.from_buffer_copy = failing
    try:
        assert not loader.inclusions(tu).complete
        assert loader.entry_starts(tu, files) == {}
        assert libclang_parser.included_files(tu, work) == {work / "a.h"}
    finally:
        cx.SourceLocation.from_buffer_copy = copy


def _read_both(tu: Any, path: Path) -> tuple[list[Any], list[Any]]:
    """``path``'s comments as the engine reads them through ``tu`` (its start made
    when it can) and as the lookup reads them (the range looked up)."""
    cx = loader.load_clang_cindex()
    file = tu.get_file(str(path))
    starts = loader.entry_starts(tu, [file])
    assert starts, "the file has a start"
    made = libclang_parser._active_comments(tu, path, [], starts)
    whole = libclang_parser._whole_file

    def looked(tu_: Any, file_: Any, line: int, *_rest: Any) -> Any:
        return cx.SourceRange.from_locations(
            cx.SourceLocation.from_position(tu_, file_, 1, 1),
            cx.SourceLocation.from_position(tu_, file_, line, 1),
        )

    libclang_parser._whole_file = looked
    try:
        reference = libclang_parser._active_comments(tu, path, [])
    finally:
        libclang_parser._whole_file = whole

    def key(comments: list[Any]) -> list[Any]:
        return [(c.text, c.start_point.row, c.column) for c in comments]

    return key(made), key(reference)


def _parsed_then_rewritten(tmp_path: Path, before: bytes, after: bytes) -> Any:
    """A unit that includes ``h.h`` parsed while it holds ``before``, then ``h.h``
    rewritten to ``after``."""
    header = tmp_path / "h.h"
    header.write_bytes(before)
    (tmp_path / "main.c").write_text('#include "h.h"\n')
    tu = libclang_parser.parse_translation_unit(
        tmp_path / "main.c", [f"-working-directory={tmp_path}"]
    )
    header.write_bytes(after)
    return tu


def test_a_file_whose_size_changed_since_the_parse_is_looked_up(tmp_path: Path) -> None:
    """A file shrunk since the parse, its modification time put back, is told by its
    size and looked up. Its bytes on disk (one line) would end the range two lines into
    what clang read, where the looked-up range ends after the first: one more comment."""
    before = b"int a;\n// one\n// two\n"
    tu = _parsed_then_rewritten(tmp_path, before, b"x" * (len(before) - 3) + b"\n")
    stamp = (tmp_path / "main.c").stat().st_mtime_ns
    file = tu.get_file(str(tmp_path / "h.h"))
    parsed = loader.file_id(file)
    assert parsed is not None
    os.utime(tmp_path / "h.h", ns=(stamp, parsed[2] * 10**9))
    made, reference = _read_both(tu, tmp_path / "h.h")
    assert len(reference) == 1
    assert made == reference


def test_a_same_size_rewrite_since_the_parse_is_looked_up(tmp_path: Path) -> None:
    """A file rewritten to as many bytes since the parse is told by its modification
    time and looked up: read over its new bytes, the range would end past a comment
    the looked-up one leaves out."""
    before = b"int s;\nint t;\n// @C, IMPL_C, impl\n"
    after = b"int s; int t; // @C, IMPL_C, impl\n"
    assert len(before) == len(after)
    tu = _parsed_then_rewritten(tmp_path, before, after)
    file = tu.get_file(str(tmp_path / "h.h"))
    parsed = loader.file_id(file)
    assert parsed is not None
    later = (parsed[2] + 10) * 10**9
    os.utime(tmp_path / "h.h", ns=(later, later))
    made, reference = _read_both(tu, tmp_path / "h.h")
    assert made == reference


def test_an_unchanged_file_reads_its_made_range(tmp_path: Path) -> None:
    """The guard above does not turn every read into a lookup: an unchanged file is
    read over its made range, with no lookup, and reads as the lookup does."""
    text = b"int s;\nint t;\n// @C, IMPL_C, impl\n"
    tu = _parsed_then_rewritten(tmp_path, text, text)
    file = tu.get_file(str(tmp_path / "h.h"))
    parsed = loader.file_id(file)
    assert parsed is not None
    stamp = parsed[2] * 10**9
    os.utime(tmp_path / "h.h", ns=(stamp, stamp))
    starts = loader.entry_starts(tu, [file])
    before = loader.slow_lookups()
    libclang_parser._active_comments(tu, tmp_path / "h.h", [], starts)
    assert loader.slow_lookups() == before
    made, reference = _read_both(tu, tmp_path / "h.h")
    assert made == reference != []


def test_a_unity_unit_finds_its_starts_once(tmp_path: Path) -> None:
    """The includer route reads every source a unity entry includes through that one
    unit: its inclusions are listed once and its cursors walked at most once, for
    ``included_files`` and every read alike."""
    sources = {f"s{i}.cpp": f"// @S{i}, IMPL_S{i}, impl\nint s{i};\n" for i in range(4)}
    _write(
        tmp_path,
        {**sources, "unity.cpp": "".join(f'#include "{name}"\n' for name in sources)},
    )
    db = _db(tmp_path, [{"file": "unity.cpp", "args": []}])
    with _costs() as costs:
        analyse = _run(tmp_path, list(sources), db)
    assert len(analyse.oneline_needs) == len(sources)
    assert costs["inclusions"] == 1
    assert costs["walks"] <= 1


def test_a_failing_walk_makes_no_start(tmp_path: Path, capfd: Any) -> None:
    """An exception inside the walk's callback (where ctypes would print it and go on,
    once per cursor left) stops the walk, and no start is made: every location is
    looked up."""
    cx = loader.load_clang_cindex()
    (tmp_path / "leaf.h").write_text("int leaf;\n")
    (tmp_path / "main.c").write_text('#include "leaf.h"\nint m;\n')
    tu = libclang_parser.parse_translation_unit(
        tmp_path / "main.c", [f"-working-directory={tmp_path}"]
    )
    files = [i.file for i in loader.inclusions(tu)]
    assert len(loader.entry_starts(tu, files)) == 2
    location_of = cx.conf.lib.clang_getCursorLocation

    def failing(*_args: Any) -> Any:
        raise RuntimeError("a cursor that cannot be read")

    capfd.readouterr()
    cx.conf.lib.clang_getCursorLocation = failing
    try:
        assert loader.entry_starts(tu, files) == {}
    finally:
        cx.conf.lib.clang_getCursorLocation = location_of
    assert "Exception ignored" not in capfd.readouterr().err


def test_an_entry_ends_at_its_files_size(tmp_path: Path) -> None:
    """``_entry_end`` finds an entry's last offset exactly, the file's size: for a file
    followed by another entry and for the unit's last."""
    sizes = {"first.h": b"int first;\n// one\n", "last.h": b"int last; /* end */"}
    for name, text in sizes.items():
        (tmp_path / name).write_bytes(text)
    (tmp_path / "main.c").write_text('#include "first.h"\n#include "last.h"\n')
    tu = libclang_parser.parse_translation_unit(
        tmp_path / "main.c", [f"-working-directory={tmp_path}"]
    )
    for name, text in sizes.items():
        file = tu.get_file(str(tmp_path / name))
        start = loader.entry_starts(tu, [file])[loader.file_id(file)]
        at = loader._file_location(start)
        assert at is not None
        assert loader._entry_end(start, at[0], 0) == len(text), name
        inside = loader.made_at(start, 5)
        assert loader._entry_end(inside, at[0], 5) == len(text), name
