"""Import guard for clang.cindex + ctypes shim for clang_getAllSkippedRanges.

clang.cindex (shipped by the PyPI ``libclang`` wheel, which bundles the native
library — no compiler required) does not expose clang_getAllSkippedRanges, so
we bind it via ctypes, exactly as the design concept's _common.py did. Nor do
the 16.0 and 18.1 bindings expose clang_Location_isFromMainFile or
clang_getSkippedRanges, which both wheels' native libraries export: they are bound
the same way. And their ``Cursor.get_included_file`` asserts on the NULL that
clang_getIncludedFile returns for an ``#include`` libclang could not resolve, so
:func:`included_file` reads it through a binding of its own. And their
``TranslationUnit.from_source`` raises the same ``TranslationUnitLoadError`` whatever
libclang reported, so :func:`parse_translation_unit` parses through
clang_parseTranslationUnit2, which says why (:class:`ParseError`).
"""

from __future__ import annotations

import bisect
import ctypes
import enum
import os
import re
from pathlib import Path
from typing import Any, NamedTuple

_INSTALL_HINT = (
    "The libclang engine requires clang.cindex. Install the extra:\n"
    "    pip install 'sphinx-codelinks[libclang]'"
)


# @Guard the optional libclang dependency with an install hint, IMPL_PREPROC_6, impl, [FE_PREPROC]
def load_clang_cindex() -> Any:
    """Return the clang.cindex module or raise a clear install error."""
    try:
        import clang.cindex as cx
    except ImportError as exc:  # pragma: no cover - exercised via patched import
        raise ImportError(_INSTALL_HINT) from exc
    return cx


# Production parse flags (design "Parse flags codelinks should use").
def _parse_options() -> int:
    cx = load_clang_cindex()
    # ``cx`` is untyped (clang ships no stubs), so the bit-or is ``Any``; coerce
    # back to ``int`` to satisfy the declared return type.
    return int(
        cx.TranslationUnit.PARSE_INCOMPLETE
        | cx.TranslationUnit.PARSE_SKIP_FUNCTION_BODIES
        | cx.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD
    )


PARSE_OPTIONS: int = _parse_options()


class SkippedRange(NamedTuple):
    file: Path | None
    start_line: int
    start_col: int
    end_line: int
    end_col: int
    from_main_file: bool
    """Whether the range starts in the translation unit's main file, in the main
    file's own pass: a later inclusion of the same path is a pass of its own, and
    reports ``False`` here (``clang_Location_isFromMainFile``)."""
    start_offset: int = 0
    """The byte offset of its start in its file, as written (raw bytes)."""
    end_offset: int = 0
    """The byte offset of its end in its file, as written: the end of the directive's
    keyword that closes it."""
    entry: int = -1
    """Which entry of its file it is in (:func:`entry_base`)."""


class _CXSourceRangeList(ctypes.Structure):
    pass


_BOUND = False
_INCLUDED_FILE: Any = None
_PARSE2: Any = None


class ParseError(enum.IntEnum):
    """Why libclang refused a parse: the ``CXErrorCode`` clang_parseTranslationUnit2
    returns, as :func:`parse_translation_unit` attaches it to the error it raises
    (:func:`parse_error`)."""

    failure = 1
    """``CXError_Failure``: as the pinned libclang reports a flag the target does not
    take (``-mfpmath=vfp``) or a target it does not model."""
    crashed = 2
    """``CXError_Crashed``: libclang crashed."""
    invalid_arguments = 3
    """``CXError_InvalidArguments``: the call itself was invalid."""
    ast_read_error = 4
    """``CXError_ASTReadError``: as the pinned libclang reports a command it does not
    run at all, whatever the target: a second input file, a ``-std`` it does not know,
    an unknown ``-Xclang`` flag."""


_ERROR_CODE = "codelinks_parse_error"
"""The attribute of a ``TranslationUnitLoadError`` that holds its :class:`ParseError`."""


