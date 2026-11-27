"""Which ``#if`` arms of a header no compilation-database entry includes the
configuration decides (useblocks/ubcode#4866, slice 2).

The twin of ubCode's ``rust/ubc_codelinks/src/preproc/decided.rs``: the rule, the two
target lists and the lexical scan are the same, so both tools leave out the same arms.

Such a header is read with the ``[preprocessor]`` table (its ``defines``, ``includes``
and ``std``) for the ``target`` setting's target, else the machine the analysis runs
on: a configuration no entry compiles it with. Its parse skips the arms that
configuration does not compile, and an arm the build compiles (on a ``-D`` of the
entries' own, or for their target) would be hidden. So of the ranges the parse
skipped, only an arm whose whole conditional chain is decided stays left out
(:func:`decided_ranges`); every other skipped arm is read as written.

An arm is decided when every condition that decides it is: its own, and those of the
earlier arms of its chain (an ``#else`` has none of its own), or when an earlier arm of
the chain is decided and taken. A condition is decided when every name it reads is
(:meth:`Stated.decides`):

- a macro the configuration states: the ``-D`` and ``-U`` of the parse's arguments (the
  ``defines``), whose value is decided in turn (``A=B`` with ``B`` unstated is not;
  ``defined(A)`` and ``#ifdef A`` read only that it is);
- the target's identity, when the ``target`` setting states it: a macro of
  :data:`TARGET_IDENTITY`, which GCC and clang set alike for one effective triple
  whatever its other flags (``__arm__``, ``_WIN32``, ``__BYTE_ORDER__``), or the
  definedness alone of one of :data:`TARGET_DEFINEDNESS` (``__LP64__``,
  ``__SIZEOF_LONG__``), decided whether clang predefines it for the parse or not. With
  no setting the target is a guess, and they decide nothing;
- ``__has_include`` and ``__has_include_next`` of a header name (``<a.h>``, ``"a.h"``)
  decide (the stated ``includes`` say what is found); of a macro, as the macro does;
  literals decide.

Never decided: a name the header itself ``#define``\\ s or ``#undef``\\ s (a condition may
read it before or after); every other name, whatever its spelling: one a build passes
(``__ZEPHYR__``, ``_DEBUG``), the compiler's identity (``__clang__``, ``__GNUC__``: the
build's compiler is not clang), one its other flags decide (``__thumb__``,
``__ARM_ARCH``, ``__OPTIMIZE__``), the standard's own (``__cplusplus``,
``__STDC_VERSION__``: the language of a header no entry compiles is a guess too),
clang's other ``__has_*`` (GCC answers otherwise); and anything the scan cannot read (a
string, an empty condition, a skipped range that starts at no directive it found). Each
fails toward reading the arm as written.

libclang gives the ranges, not the conditions, so the directives are read from the
header's text by a lexical scan (:func:`directives`): line splices joined, comments,
string and character literals (raw strings too) passed over, a directive introduced by
``#`` or by its digraph ``%:``.

Nothing here needs libclang: the parse's skipped ranges and macro definitions are
handed in.
"""

from __future__ import annotations

import enum
from collections.abc import Iterable
from dataclasses import dataclass, field

from sphinx_codelinks.analyse.preproc.headers import SkippedSpan

# The two lists are copied verbatim, in the same order, from ubCode's
# ``rust/ubc_codelinks/src/preproc/decided.rs`` (``TARGET_IDENTITY`` and
# ``TARGET_DEFINEDNESS``), its twin: change both together.

