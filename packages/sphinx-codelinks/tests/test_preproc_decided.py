"""The lexical scan and the rule of ``analyse/preproc/decided.py`` (useblocks/ubcode#4866,
slice 2): which arms of a header no compilation-database entry includes its
configuration decides.

The twin of ubCode's ``rust/ubc_codelinks/src/preproc/decided_tests.rs``, case for case:
the skipped ranges are written as a parse gives them, without libclang, and the two
target lists are checked against the loaded libclang.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("clang.cindex")

from sphinx_codelinks.analyse.preproc.decided import (
    TARGET_DEFINEDNESS,
    TARGET_IDENTITY,
    Kind,
    Stated,
    decided_ranges,
    directives,
    names,
)

from sphinx_codelinks.analyse.preproc import libclang_parser, loader
from sphinx_codelinks.analyse.preproc.headers import SkippedSpan


def _span(text: str, first: int, last: int) -> SkippedSpan:
    """A span from line ``first`` to line ``last``, its bytes the start of each line in
    ``text``."""

    def start(line: int) -> int:
        return sum(len(each) for each in text.encode().splitlines(True)[: line - 1])

    return SkippedSpan(start(first), start(last), first, last)


def _scanned(text: str) -> list[tuple[Kind, int, str]]:
    """Each directive the scan finds: its kind, line and text."""
    return [(d.kind, d.line, d.text) for d in directives(text.encode())]


def test_the_scan_reads_the_directives_of_a_header() -> None:
    """Directives are found at the start of a line only, through splices, around
    comments and past literals that hold a ``#``."""
    text = (
        "#ifndef G_H\n#define G_H\n  # if A && \\\n  B /* x\n y */ || C // z\n"
        'const char *s = "\\\n#if NOT";\nauto r = R"d(\n#if RAW\n)d";\n'
        "/*\n#if COMMENTED\n*/\n#elif defined X\n#else\n#endif\n"
        "int x; #if NOT_AT_START\n#endif\n"
    )
    assert _scanned(text) == [
        (Kind.if_, 1, "!defined(G_H)"),
        (Kind.define, 2, "G_H"),
        (Kind.if_, 3, "A &&   B   || C"),
        (Kind.elif_, 14, "defined X"),
        (Kind.elif_, 15, ""),
        (Kind.endif, 16, ""),
        (Kind.endif, 18, ""),
    ]


@pytest.mark.parametrize(
    ("condition", "expected"),
    [
        pytest.param("0", [], id="constant"),
        pytest.param("(2 + 3) * 4 > 0x1Fu", [], id="arith"),
        pytest.param("1e+3 > 2", [], id="exponent"),
        pytest.param("'a' == L'b'", [], id="char_literal"),
        pytest.param(
            "defined(A) && !defined ( B )",
            [("A", True), ("B", True)],
            id="defined_parens",
        ),
        pytest.param(
            "defined A || C > 1", [("A", True), ("C", False)], id="defined_bare"
        ),
        pytest.param(
            '__has_include(<a/b.h>) && __has_include_next("c.h")',
            [],
            id="has_include",
        ),
        pytest.param(
            "__has_include( CFG_HDR )", [("CFG_HDR", False)], id="has_include_macro"
        ),
        pytest.param("__has_include", None, id="has_include_bare"),
        pytest.param(
            "__has_builtin(__builtin_x)",
            [("__has_builtin", False)],
            id="has_builtin",
        ),
        pytest.param(
            "VERSION(1, MINOR) > 2",
            [("VERSION", False), ("MINOR", False)],
            id="function_like",
        ),
        pytest.param("A and not B", [("A", False), ("B", False)], id="word_operators"),
        pytest.param('A == "x"', None, id="string"),
        pytest.param("  ", None, id="empty"),
        pytest.param("defined()", None, id="defined_nothing"),
    ],
)
def test_the_names_of_a_condition(
    condition: str, expected: list[tuple[str, bool]] | None
) -> None:
    """The names a condition reads (``True``: only its definedness): ``defined`` reads
    its operand's definedness, ``__has_include`` of a header name none, of a macro the
    macro, a literal none; a string or nothing at all cannot be read."""
    assert names(condition) == expected