def parse_translation_unit(file_path: Path, args: list[str], options: int) -> Any:
    """``file_path`` parsed by a new index with ``args`` and ``options``, as
    ``clang.cindex``'s ``Index.parse`` parses it, but through
    clang_parseTranslationUnit2, which says why libclang refused it.

    :raises clang.cindex.TranslationUnitLoadError: libclang could not load it; the
        error carries libclang's reason (:func:`parse_error`).
    """
    global _PARSE2
    cx = load_clang_cindex()
    if _PARSE2 is None:
        # A function pointer of its own (``CDLL.__getitem__`` makes a new one).
        function = cx.conf.lib["clang_parseTranslationUnit2"]
        function.argtypes = [
            cx.Index,
            ctypes.c_char_p,
            ctypes.POINTER(ctypes.c_char_p),
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_uint,
            ctypes.c_uint,
            ctypes.POINTER(cx.c_object_p),
        ]
        function.restype = ctypes.c_int
        _PARSE2 = function
    index = cx.Index.create()
    # encoded as ``clang.cindex`` encodes them
    arguments = (ctypes.c_char_p * len(args))(*(arg.encode("utf-8") for arg in args))
    unit = cx.c_object_p()
    code = _PARSE2(
        index,
        str(file_path).encode("utf-8"),
        arguments,
        len(args),
        None,
        0,
        options,
        ctypes.byref(unit),
    )
    if code == 0 and unit:
        return cx.TranslationUnit(unit, index=index)
    error = cx.TranslationUnitLoadError("Error parsing translation unit.")
    try:
        reason: ParseError | None = ParseError(code)
    except ValueError:
        reason = None
    setattr(error, _ERROR_CODE, reason)
    raise error


def parse_error(error: BaseException | None) -> ParseError | None:
    """Why libclang refused the parse that raised ``error``
    (:func:`parse_translation_unit`); ``None`` when it does not say (an error raised
    some other way)."""
    reason = getattr(error, _ERROR_CODE, None)
    return reason if isinstance(reason, ParseError) else None


def refused_by_command(error: BaseException | None) -> bool:
    """Whether libclang refused the parse that raised ``error`` for its command
    itself, whatever the target (``CXError_ASTReadError``, or a crash: a second input
    file, a ``-std`` it does not know, an ``-Xclang`` flag), rather than for its target
    with a flag (``CXError_Failure``: ``-mfpmath=vfp``), as measured with the pinned
    libclang. An error that does not say is the target's (:func:`parse_error`)."""
    return parse_error(error) in (ParseError.ast_read_error, ParseError.crashed)


def _bind() -> None:
    global _BOUND
    if _BOUND:
        return
    cx = load_clang_cindex()
    _CXSourceRangeList._fields_ = [
        ("count", ctypes.c_uint),
        ("ranges", ctypes.POINTER(cx.SourceRange)),
    ]
    lib = cx.conf.lib
    lib.clang_getAllSkippedRanges.argtypes = [ctypes.c_void_p]
    lib.clang_getAllSkippedRanges.restype = ctypes.POINTER(_CXSourceRangeList)
    lib.clang_getSkippedRanges.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    lib.clang_getSkippedRanges.restype = ctypes.POINTER(_CXSourceRangeList)
    lib.clang_disposeSourceRangeList.argtypes = [ctypes.POINTER(_CXSourceRangeList)]
    lib.clang_disposeSourceRangeList.restype = None
    # Registered as cindex registers clang_Location_isInSystemHeader, but with a
    # ctypes restype rather than ``bool`` (a non-ctypes restype is deprecated).
    lib.clang_Location_isFromMainFile.argtypes = [cx.SourceLocation]
    lib.clang_Location_isFromMainFile.restype = ctypes.c_int
    _BOUND = True


def entry_base(location: Any) -> int:
    """Which entry of its file a location of a translation unit is in: the start of
    that entry in the unit's source-location space (its raw encoding less its offset in
    the file). Each entry of a file (``#include``, ``-include``) is a file ID of its
    own, which ``clang_getSkippedRanges`` and the file's line and offset do not tell
    apart."""
    return int(location.int_data) - int(location.offset)


def first_entry_base(tu: Any, file: Any) -> int:
    """:func:`entry_base` of ``file``'s first entry into ``tu`` (``clang_getLocation``
    names a location in the first)."""
    return entry_base(looked_up(tu, file, line=1))


_SLOW_LOOKUPS = 0