TARGET_IDENTITY: tuple[str, ...] = (
    # Architecture.
    "__aarch64__",
    "__amd64",
    "__amd64__",
    "__arm__",
    "__AVR__",
    "__hexagon__",
    "__i386",
    "__i386__",
    "__loongarch__",
    "__m68k__",
    "__mips__",
    "__MSP430__",
    "__powerpc__",
    "__powerpc64__",
    "__PPC__",
    "__PPC64__",
    "__riscv",
    "__s390__",
    "__s390x__",
    "__sparc",
    "__sparc__",
    "__wasm__",
    "__wasm32__",
    "__wasm64__",
    "__x86_64",
    "__x86_64__",
    # Operating system, environment and object format.
    "__ANDROID__",
    "__APPLE__",
    "__CYGWIN__",
    "__ELF__",
    "__EMSCRIPTEN__",
    "__gnu_linux__",
    "__HAIKU__",
    "__linux",
    "__linux__",
    "__MACH__",
    "__MINGW32__",
    "__MINGW64__",
    "__NetBSD__",
    "__OpenBSD__",
    "__sun",
    "__unix__",
    "__wasi__",
    "_AIX",
    "_WIN32",
    "_WIN64",
    # Byte order.
    "__AARCH64EB__",
    "__AARCH64EL__",
    "__ARMEB__",
    "__ARMEL__",
    "__BYTE_ORDER__",
    "__CHAR_BIT__",
    "__MIPSEB__",
    "__MIPSEL__",
    "__ORDER_BIG_ENDIAN__",
    "__ORDER_LITTLE_ENDIAN__",
    "__ORDER_PDP_ENDIAN__",
)
"""The macros a stated target decides, value and all (:meth:`Stated.decides`): those
that GCC and clang, targeting one effective triple, both set or both leave unset, to one
value, whatever the entry's other flags (``-m``, ``-f``, ``-O``, ``-std``), so that the
triple the ``target`` setting names decides them as it decides the build's. Each is
decided whether clang predefines it for the parse (an arm on it is read as clang
evaluates it) or not. The triple is the build's EFFECTIVE one: ``-m32``, ``-mx32``,
``-mbig-endian``, ``-EB``, ``-EL`` or ``-mabi=`` change it, and a ``target`` that does
not name it decides wrongly.

- Architecture: the triple's first part (``arm``/``thumb*`` both define ``__arm__``;
  ``-mthumb``'s ``__thumb__`` is a flag's, so not listed). Not the spellings one
  compiler alone sets (clang's ``__arm64__`` off Apple, ``__ppc__`` off Darwin), nor
  those an ``-march`` or ``-mcpu`` decides (``__mips``, the ISA number; ``__mips64``;
  ``__sparc_v9__``).
- Operating system, environment and object format: the triple's other parts
  (``-linux-gnu``, ``-w64-mingw32``, ``-apple-darwin``, ``-none-eabi``), in the
  spellings both compilers set even under a strict ``-std`` (``__linux__``, not
  ``linux``), for the same triples (not ``__unix``, which clang does not set on NetBSD,
  nor ``__Fuchsia__``, GCC's being ``__fuchsia__``).
- Byte order: ``__BYTE_ORDER__`` and its ``__ORDER_*__`` constants, and the
  architectures' own (``__ARMEL__``, ``__AARCH64EB__``, ``__MIPSEL__``); not clang's
  ``__LITTLE_ENDIAN__`` and ``__BIG_ENDIAN__``, which GCC sets on few targets.

Every name is one clang predefines for some triple
(``test_clang_predefines_every_listed_name_for_some_triple``): one it never does would
be decided absent where GCC sets it (``__powerpc``, set by clang on AIX alone;
``__xtensa__``, a target the pinned libclang does not have).

Never here: the compiler's identity (``__clang__``, ``__GNUC__``, ``_MSC_VER``, and
clang's ``_ILP32``, ``__ILP32__``: the build's compiler is not clang), what a flag
decides (``-mcpu``, ``-mfpu``, ``-mfloat-abi``, ``-O``: ``__ARM_ARCH``, ``__ARM_FP``,
``__OPTIMIZE__``), the standard's (``__cplusplus``), every name a build may pass with
``-D``, and the data model's values (:data:`TARGET_DEFINEDNESS`)."""