def _decides(
    stated: Stated, name: str, defined_only: bool, local: tuple[str, ...] = ()
) -> bool:
    """Whether ``stated`` decides the value of ``name`` (or only its definedness), in a
    header that defines ``local``."""
    return stated.decides((name, defined_only), frozenset(local))


def test_the_stated_defines_are_the_arguments_d_and_u() -> None:
    """The configuration's ``-D`` and ``-U``, as the parse's arguments carry them: a
    stated macro's value decides only when it is decided in turn (a literal, nothing, a
    header name, or stated macros, a function-like macro's parameters aside); its
    definedness always; a cycle decides nothing."""
    args = [
        "-x",
        "c++",
        "-DA",
        "-DB=1",
        "-D",
        "C",
        "-UD",
        "-DF(x)=x+B",
        "-Ifoo",
        "-DE=UNSTATED",
        "-DG=B*2",
        "-DH=",
        "-DI=<cfg.h>",
        "-DJ=K",
        "-DK=J",
        "-DL(x)=x+M",
    ]
    stated = Stated.of(args, target=False)
    for name in ["A", "B", "C", "D", "F", "G", "H", "I"]:
        assert _decides(stated, name, False), name
    for name in ["E", "J", "K", "L", "foo", "x", "UNSTATED"]:
        assert not _decides(stated, name, False), name
    for name in ["E", "J", "L"]:
        assert _decides(stated, name, True), f"{name} is defined"
    assert not _decides(stated, "A", True, ("A",)), "the header's own"
    assert not _decides(stated, "G", False, ("B",)), "its value is the header's"


def test_the_target_decides_only_its_identity_when_stated() -> None:
    """The target decides only its identity, and only when it is stated: not a name a
    file of the parse defines, nor a build's ``-D`` spelling, the compiler's identity, a
    flag's, nor the standard's own."""
    macros = [("__x86_64__", False), ("__clang__", False), ("__linux__", True)]
    guessed = Stated.of([], target=False)
    guessed.macros(macros)
    stated = Stated.of([], target=True)
    stated.macros(macros)
    for name in ["__x86_64__", "__arm__", "_WIN32", "__BYTE_ORDER__"]:
        assert not _decides(guessed, name, False), name
        assert _decides(stated, name, False), name
    # The data model: its definedness alone.
    for name in ["__LP64__", "__SIZEOF_LONG__", "_M_X64"]:
        assert not _decides(guessed, name, True), name
        assert _decides(stated, name, True), name
        assert not _decides(stated, name, False), f"{name}'s value"
    for name in [
        "__linux__",
        "__ZEPHYR__",
        "_DEBUG",
        "_GNU_SOURCE",
        "__KERNEL__",
        "__clang__",
        "__GNUC__",
        "_MSC_VER",
        "__thumb__",
        "__ARM_ARCH",
        "__ARM_ARCH_7M__",
        "__OPTIMIZE__",
        # Clang's own spellings, and what `-march` or `/arch` decides.
        "__LITTLE_ENDIAN__",
        "__BIG_ENDIAN__",
        "__ILP32__",
        "_ILP32",
        "__arm64__",
        "__ppc__",
        "__mips",
        "__mips64",
        "__sparc_v9__",
        "_M_ARM",
        "__cplusplus",
        "__has_feature",
        "CONFIG_X",
    ]:
        assert not _decides(stated, name, False), name


def test_a_digraph_introduces_a_directive() -> None:
    """The digraph ``%:`` introduces a directive as ``#`` does."""
    text = "#ifdef S\n%:ifndef U\na\n  %: else\nb\n%:endif\n#endif\n"
    assert _scanned(text) == [
        (Kind.if_, 1, "defined(S)"),
        (Kind.if_, 2, "!defined(U)"),
        (Kind.elif_, 4, ""),
        (Kind.endif, 6, ""),
        (Kind.endif, 7, ""),
    ]
    # The `%:else` arm is the `%:ifndef U`'s, undecided: dropped.
    ranges, count = decided_ranges(
        text.encode(), [_span(text, 4, 6)], Stated.of(["-DS"], target=False)
    )
    assert ranges == []
    assert count == 1