def looked_up(
    tu: Any, file: Any, *, line: int | None = None, offset: int | None = None
) -> Any:
    """The location of ``file``'s first entry into ``tu`` at ``line`` (column 1) or at
    ``offset``, looked up (``clang_getLocation`` / ``clang_getLocationForOffset``), and
    counted (:func:`slow_lookups`).

    The one place a location is looked up. Both calls map what they find through the
    macro-argument table of the file's first entry, which libclang builds on the first
    lookup in it: a walk of every macro expansion there, minutes for a macro-heavy header
    (about two for Zephyr's ``ctf_top.h``, useblocks/ubcode#4982). A file the unit
    entered once has its locations made from where its entry starts instead
    (:func:`entry_starts`).
    """
    global _SLOW_LOOKUPS
    cx = load_clang_cindex()
    _SLOW_LOOKUPS += 1
    if offset is not None:
        return cx.SourceLocation.from_offset(tu, file, offset)
    return cx.SourceLocation.from_position(tu, file, line, 1)


def slow_lookups() -> int:
    """How many locations :func:`looked_up` has looked up in this process."""
    return _SLOW_LOOKUPS


_MACRO_BIT = 0x80000000
"""The bit of a raw source-location encoding that marks a macro location."""


class _CXFileUniqueID(ctypes.Structure):
    _fields_ = [("data", ctypes.c_ulonglong * 3)]


class _CXTUResourceUsageEntry(ctypes.Structure):
    _fields_ = [("kind", ctypes.c_int), ("amount", ctypes.c_ulong)]


class _CXTUResourceUsage(ctypes.Structure):
    _fields_ = [
        ("data", ctypes.c_void_p),
        ("numEntries", ctypes.c_uint),
        ("entries", ctypes.POINTER(_CXTUResourceUsageEntry)),
    ]


_EXTERNAL_AST_SOURCE_MEMORY = (9, 10)
"""``CXTUResourceUsage_ExternalASTSource_Membuffer_Malloc`` and ``…_MMap``."""

_OWN_FUNCTIONS: dict[str, Any] = {}


def _call(name: str) -> Any:
    """libclang's ``name``, as a function pointer of its own (``CDLL.__getitem__``
    makes a new one), so that a binding ``clang.cindex`` makes of the same function is
    left as it is; bound on first use, for what :func:`entry_starts` calls."""
    if name in _OWN_FUNCTIONS:
        return _OWN_FUNCTIONS[name]
    cx = load_clang_cindex()
    signatures: dict[str, tuple[list[Any], Any]] = {
        "clang_getFileUniqueID": (
            [ctypes.c_void_p, ctypes.POINTER(_CXFileUniqueID)],
            ctypes.c_int,
        ),
        "clang_getFileContents": (
            [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t)],
            ctypes.c_void_p,
        ),
        "clang_getCXTUResourceUsage": ([ctypes.c_void_p], _CXTUResourceUsage),
        "clang_disposeCXTUResourceUsage": ([_CXTUResourceUsage], None),
        "clang_getFileLocation": (
            [
                cx.SourceLocation,
                ctypes.POINTER(ctypes.c_void_p),
                ctypes.POINTER(ctypes.c_uint),
                ctypes.POINTER(ctypes.c_uint),
                ctypes.POINTER(ctypes.c_uint),
            ],
            None,
        ),
    }
    function = cx.conf.lib[name]
    function.argtypes, function.restype = signatures[name]
    _OWN_FUNCTIONS[name] = function
    return function


def file_id(file: Any) -> tuple[int, int, int] | None:
    """``file``'s identity (``clang_getFileUniqueID``: its device and inode), which a
    location lookup goes by (``SourceManager::translateFile``), whatever name it was
    found under; ``None`` when libclang cannot tell."""
    unique = _CXFileUniqueID()
    if _call("clang_getFileUniqueID")(_pointer(file), ctypes.byref(unique)) != 0:
        return None
    return (unique.data[0], unique.data[1], unique.data[2])


def _pointer(file: Any) -> Any:
    """The ``CXFile`` of a ``clang.cindex.File``."""
    return file.from_param() if hasattr(file, "from_param") else file


