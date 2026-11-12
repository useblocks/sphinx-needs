"""clang's builtin headers, passed to libclang as ``-resource-dir``.

``stddef.h``, ``stdarg.h``, ``stdbool.h``, ``float.h``, ``stdatomic.h``, the compiler's
half of ``limits.h`` and, where no C library is on the search path (a bare-metal
target), ``stdint.h`` come with the compiler, not with the C library. The ``libclang``
wheel carries none of them, and libclang looks for them relative to the working
directory of the parse, so without help every ``#include`` of one fails, and an ``#if``
on what it defines (``UINT32_MAX``, ``INT_MAX``, ``__has_include(<stdatomic.h>)``,
``bool``) takes the branch the compiler does not take.

So the package ships clang's 30 portable builtin headers, from the LLVM release of the
``libclang`` it is tested with (``clang_resource/manifest.toml`` names the tag and each
file's sha256; ``clang_resource/LICENSE.TXT`` is their licence). Every parse is handed a
resource directory, the first that applies:

1. ``resource_dir`` of the ``preprocessor`` configuration, when set;
2. none, when the arguments already choose (``-resource-dir``, ``-nostdinc``,
   ``-nobuiltininc``): the build's own choice stands;
3. the headers that ship with the package, read where they are installed;
4. none, when those are not on the filesystem (the package is imported from an archive,
   or the files were removed): the analysis warns once and parses without them.

A builtin header that is still missing after that (an intrinsics header such as
``immintrin.h``, which is not shipped) is warned about once per parsed file, naming it
and the setting that fixes it.
"""

from __future__ import annotations

import re
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

#: The headers under ``clang_resource/include`` (``tests/test_builtin_headers.py`` holds
#: the directory and the manifest to this list).
BUILTIN_HEADERS: frozenset[str] = frozenset(
    {
        "__stdarg___gnuc_va_list.h",
        "__stdarg___va_copy.h",
        "__stdarg_va_arg.h",
        "__stdarg_va_copy.h",
        "__stdarg_va_list.h",
        "__stddef_max_align_t.h",
        "__stddef_null.h",
        "__stddef_nullptr_t.h",
        "__stddef_offsetof.h",
        "__stddef_ptrdiff_t.h",
        "__stddef_rsize_t.h",
        "__stddef_size_t.h",
        "__stddef_unreachable.h",
        "__stddef_wchar_t.h",
        "__stddef_wint_t.h",
        "float.h",
        "inttypes.h",
        "iso646.h",
        "limits.h",
        "stdalign.h",
        "stdarg.h",
        "stdatomic.h",
        "stdbool.h",
        "stdckdint.h",
        "stddef.h",
        "stdint.h",
        "stdnoreturn.h",
        "tgmath.h",
        "vadefs.h",
        "varargs.h",
    }
)

#: Builtin headers the package does not ship, by name: the compiler intrinsics.
_UNSHIPPED_PATTERNS = ("*intrin.h", "arm_*.h")

#: The directory holding the shipped headers under ``include/``.
BUNDLED_RESOURCE_DIR: Path = Path(__file__).parent / "clang_resource"

#: Arguments with which a compile command chooses its builtin headers itself: its own
#: resource directory, or none (``--no-standard-includes`` is ``-nostdinc``).
_CHOOSING_FLAGS = frozenset(
    {"-resource-dir", "-nostdinc", "--no-standard-includes", "-nobuiltininc"}
)

_NOT_FOUND = re.compile(r"^'(?P<name>[^']+)' file not found$")


def bundled_resource_dir() -> Path | None:
    """The shipped resource directory, or ``None`` when its headers are not all files
    on the filesystem (an import from an archive, a repackaging that dropped them)."""
    include = BUNDLED_RESOURCE_DIR / "include"
    if all((include / name).is_file() for name in BUILTIN_HEADERS):
        return BUNDLED_RESOURCE_DIR
    return None


def chooses_builtin_headers(args: list[str]) -> bool:
    """Whether ``args`` choose their builtin headers themselves (see
    :data:`_CHOOSING_FLAGS`; ``-resource-dir=<dir>`` too)."""
    return any(
        arg in _CHOOSING_FLAGS or arg.startswith("-resource-dir=") for arg in args
    )


def resource_dir_args(
    args: list[str], configured: Path | None
) -> tuple[list[str], bool]:
    """``args`` with the resource directory a parse is to use (see the module docstring).

    :param args: The arguments of the parse.
    :param configured: The ``resource_dir`` setting, if set.
    :return: The arguments, and whether the shipped headers were wanted but are not
        available (step 4), which the caller warns about once.
    """
    if configured is not None:
        return [*args, "-resource-dir", str(configured)], False
    if chooses_builtin_headers(args):
        return args, False
    bundled = bundled_resource_dir()
    if bundled is None:
        return args, True
    return [*args, "-resource-dir", str(bundled)], False


def is_builtin_header(name: str) -> bool:
    """Whether the ``#include``\\ d ``name`` is a header the compiler provides: one
    of :data:`BUILTIN_HEADERS`, or an intrinsics header (``immintrin.h``,
    ``arm_neon.h``). A name with a directory (``sys/stdint.h``) is none."""
    if "/" in name or "\\" in name:
        return False
    return name in BUILTIN_HEADERS or any(
        fnmatch(name, pattern) for pattern in _UNSHIPPED_PATTERNS
    )


def missing_builtin_header(tu: Any) -> tuple[str, str | None, int] | None:
    """The first builtin header a parse could not find: its name, and the file and
    line of the ``#include`` (``None`` and 0 when libclang gives no location).

    Only the first such header is reported by libclang as an error; a later one
    fails without a diagnostic.
    """
    for diagnostic in tu.diagnostics:
        match = _NOT_FOUND.match(diagnostic.spelling)
        if match is None or not is_builtin_header(match["name"]):
            continue
        location = diagnostic.location
        file = location.file.name if location.file is not None else None
        return match["name"], file, location.line
    return None