@pytest.mark.parametrize(
    ("text", "skipped", "kept", "undecided"),
    [
        # `#if 0` / `#elif U` / `#else`: one range from the `#if` to the `#else`.
        pytest.param(
            "#if 0\na\n#elif U\nb\n#else\nc\n#endif\n", [(1, 5)], [(1, 3)], 1, id="cut"
        ),
        # `#if U` taken / `#else`: the `#else` reads `U` too.
        pytest.param(
            "#if U\na\n#else\nb\n#endif\n",
            [(3, 5)],
            [],
            1,
            id="after_undecided_taken",
        ),
        # `#if 1` taken / `#elif U` / `#else`: both decided by the taken arm.
        pytest.param(
            "#if 1\na\n#elif U\nb\n#else\nc\n#endif\n",
            [(3, 7)],
            [(3, 7)],
            0,
            id="after_decided_taken",
        ),
        # `#if U` skipped / `#elif 1`: the `#elif` follows an undecided arm.
        pytest.param(
            "#if U\na\n#elif 1\nb\n#endif\n", [(1, 3)], [], 1, id="first_undecided"
        ),
        # A nested chain decides on its own; its enclosing arm is taken.
        pytest.param(
            "#ifdef U\n#if 0\na\n#endif\n#endif\n",
            [(2, 4)],
            [(2, 4)],
            0,
            id="nested",
        ),
        # A range no directive starts is read as written.
        pytest.param("int a;\n#if 0\n#endif\n", [(1, 3)], [], 1, id="unmatched"),
    ],
)
def test_the_ranges_a_chain_decides(
    text: str,
    skipped: list[tuple[int, int]],
    kept: list[tuple[int, int]],
    undecided: int,
) -> None:
    """A chain's arms: decided until its first undecided condition, every later arm
    decided once an arm decided is taken. A range covering several arms is cut before
    its first undecided one."""
    spans = [_span(text, first, last) for first, last in skipped]
    ranges, count = decided_ranges(text.encode(), spans, Stated.of([], target=False))
    assert [(r.start_line, r.end_line) for r in ranges] == kept
    assert count == undecided
    # A cut range ends at the `#` of the arm it stops before.
    for r in ranges:
        expected = _span(text, r.start_line, r.end_line)
        assert (r.start_byte, r.end_byte) == (expected.start_byte, expected.end_byte)


#: for each name of the two lists, a triple the loaded libclang predefines it for
#: (ubCode's ``clang_predefines_every_listed_name_for_some_triple`` table)
BY_TRIPLE: list[tuple[str, list[str]]] = [
    (
        "x86_64-linux-gnu",
        [
            "__amd64",
            "__amd64__",
            "__x86_64",
            "__x86_64__",
            "__ELF__",
            "__gnu_linux__",
            "__linux",
            "__linux__",
            "__unix__",
            "__BYTE_ORDER__",
            "__CHAR_BIT__",
            "__ORDER_BIG_ENDIAN__",
            "__ORDER_LITTLE_ENDIAN__",
            "__ORDER_PDP_ENDIAN__",
            "__LP64__",
            "_LP64",
            "__SIZEOF_INT__",
            "__SIZEOF_LONG__",
            "__SIZEOF_LONG_LONG__",
            "__SIZEOF_POINTER__",
            "__SIZEOF_PTRDIFF_T__",
            "__SIZEOF_SHORT__",
            "__SIZEOF_SIZE_T__",
        ],
    ),
    ("i386-linux-gnu", ["__i386", "__i386__"]),
    ("aarch64-linux-gnu", ["__aarch64__", "__AARCH64EL__"]),
    ("aarch64_be-linux-gnu", ["__AARCH64EB__"]),
    ("arm-none-eabi", ["__arm__", "__ARMEL__"]),
    ("armeb-none-eabi", ["__ARMEB__"]),
    ("riscv64-linux-gnu", ["__riscv"]),
    ("mips-linux-gnu", ["__mips__", "__MIPSEB__"]),
    ("mipsel-linux-gnu", ["__MIPSEL__"]),
    (
        "powerpc64-linux-gnu",
        ["__powerpc__", "__powerpc64__", "__PPC__", "__PPC64__"],
    ),
    ("s390x-linux-gnu", ["__s390__", "__s390x__"]),
    ("sparc-linux-gnu", ["__sparc", "__sparc__"]),
    ("avr", ["__AVR__"]),
    ("msp430", ["__MSP430__"]),
    ("hexagon", ["__hexagon__"]),
    ("loongarch64-linux-gnu", ["__loongarch__"]),
    ("m68k-linux-gnu", ["__m68k__"]),
    ("wasm32-wasi", ["__wasm__", "__wasm32__", "__wasi__"]),
    ("wasm64", ["__wasm64__"]),
    ("wasm32-unknown-emscripten", ["__EMSCRIPTEN__"]),
    ("x86_64-w64-mingw32", ["__MINGW32__", "__MINGW64__", "_WIN32", "_WIN64"]),
    ("x86_64-pc-windows-msvc", ["_M_AMD64", "_M_X64"]),
    ("i686-pc-windows-msvc", ["_M_IX86"]),
    ("aarch64-pc-windows-msvc", ["_M_ARM64"]),
    ("x86_64-apple-darwin", ["__APPLE__", "__MACH__"]),
    ("aarch64-linux-android", ["__ANDROID__"]),
    ("x86_64-unknown-freebsd", ["__FreeBSD__"]),
    ("x86_64-pc-cygwin", ["__CYGWIN__"]),
    ("x86_64-unknown-haiku", ["__HAIKU__"]),
    ("x86_64-unknown-netbsd", ["__NetBSD__"]),
    ("x86_64-unknown-openbsd", ["__OpenBSD__"]),
    ("x86_64-pc-solaris2.11", ["__sun"]),
    ("powerpc-ibm-aix", ["_AIX"]),
]