def file_contents(tu: Any, file: Any) -> bytes | None:
    """The bytes clang read for ``file`` in ``tu`` (``clang_getFileContents``)."""
    size = ctypes.c_size_t()
    data = _call("clang_getFileContents")(tu.obj, _pointer(file), ctypes.byref(size))
    if not data:
        return None
    return ctypes.string_at(data, size.value)


def _file_location(location: Any) -> tuple[int, int] | None:
    """The ``CXFile`` and offset a FILE location of a unit is at
    (``clang_getFileLocation``); ``None`` for a macro location, or one in no file."""
    if int(location.int_data) & _MACRO_BIT:
        return None
    file, offset = ctypes.c_void_p(), ctypes.c_uint()
    _call("clang_getFileLocation")(
        location, ctypes.byref(file), None, None, ctypes.byref(offset)
    )
    if not file.value:
        return None
    return file.value, offset.value


def _decoded(location: Any) -> tuple[tuple[int, int, int] | None, int] | None:
    """The file (:func:`file_id`) and offset a FILE location of a unit is at; ``None``
    for a macro location, or one in no file."""
    at = _file_location(location)
    return None if at is None else (file_id(at[0]), at[1])


def _in_entry(begin: Any, offset: int, file: int) -> bool:
    """Whether ``offset`` bytes past ``begin``, a location at the start of an entry of
    the ``CXFile`` ``file``, is still in that entry."""
    cx = load_clang_cindex()
    made = cx.SourceLocation()
    made.ptr_data = begin.ptr_data
    made.int_data = int(begin.int_data) + offset
    return _file_location(made) == (file, offset)


def _entry_end(location: Any, file: int, offset: int) -> int:
    """The last offset of the entry ``location`` is in, at ``offset`` of the ``CXFile``
    ``file``: an entry spans ``[start, start + size]``, the next starts after it.
    Found by probing (``clang_getFileLocation``), never ``clang_getFileContents``,
    whose ``SourceManager::translateFile`` walks every entry of the unit: milliseconds
    a call in a unit of many macro expansions."""
    cx = load_clang_cindex()
    begin = cx.SourceLocation()
    begin.ptr_data = location.ptr_data
    begin.int_data = int(location.int_data) - offset
    inside, step = offset, 1
    while _in_entry(begin, inside + step, file):
        inside += step
        step *= 2
    outside = inside + step
    while outside - inside > 1:
        middle = (inside + outside) // 2
        if _in_entry(begin, middle, file):
            inside = middle
        else:
            outside = middle
    return inside


def entry_has(start: Any, size: int) -> bool:
    """Whether the entry ``start`` (a location at offset 0, :func:`entry_starts`)
    begins holds exactly ``size`` bytes: its last offset is ``size``."""
    at = _file_location(start)
    if at is None or at[1] != 0:
        return False
    return _in_entry(start, size, at[0]) and not _in_entry(start, size + 1, at[0])


def unchanged_since_parse(file: Any, path: Path) -> bool:
    """Whether ``path``, the file ``file`` of a unit, still has the modification time,
    in whole seconds, it had when the unit read it (``clang_getFileUniqueID``'s third
    word). A file that cannot be stat'ed is taken as changed. A rewrite within the
    second of the parse is not seen."""
    key = file_id(file)
    try:
        mtime = os.stat(path).st_mtime_ns // 1_000_000_000
    except OSError:
        return False
    return key is not None and key[2] == mtime


def _empty_on_disk(file: Any) -> bool:
    """Whether ``file``, named by an absolute path, is an empty file on disk; ``False``
    for a relative name (relative to a working directory this does not know)."""
    name = file.name
    try:
        return os.path.isabs(name) and os.path.getsize(name) == 0
    except OSError:
        return False


def loads_an_ast_file(tu: Any) -> bool:
    """Whether ``tu`` loaded an AST file (a precompiled header, a Clang module): whether
    its external AST source holds any memory (``clang_getCXTUResourceUsage``). A loaded
    file's entries are not the unit's own: ``clang_getInclusions`` does not list them,
    so no file's count of entries is known there, and every location is looked up."""
    usage = _call("clang_getCXTUResourceUsage")(tu.obj)
    try:
        return any(
            usage.entries[i].kind in _EXTERNAL_AST_SOURCE_MEMORY
            and usage.entries[i].amount > 0
            for i in range(usage.numEntries if usage.entries else 0)
        )
    finally:
        _call("clang_disposeCXTUResourceUsage")(usage)


