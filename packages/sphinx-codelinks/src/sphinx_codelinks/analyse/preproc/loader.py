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

import ctypes
import enum
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
                    f, start.line, start.column, end.line, end.column, from_main
                )
            )
        return out
    finally:
        cx.conf.lib.clang_disposeSourceRangeList(ptr)