def test_clang_predefines_every_listed_name_for_some_triple(tmp_path: Path) -> None:
    """For each name of the two lists, a triple the loaded libclang predefines it for: a
    name clang predefines for no triple would be decided ABSENT on every stated target,
    its arm left out where GCC compiles it (the reason ``__powerpc``, which clang sets on
    AIX alone, is not listed). A libclang upgrade that stops predefining one turns this
    red. ``__wasm64__`` and the MSVC ``_M_*`` have no GCC port; the rest GCC sets too
    (the report of useblocks/ubcode#4866 cites where)."""
    # Every listed name is in the table, once.
    table = sorted(name for _, listed in BY_TRIPLE for name in listed)
    assert table == sorted([*TARGET_IDENTITY, *TARGET_DEFINEDNESS])
    path = tmp_path / "a.c"
    path.write_text("int x;\n", encoding="utf-8")
    cx = loader.load_clang_cindex()

    def predefined(triple: str) -> set[str]:
        tu = libclang_parser.parse_translation_unit(
            path, ["-x", "c", f"--target={triple}"]
        )
        return {
            cursor.spelling
            for cursor in tu.cursor.get_children()
            if cursor.kind == cx.CursorKind.MACRO_DEFINITION
        }

    for triple, listed in BY_TRIPLE:
        found = predefined(triple)
        for name in listed:
            assert name in found, f"{name} for {triple}"
    # Why these are not listed: clang predefines none of them where GCC sets them
    # (`__powerpc`, `__unix` on Linux PowerPC and NetBSD), or sets one GCC does not
    # (`__Fuchsia__`; GCC's spelling is `__fuchsia__`), and no triple of its at all
    # (`__xtensa__`).
    assert "__powerpc" not in predefined("powerpc-linux-gnu")
    assert "__unix" not in predefined("x86_64-unknown-netbsd")


def test_the_lists_are_ubcodes_in_its_order() -> None:
    """The two lists are copied from ubCode's ``decided.rs`` in its order (the table
    above sorts them, so it cannot see an order or a duplicate): each name once, the
    identity list's architectures, systems and byte orders in their three groups."""
    assert len(set(TARGET_IDENTITY)) == len(TARGET_IDENTITY) == 57
    assert len(set(TARGET_DEFINEDNESS)) == len(TARGET_DEFINEDNESS) == 14
    assert not set(TARGET_IDENTITY) & set(TARGET_DEFINEDNESS)
    assert TARGET_IDENTITY[0] == "__aarch64__"
    assert TARGET_IDENTITY[25:27] == ("__x86_64__", "__ANDROID__")
    assert TARGET_IDENTITY[45:47] == ("_WIN64", "__AARCH64EB__")
    assert TARGET_IDENTITY[-1] == "__ORDER_PDP_ENDIAN__"
    assert TARGET_DEFINEDNESS[0] == "__FreeBSD__"
    assert TARGET_DEFINEDNESS[-1] == "_M_X64"