class Inclusion(NamedTuple):
    """One entry of a file into a translation unit (``clang_getInclusions``)."""

    file: Any
    """The ``clang.cindex.File`` entered."""
    stack: tuple[Any, ...]
    """Where it was entered from, innermost first: the ``#include`` in its includer,
    then that file's, up to the main file; empty for the main file itself. Copied
    while libclang hands them out."""


class Inclusions(list[Inclusion]):
    """:func:`inclusions`' list, and whether it holds every entry."""

    complete: bool = True
    """``False`` when an entry could not be read: then no file's count of entries is
    known, and :func:`entry_starts` makes no start."""


_COSTS = {"inclusions": 0, "walks": 0, "cursors": 0}


def costs() -> dict[str, int]:
    """How many times this process listed a unit's inclusions (:func:`inclusions`),
    walked a unit's top-level cursors for anchors (:func:`entry_starts`), and how many
    cursors those walks took."""
    return dict(_COSTS)


def inclusions(tu: Any) -> Inclusions:
    """Every entry of a file into ``tu``, in the order the unit made them, the main
    file's first.

    ``clang.cindex``'s ``TranslationUnit.get_includes`` keeps ``lptr.contents``, a view
    of the stack libclang reuses for every entry and frees when the call returns, so
    its ``FileInclusion.location`` reads freed memory once the call is over (never read
    it); here each location is copied inside the callback. An exception there would be
    printed and swallowed by ctypes, losing the entry: it marks the list incomplete
    instead (:attr:`Inclusions.complete`).
    """
    cx = load_clang_cindex()
    _COSTS["inclusions"] += 1
    out = Inclusions()

    def visit(file: Any, stack: Any, depth: int, _data: Any) -> None:
        try:
            out.append(
                Inclusion(
                    cx.File(file),
                    tuple(
                        cx.SourceLocation.from_buffer_copy(stack[k])
                        for k in range(depth)
                    ),
                )
            )
        except Exception:  # ctypes would print and swallow it: fail closed
            out.complete = False

    callback = cx.callbacks["translation_unit_includes"](visit)
    cx.conf.lib.clang_getInclusions(tu, callback, None)
    return out


def entry_starts(
    tu: Any, wanted: list[Any], entered: Inclusions | None = None
) -> dict[tuple[int, int, int], Any]:
    """The location at offset 0 of each of ``wanted`` (``clang.cindex.File``\\ s) that
    ``tu`` entered once, made from a location the unit already hands out in it, with no
    lookup (:func:`looked_up`), by :func:`file_id`.

    A file location less its offset is where its entry starts (:func:`entry_base`); in
    a file entered once that is the start :func:`looked_up` would give. The anchors are
    sought in order, only while a wanted file is without one: (a) the ``#include``\\ s
    the inclusion stacks hold (:func:`inclusions`), (b) the unit's extent (its main file),
    (c) the skipped ranges' starts and ends, (d) the top-level cursors (the
    preprocessing record and the declarations), the walk stopping once every wanted
    file with any bytes has one. A made location is kept only if it decodes to its file
    at offset 0 and is no macro location. A file entered more than once, an empty file
    with no anchor and every file of a unit that loaded an AST file
    (:func:`loads_an_ast_file`) have none: they are looked up.

    Each call lists the unit's inclusions and may walk its cursors once: a caller
    that reads several files through one unit asks once, for all of them, and keeps
    what it gets while the unit lives (a made location is a location of ``tu``).

    :param entered: :func:`inclusions` of ``tu``, if the caller has them.
    """
    if loads_an_ast_file(tu):
        return {}
    cx = load_clang_cindex()
    entered = inclusions(tu) if entered is None else entered
    if not entered.complete:
        return {}
    entries: dict[tuple[int, int, int] | None, int] = {}
    for inclusion in entered:
        key = file_id(inclusion.file)
        entries[key] = entries.get(key, 0) + 1
    missing: dict[tuple[int, int, int], Any] = {}
    for file in wanted:
        key = file_id(file)
        if key is not None and entries.get(key) == 1:
            missing[key] = file
    starts: dict[tuple[int, int, int], Any] = {}

    def offer(location: Any) -> None:
        at = _decoded(location)
        if at is None or at[0] not in missing:
            return
        made = cx.SourceLocation()
        made.ptr_data = location.ptr_data
        made.int_data = int(location.int_data) - at[1]
        # always so for a file location less its own offset: a guard against a
        # libclang whose encoding of a location is not its entry's start plus it
        if _decoded(made) == (at[0], 0):
            starts[at[0]] = made
            del missing[at[0]]

    # every #include of the unit is the innermost location of the entry it made
    for inclusion in entered:
        if not missing:
            return starts
        if inclusion.stack:
            offer(inclusion.stack[0])
    if missing:
        offer(tu.cursor.extent.start)
    if missing:
        _bind()
        ranges = cx.conf.lib.clang_getAllSkippedRanges(tu.obj)
        if ranges:
            try:
                for i in range(ranges.contents.count):
                    if not missing:
                        break
                    offer(ranges.contents.ranges[i].start)
                    offer(ranges.contents.ranges[i].end)
            finally:
                cx.conf.lib.clang_disposeSourceRangeList(ranges)
    # an empty file holds no location: it is looked up, which costs nothing there
    sought = {key for key, file in missing.items() if not _empty_on_disk(file)}
    if sought and not _walk(tu, sought, missing, offer):
        return {}
    return starts