TARGET_DEFINEDNESS: tuple[str, ...] = (
    "__FreeBSD__",
    "__LP64__",
    "__SIZEOF_INT__",
    "__SIZEOF_LONG__",
    "__SIZEOF_LONG_LONG__",
    "__SIZEOF_POINTER__",
    "__SIZEOF_PTRDIFF_T__",
    "__SIZEOF_SHORT__",
    "__SIZEOF_SIZE_T__",
    "_LP64",
    "_M_AMD64",
    "_M_ARM64",
    "_M_IX86",
    "_M_X64",
)
"""The macros a stated target decides the definedness of, never the value (``#ifdef
__LP64__`` decides; ``#if __SIZEOF_LONG__ == 8`` does not): the data model, whose sizes
a flag can change for one triple (``-mabi=ilp32``, ``-mlong32``, ``-mint8``), the MSVC
architecture macros, whose values the compiler's ``/arch`` decides, and
``__FreeBSD__``, whose value is the system's version. The effective-triple caveat of
:data:`TARGET_IDENTITY` holds too."""

_WORD_OPERATORS = frozenset(
    (
        "and",
        "and_eq",
        "bitand",
        "bitor",
        "compl",
        "not",
        "not_eq",
        "or",
        "or_eq",
        "xor",
        "xor_eq",
    )
)
"""The operators C++ spells as words."""

_IDENTITY = frozenset(TARGET_IDENTITY)
_DEFINEDNESS = frozenset(TARGET_DEFINEDNESS)


@dataclass(frozen=True)
class _Definition:
    """A stated macro's definition: a function-like one's parameters, and its value
    (``1`` for ``-DNAME``)."""

    parameters: tuple[str, ...]
    value: str


@dataclass
class Stated:
    """What the configuration of a header no entry includes states."""

    defines: dict[str, _Definition | None] = field(default_factory=dict)
    """The macros its arguments define (``-D``: their definition) or undefine (``-U``:
    ``None``), the last of each name."""
    target: bool = False
    """Whether the target is stated (the ``target`` setting): the macros of
    :data:`TARGET_IDENTITY` decide."""
    file_defined: set[str] = field(default_factory=set)
    """The macros a file of the parse defines: none of them is the target's."""

    @classmethod
    def of(cls, args: list[str], target: bool) -> Stated:
        """What ``args``, the parse's arguments, state, the target stated or not; a
        stated target's macros are added from the parse (:meth:`macros`)."""
        defines: dict[str, _Definition | None] = {}
        it = iter(args)
        for arg in it:
            if arg == "-D":
                operand, is_define = next(it, None), True
            elif arg == "-U":
                operand, is_define = next(it, None), False
            elif arg.startswith("-D"):
                operand, is_define = arg[2:], True
            elif arg.startswith("-U"):
                operand, is_define = arg[2:], False
            else:
                continue
            if operand is None:
                continue
            head, equals, value = operand.partition("=")
            if not equals:
                value = "1"
            name, paren, parameters = head.partition("(")
            name = name.strip()
            if not name:
                continue
            defines[name] = (
                _Definition(
                    tuple(p.strip() for p in parameters.rstrip(")").split(","))
                    if paren
                    else (),
                    value,
                )
                if is_define
                else None
            )
        return cls(defines, target)

    def macros(self, definitions: Iterable[tuple[str, bool]]) -> None:
        """The parse's macro definitions, by name and whether a file holds them
        (``False``: predefined, ``<built-in>`` or ``-D``): a file's is no longer the
        target's."""
        self.file_defined.update(name for name, in_file in definitions if in_file)

    def decides(
        self,
        read: tuple[str, bool],
        local: set[str] | frozenset[str],
        visiting: list[str] | None = None,
    ) -> bool:
        """Whether ``read``, a name and whether only its definedness is read (as
        ``defined(..)`` reads it), is decided, in a header that defines or undefines
        ``local``: a stated macro's value decided in turn (``visiting``: the stated
        macros whose values are being read, so that a cycle decides nothing)."""
        name, defined_only = read
        if name in local:
            return False
        if name in self.defines:
            definition = self.defines[name]
            if definition is None or defined_only:
                # Undefined (``-U``), or only its definedness is read.
                return True
            value = definition.value.strip()
            if not value or value.startswith(("<", '"')):
                # Nothing, or a header name (``__has_include(MACRO)``).
                return True
            visiting = [] if visiting is None else visiting
            if name in visiting:
                return False
            visiting.append(name)
            names_read = names(value)
            decided = names_read is not None and all(
                each[0] in definition.parameters or self.decides(each, local, visiting)
                for each in names_read
            )
            visiting.pop()
            return decided
        return (
            self.target
            and name not in self.file_defined
            and (name in _IDENTITY or (defined_only and name in _DEFINEDNESS))
        )


