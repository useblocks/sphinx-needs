"""Import guard for clang.cindex + ctypes shim for clang_getAllSkippedRanges.

clang.cindex (shipped by the PyPI ``libclang`` wheel, which bundles the native
library — no compiler required) does not expose clang_getAllSkippedRanges, so
we bind it via ctypes, exactly as the design concept's _common.py did.
"""

from __future__ import annotations

import ctypes
from pathlib import Path
from typing import Any, NamedTuple

_INSTALL_HINT = (
    "The libclang engine requires clang.cindex. Install the extra:\n"
    "    pip install 'sphinx-codelinks[libclang]'"
)


def load_clang_cindex() -> Any:  # type: ignore[explicit-any]
    """Return the clang.cindex module or raise a clear install error."""
    try:
        import clang.cindex as cx  # noqa: PLC0415
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


class _CXSourceRangeList(ctypes.Structure):
    pass


_BOUND = False


def _bind() -> None:
    global _BOUND  # noqa: PLW0603
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
    lib.clang_disposeSourceRangeList.argtypes = [ctypes.POINTER(_CXSourceRangeList)]
    lib.clang_disposeSourceRangeList.restype = None
    _BOUND = True


def get_all_skipped_ranges(tu: Any) -> list[SkippedRange]:  # type: ignore[explicit-any]
    """Return every source range the preprocessor skipped in this TU."""
    _bind()
    cx = load_clang_cindex()
    ptr = cx.conf.lib.clang_getAllSkippedRanges(tu.obj)
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
            out.append(SkippedRange(f, start.line, start.column, end.line, end.column))
        return out
    finally:
        cx.conf.lib.clang_disposeSourceRangeList(ptr)