_CONTINUE, _BREAK = 1, 0
"""``CXChildVisit_Continue`` and ``CXChildVisit_Break``."""


def _walk(
    tu: Any,
    sought: set[tuple[int, int, int]],
    missing: dict[tuple[int, int, int], Any],
    offer: Any,
) -> bool:
    """Offer the location of the first top-level cursor (``clang_visitChildren`` of the
    unit: its preprocessing record and declarations) in each entry of a file, until
    every file in ``sought`` has a start (it leaves ``missing``).

    Each entry is decoded once (``clang_getFileLocation``): a cursor whose raw location
    falls in an entry already seen, ``[start, start + size]``, is passed over without a
    call, as is a macro location. ``False`` when the walk failed: an exception inside
    the callback, which stops it.
    """
    cx = load_clang_cindex()
    location_of = cx.conf.lib.clang_getCursorLocation
    bisect_right = bisect.bisect_right
    _COSTS["walks"] += 1
    # the entries seen, sorted by start, and where each ends; the last one seen first,
    # as consecutive cursors are mostly in one entry
    begins: list[int] = []
    ends: list[int] = []
    last = [1, 0]
    visited = [0]

    def seen(location: Any, raw: int) -> None:
        """Note the entry ``location`` is in, and offer it."""
        at = _file_location(location)
        if at is None:
            return
        begin = raw - at[1]
        end = begin + _entry_end(location, at[0], at[1])
        i = bisect.bisect_left(begins, begin)
        begins.insert(i, begin)
        ends.insert(i, end)
        last[0], last[1] = begin, end
        offer(location)
        sought.intersection_update(missing.keys())

    failed = [False]

    def visit(cursor: Any, _parent: Any, _data: Any) -> int:
        try:
            visited[0] += 1
            location = location_of(cursor)
            raw = location.int_data
            if raw & _MACRO_BIT or last[0] <= raw <= last[1]:
                return _CONTINUE
            i = bisect_right(begins, raw) - 1
            if i >= 0 and raw <= ends[i]:
                last[0], last[1] = begins[i], ends[i]
                return _CONTINUE
            seen(location, raw)
        except Exception:  # ctypes would print and swallow it, per cursor: fail closed
            failed[0] = True
            return _BREAK
        return _CONTINUE if sought else _BREAK

    cx.conf.lib.clang_visitChildren(
        tu.cursor, cx.callbacks["cursor_visit"](visit), None
    )
    _COSTS["cursors"] += visited[0]
    return not failed[0]


_LINE_BREAK = re.compile(rb"\r\n?|\n")
"""A line break as clang counts one: ``\\r\\n``, a lone ``\\r`` or ``\\n``."""