class Kind(enum.Enum):
    """What a directive is."""

    if_ = "if"
    """``#if``, ``#ifdef``, ``#ifndef``: a chain opens."""
    elif_ = "elif"
    """``#elif``, ``#elifdef``, ``#elifndef``, ``#else``: the chain's next arm."""
    endif = "endif"
    """``#endif``."""
    define = "define"
    """``#define``, ``#undef``: the name is the header's own."""


@dataclass(frozen=True)
class Directive:
    """One directive of interest of a header's text."""

    kind: Kind
    line: int
    """The line of its ``#``, 1-based."""
    hash: int
    """The raw byte offset of its ``#``."""
    text: str
    """What it tests, as an expression: an ``#ifdef X`` is ``defined(X)``, an ``#else``
    empty; a ``#define``'s name."""


def _is_word(byte: int) -> bool:
    return (
        0x30 <= byte <= 0x39
        or 0x41 <= byte <= 0x5A
        or 0x61 <= byte <= 0x7A
        or byte == 0x5F  # _
    )


def _is_word_char(char: str) -> bool:
    return char.isascii() and (char.isalnum() or char == "_")


def directives(data: bytes) -> list[Directive]:
    """The directives of ``data``, a header's raw text, in order: the conditionals and
    the ``#define``\\ s and ``#undef``\\ s, each with its logical line (splices joined,
    comments a space)."""
    found: list[Directive] = []
    at = 0
    line = [1]
    line_start = True
    size = len(data)
    while at < size:
        byte = data[at]
        if byte == 0x0A:  # \n
            line[0] += 1
            line_start = True
            at += 1
        elif byte == 0x0D:  # \r
            if data[at + 1 : at + 2] != b"\n":
                line[0] += 1
                line_start = True
            at += 1
        elif byte in (0x20, 0x09, 0x0B, 0x0C):
            at += 1
        elif byte == 0x5C and _splice(data, at) is not None:  # \
            line[0] += 1
            at = _splice(data, at) or at + 1
        elif byte == 0x2F and data[at + 1 : at + 2] == b"*":
            at = _block_comment(data, at, line)
        elif byte == 0x2F and data[at + 1 : at + 2] == b"/":
            at = _line_end(data, at, line)
        elif byte == 0x23 and line_start:  # #
            directive, at = _directive(data, at, 1, line)
            if directive is not None:
                found.append(directive)
        elif byte == 0x25 and line_start and data[at + 1 : at + 2] == b":":
            # The digraph of `#`.
            directive, at = _directive(data, at, 2, line)
            if directive is not None:
                found.append(directive)
        elif byte == 0x22:  # "
            line_start = False
            at = (
                _raw_string(data, at, line)
                if _raw_prefix(data, at)
                else _quoted(data, at, 0x22, line)
            )
        elif byte == 0x27:  # '
            line_start = False
            at = _quoted(data, at, 0x27, line)
        else:
            line_start = False
            at += 1
    return found


