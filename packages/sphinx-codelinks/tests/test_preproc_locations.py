"""The libclang engine reads a file its unit entered once without a location lookup
(the twin of useblocks/ubcode#4982).

``clang_getLocation`` and ``clang_getLocationForOffset`` (``SourceLocation.from_position``
and ``from_offset``) map the location they find through the macro-argument table of the
file's first entry, which libclang builds on the first lookup: a walk of every macro
expansion in it, about two minutes for Zephyr's ``ctf_top.h``. These tests fence the
lookups: how many a cold analysis makes, and where in the source a call may be written.
"""

import ast
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

pytest.importorskip("clang.cindex")

import sphinx_codelinks
from sphinx_codelinks.analyse.preproc import loader

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
    with _counted() as calls:
        analyse = _run(tmp_path, ["main.cpp", "inc.cpp", "a.h", "b.h"], db)
    assert {n.need["id"] for n in analyse.oneline_needs} == {
        "IMPL_MAIN",
        "IMPL_INC",
        "IMPL_A",
        "IMPL_B",
    }
    assert calls == []


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
    with _counted() as calls:
        analyse = _run(tmp_path, ["twice.h"], db)
    assert {n.need["id"] for n in analyse.oneline_needs} == {"IMPL_T"}
    assert sorted(calls) == ["from_position"] * 5


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
