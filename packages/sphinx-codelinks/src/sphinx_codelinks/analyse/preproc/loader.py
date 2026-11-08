"""Import guard for clang.cindex + ctypes shim for clang_getAllSkippedRanges.

clang.cindex (shipped by the PyPI ``libclang`` wheel, which bundles the native
library — no compiler required) does not expose clang_getAllSkippedRanges, so
we bind it via ctypes, exactly as the design concept's _common.py did. Nor do
the 16.0 and 18.1 bindings expose clang_Location_isFromMainFile or
clang_getSkippedRanges, which both wheels' native libraries export: they are bound
the same way. And their ``Cursor.get_included_file`` asserts on the NULL that
clang_getIncludedFile returns for an ``#include`` libclang could not resolve, so
:func:`included_file` reads it through a binding of its own.
"""

from __future__ import annotations

import ctypes
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


class _CXSourceRangeList(ctypes.Structure):
    pass


_BOUND = False
_INCLUDED_FILE: Any = None


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


def included_file(cursor: Any) -> Path | None:
    """The file an inclusion-directive cursor includes, or ``None`` when libclang did
    not find it (``<stddef.h>`` without the builtin headers, a header not generated
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
                    f, start.line, start.column, end.line, end.column, from_main
                )
            )
        return out
    finally:
        cx.conf.lib.clang_disposeSourceRangeList(ptr)