def _splice(data: bytes, at: int) -> int | None:
    """The end of the line splice (``\\`` and a line break) at ``at``, if one is."""
    following = data[at + 1 : at + 3]
    if following == b"\r\n":
        return at + 3
    if following[:1] in (b"\n", b"\r"):
        return at + 2
    return None


def _block_comment(data: bytes, at: int, line: list[int]) -> int:
    """Past the block comment that starts at ``at``, counting its lines."""
    at += 2
    while at < len(data):
        if data[at] == 0x2A and data[at + 1 : at + 2] == b"/":
            return at + 2
        _count_break(data, at, line)
        at += 1
    return at


def _count_break(data: bytes, at: int, line: list[int]) -> None:
    """Counts the line break at ``at``, if one is (a CRLF once)."""
    if data[at] == 0x0A or (data[at] == 0x0D and data[at + 1 : at + 2] != b"\n"):
        line[0] += 1


def _line_end(data: bytes, at: int, line: list[int]) -> int:
    """The line break that ends the logical line at ``at`` (splices joined), counting
    the lines it joins; the end of ``data`` when none does."""
    while at < len(data):
        byte = data[at]
        if byte in (0x0A, 0x0D):
            return at
        if byte == 0x5C and _splice(data, at) is not None:
            line[0] += 1
            at = _splice(data, at) or at + 1
        else:
            at += 1
    return at


def _quoted(data: bytes, at: int, quote: int, line: list[int]) -> int:
    """Past the literal quoted by ``quote`` that starts at ``at``: at its closing quote,
    or at the line break that ends it unclosed."""
    at += 1
    while at < len(data):
        byte = data[at]
        if byte == 0x5C and _splice(data, at) is not None:
            line[0] += 1
            at = _splice(data, at) or at + 1
        elif byte == 0x5C:
            at += 2
        elif byte in (0x0A, 0x0D):
            return at
        elif byte == quote:
            return at + 1
        else:
            at += 1
    return at


def _raw_prefix(data: bytes, at: int) -> bool:
    """Whether the ``"`` at ``at`` opens a raw string: ``R"``, ``LR"``, ``uR"``,
    ``UR"``, ``u8R"``, as a word of its own."""
    start = at
    while start > 0 and _is_word(data[start - 1]):
        start -= 1
    return data[start:at] in (b"R", b"LR", b"uR", b"UR", b"u8R")


def _raw_string(data: bytes, at: int, line: list[int]) -> int:
    """Past the raw string whose ``"`` is at ``at``, counting its lines."""
    opening = at + 1
    paren = data[opening : opening + 17].find(b"(")
    if paren < 0:
        return opening
    delimiter = data[opening : opening + paren]
    at = opening + paren + 1
    while at < len(data):
        if (
            data[at] == 0x29  # )
            and data[at + 1 :].startswith(delimiter)
            and data[at + 1 + len(delimiter) : at + 2 + len(delimiter)] == b'"'
        ):
            return at + len(delimiter) + 2
        _count_break(data, at, line)
        at += 1
    return at