def line_offset(contents: bytes, line: int) -> int:
    """The offset of ``line`` (1-based), column 1, in a file whose bytes are
    ``contents``, where clang places it (``SourceManager::translateLineCol``): a line
    starts after ``\\n``, ``\\r`` or ``\\r\\n``, and a line past the last is the file's
    last byte (its offset 0 when it is empty)."""
    if line == 1:
        return 0
    breaks = contents.count(b"\n") + contents.count(b"\r") - contents.count(b"\r\n")
    if line > breaks + 1:
        return max(len(contents) - 1, 0)
    if line == breaks + 1:  # the last line, the one a whole file's range ends at
        return max(contents.rfind(b"\n"), contents.rfind(b"\r")) + 1
    for number, found in enumerate(_LINE_BREAK.finditer(contents), start=2):
        if number == line:
            return found.end()
    return max(len(contents) - 1, 0)  # pragma: no cover -- counted above


def made_at(start: Any, offset: int) -> Any | None:
    """The location ``offset`` bytes into the entry that ``start`` (a location at
    offset 0, :func:`entry_starts`) begins, if it decodes to that file at that offset,
    else ``None``. The engine asks only for offsets within the bytes clang read, which
    always decode so: the check guards against a libclang whose encoding of a location
    is not its entry's start plus the offset."""
    cx = load_clang_cindex()
    made = cx.SourceLocation()
    made.ptr_data = start.ptr_data
    made.int_data = int(start.int_data) + offset
    begin = _decoded(start)
    if begin is None or _decoded(made) != (begin[0], offset):
        return None
    return made


def included_file(cursor: Any) -> Path | None:
    """The file an inclusion-directive cursor includes, or ``None`` when libclang did
    not find it (``<stddef.h>`` without clang's builtin headers, a header not generated
    yet).

    The name is the one libclang knows the file by: relative to the unit's working
    directory when it was found through a relative include directory.
    """
    global _INCLUDED_FILE
    cx = load_clang_cindex()
    if _INCLUDED_FILE is None:
        # A function pointer of its own (``CDLL.__getitem__`` makes a new one), so
        # the ``clang.cindex`` binding of the same function is left as it is.
        function = cx.conf.lib["clang_getIncludedFile"]
        function.argtypes = [cx.Cursor]
        function.restype = ctypes.c_void_p
        _INCLUDED_FILE = function
    pointer = _INCLUDED_FILE(cursor)
    if not pointer:
        return None
    return Path(cx.File(ctypes.cast(pointer, cx.c_object_p)).name)


def get_all_skipped_ranges(tu: Any) -> list[SkippedRange]:
    """Return every source range the preprocessor skipped in this TU."""
    _bind()
    cx = load_clang_cindex()
    return _read_range_list(cx, cx.conf.lib.clang_getAllSkippedRanges(tu.obj))


def get_first_inclusion_skipped_ranges(tu: Any, file: Any) -> list[SkippedRange]:
    """Return the ranges the preprocessor skipped in ``file``'s FIRST pass.

    ``clang_getSkippedRanges`` selects the ranges of one file ID, the one the source
    manager gives for the file (``SourceManager::translateFile``): its first inclusion
    in the translation unit. A later inclusion of the same file is a file ID of its
    own, and its ranges are not returned.

    :param tu: The parsed translation unit.
    :param file: A ``clang.cindex.File`` of ``tu`` (``tu.get_file``).
    """
    _bind()
    cx = load_clang_cindex()
    return _read_range_list(cx, cx.conf.lib.clang_getSkippedRanges(tu.obj, file))


def _read_range_list(cx: Any, ptr: Any) -> list[SkippedRange]:
    """Read and dispose of a ``CXSourceRangeList``."""
    if not ptr:
        return []
    try:
        rl = ptr.contents
        out: list[SkippedRange] = []
        for i in range(rl.count):
            r = rl.ranges[i]
            start = r.start
            end = r.end
            f = Path(start.file.name) if start.file else None
            from_main = bool(cx.conf.lib.clang_Location_isFromMainFile(start))
            out.append(
                SkippedRange(
                    f,
                    start.line,
                    start.column,
                    end.line,
                    end.column,
                    from_main,
                    start.offset,
                    end.offset,
                    entry_base(start),
                )
            )
        return out
    finally:
        cx.conf.lib.clang_disposeSourceRangeList(ptr)