def _directive(
    data: bytes, hash_at: int, width: int, line: list[int]
) -> tuple[Directive | None, int]:
    """The directive whose ``#`` (``width`` bytes: 2 for ``%:``) is at ``hash_at``, when
    it is one of interest, and where its logical line ends."""
    first = line[0]
    # Its logical line, splices joined and comments a space.
    text = bytearray()
    at = hash_at + width
    while at < len(data):
        byte = data[at]
        if byte in (0x0A, 0x0D):
            break
        if byte == 0x5C and _splice(data, at) is not None:
            line[0] += 1
            at = _splice(data, at) or at + 1
        elif byte == 0x2F and data[at + 1 : at + 2] == b"*":
            at = _block_comment(data, at, line)
            text.append(0x20)
        elif byte == 0x2F and data[at + 1 : at + 2] == b"/":
            at = _line_end(data, at, line)
        elif byte in (0x22, 0x27):
            end = _quoted(data, at, byte, line)
            text += data[at:end]
            at = end
        else:
            text.append(byte)
            at += 1
    # Byte for character: the names it reads are ASCII.
    logical = text.decode("latin-1").lstrip()
    name = _identifier(logical)
    rest = logical[len(name) :].strip()
    if name in ("if", "elif"):
        kind, condition = (Kind.if_ if name == "if" else Kind.elif_), rest
    elif name in ("ifdef", "elifdef"):
        kind = Kind.if_ if name == "ifdef" else Kind.elif_
        condition = f"defined({rest})"
    elif name in ("ifndef", "elifndef"):
        kind = Kind.if_ if name == "ifndef" else Kind.elif_
        condition = f"!defined({rest})"
    elif name == "else":
        kind, condition = Kind.elif_, ""
    elif name == "endif":
        kind, condition = Kind.endif, ""
    elif name in ("define", "undef"):
        kind, condition = Kind.define, _identifier(rest)
    else:
        return None, at
    return Directive(kind, first, hash_at, condition), at


def _identifier(text: str) -> str:
    """The identifier ``text`` starts with (empty when none)."""
    end = 0
    while end < len(text) and _is_word_char(text[end]):
        end += 1
    return text[:end]


def names(condition: str) -> list[tuple[str, bool]] | None:
    """The names ``condition`` reads, each with whether only its definedness is
    (``defined(X)`` reads ``X``'s), or ``None`` when the scan cannot read it (empty, or
    holding a string outside ``__has_include``). ``__has_include(<..>)`` and
    ``__has_include("..")`` read none; ``__has_include(MACRO)`` reads ``MACRO``."""
    read: list[tuple[str, bool]] = []
    tokens = 0
    at = 0
    size = len(condition)
    while at < size:
        char = condition[at]
        if char in " \t\n\x0c\r":
            at += 1
            continue
        tokens += 1
        if (char.isascii() and char.isalpha()) or char == "_":
            name = _identifier(condition[at:])
            at += len(name)
            if name in ("L", "u", "U", "u8") and condition[at : at + 1] == "'":
                # A character literal's prefix.
                pass
            elif name == "defined":
                rest = condition[at:].lstrip()
                if rest.startswith("("):
                    rest = rest[1:].lstrip()
                operand = _identifier(rest)
                if not operand:
                    return None
                read.append((operand, True))
                at = size - len(rest) + len(operand)
                # A `)` is an operator.
            elif name in ("__has_include", "__has_include_next"):
                # A header name decides; a macro operand is read on as names, its
                # parentheses operators.
                operand = condition[at:].lstrip()
                if not operand.startswith("("):
                    return None
                if operand[1:].lstrip().startswith(("<", '"')):
                    past = _past_parens(condition, at)
                    if past is None:
                        return None
                    at = past
            elif name in _WORD_OPERATORS:
                pass
            elif name.startswith("__has_"):
                read.append((name, False))
                past = _past_parens(condition, at)
                at = past if past is not None else at
            else:
                read.append((name, False))
        elif (char.isascii() and char.isdigit()) or (
            char == "." and condition[at + 1 : at + 2].isdigit()
        ):
            # A pp-number, its suffix and exponent's sign with it.
            at += 1
            while at < size:
                c = condition[at]
                sign = c in "+-" and condition[at - 1] in "eEpP"
                if _is_word_char(c) or c in ".'" or sign:
                    at += 1
                else:
                    break
        elif char == "'":
            at = _quoted_text(condition, at, "'")
        elif char == '"':
            return None
        else:
            at += 1
    return read if tokens > 0 else None


def _quoted_text(text: str, at: int, quote: str) -> int:
    """:func:`_quoted` over a condition's text, where no line break is left (a
    character beyond Latin-1, of a ``-D`` value, one byte as every other)."""
    return _quoted(text.encode("latin-1", errors="replace"), at, ord(quote), [0])


def _past_parens(text: str, at: int) -> int | None:
    """Past the parenthesised operand that follows ``at`` (whitespace first), nested
    parentheses included; ``None`` when none follows or it is unclosed."""
    while at < len(text) and text[at] in " \t\n\x0c\r":
        at += 1
    if text[at : at + 1] != "(":
        return None
    depth = 0
    while at < len(text):
        char = text[at]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return at + 1
        elif char == '"':
            at = _quoted_text(text, at, '"')
            continue
        at += 1
    return None


@dataclass(frozen=True)
class _Arm:
    """One arm of a conditional chain: its directive's line and ``#``, and whether it
    is decided (:func:`decided_ranges`)."""

    line: int
    hash: int
    decided: bool


def decided_ranges(
    data: bytes, skipped: Iterable[SkippedSpan], stated: Stated
) -> tuple[list[SkippedSpan], int]:
    """Of ``skipped``, the ranges the parse of the header whose raw text is ``data``
    skipped (each from the ``#`` of the directive that starts it to the line of the
    directive that ends it), the parts the configuration ``stated`` decides, and how
    many arms are read as written for a condition it does not decide.

    A range covers one arm, or several consecutive arms of one chain (those the
    preprocessor skipped in one go). It stays whole when every arm it covers is
    decided, is cut short before its first undecided arm, and is dropped when that is
    its first: an arm's decision only ever goes from decided to undecided along its
    chain, until an arm decided and taken decides every later one.
    """
    skipped = list(skipped)
    found = directives(data)
    local = frozenset(d.text for d in found if d.kind is Kind.define)

    def reads_stated(text: str) -> bool:
        read = names(text)
        return read is not None and all(stated.decides(each, local) for each in read)

    def is_skipped(line: int) -> bool:
        return any(span.start_line <= line < span.end_line for span in skipped)

    # Each chain's arms, and where each arm is by its line.
    chains: list[list[_Arm]] = []
    open_chains: list[int] = []
    by_line: dict[int, tuple[int, int]] = {}
    # Per open chain: every arm so far decided, and one decided and taken.
    state: list[list[bool]] = []
    for directive in found:
        if directive.kind is Kind.if_:
            chains.append([])
            open_chains.append(len(chains) - 1)
            state.append([True, False])
            chain = len(chains) - 1
        elif directive.kind is Kind.elif_:
            if not open_chains:
                continue
            chain = open_chains[-1]
        elif directive.kind is Kind.endif:
            if open_chains:
                open_chains.pop()
                state.pop()
            continue
        else:
            continue
        prefix_settled = state[-1]
        if prefix_settled[1]:
            decided = True
        else:
            prefix_settled[0] = prefix_settled[0] and (
                not directive.text or reads_stated(directive.text)
            )
            if prefix_settled[0] and not is_skipped(directive.line):
                prefix_settled[1] = True
            decided = prefix_settled[0]
        by_line[directive.line] = (chain, len(chains[chain]))
        chains[chain].append(_Arm(directive.line, directive.hash, decided))
    kept: list[SkippedSpan] = []
    undecided = 0
    for span in skipped:
        where = by_line.get(span.start_line)
        if where is None:
            # No directive the scan found starts it: read as written.
            undecided += 1
            continue
        chain, first = where
        cut: _Arm | None = None
        for arm in chains[chain][first:]:
            if not (arm.line == span.start_line or arm.line < span.end_line):
                break
            if not arm.decided:
                if cut is None:
                    cut = arm
                undecided += 1
        if cut is None:
            kept.append(span)
        elif cut.line != span.start_line:
            kept.append(
                SkippedSpan(
                    span.start_byte,
                    max(cut.hash, span.start_byte),
                    span.start_line,
                    cut.line,
                )
            )
    return kept, undecided
