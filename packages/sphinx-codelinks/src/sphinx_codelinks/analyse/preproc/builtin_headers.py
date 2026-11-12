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

``chooses_builtin_headers`` reads a compile command as clang 18's driver does.

A builtin header that is still missing after that (an intrinsics header such as
``immintrin.h``, which is not shipped) is warned about once per parsed file, naming it
and the setting that fixes it. A builtin header is any name a default full install of
clang 18 (and its compiler-rt) puts in its resource ``include`` directory
(``clang_resource/names.txt``).
"""

from __future__ import annotations

import platform
import re
import sys
from functools import cache
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

#: Every header name a default full clang install puts in its resource ``include``
#: directory, one per line, relative to it (``immintrin.h``, ``sanitizer/asan_interface.h``).
_NAMES_FILE: Path = Path(__file__).parent / "clang_resource" / "names.txt"

#: The directory holding the shipped headers under ``include/``.
BUNDLED_RESOURCE_DIR: Path = Path(__file__).parent / "clang_resource"

#: Driver arguments with which a compile command chooses its builtin headers itself: its
#: own resource directory, or none (``--no-standard-includes`` is ``-nostdinc``).
_CHOOSING_FLAGS = frozenset(
    {"-resource-dir", "-nostdinc", "--no-standard-includes", "-nobuiltininc"}
)

#: The driver options (clang 18's ``Options.td``) that hand their next argument to another
#: tool, so the driver does not read it: ``-Xclang -nobuiltininc`` reaches the compiler
#: after the driver has already added the builtin headers' directory, and chooses
#: nothing. ``-Xarch_device`` is the offloading device's, never the host compile's.
_PASS_THROUGH = frozenset(
    {
        "-Xanalyzer",
        "-Xarch_device",
        "-Xassembler",
        "-Xclang",
        "-Xcuda-fatbinary",
        "-Xcuda-ptxas",
        "-Xlinker",
        "-Xopenmp-target",
        "-Xpreprocessor",
        "-z",
    }
)
#: The same, joined to a target: ``-Xopenmp-target=<triple> <arg>``,
#: ``-Xoffload-linker[-<triple>] <arg>``.
_PASS_THROUGH_PREFIXES = ("-Xopenmp-target=", "-Xoffload-linker")

#: Of :data:`_CHOOSING_FLAGS`, those the driver takes through ``-Xarch_``: it refuses
#: ``-resource-dir`` there (a driver-only option, and one with a value).
_XARCH_CHOOSING_FLAGS = frozenset(
    {"-nostdinc", "--no-standard-includes", "-nobuiltininc"}
)

#: The operating systems of a Mach-O target, whose driver reads ``-Xarch_<arch>``.
_MACHO_SYSTEMS = ("darwin", "macos", "ios", "tvos", "watchos", "xros", "driverkit")

_NOT_FOUND = re.compile(r"^'(?P<name>[^']+)' file not found$")


def bundled_resource_dir() -> Path | None:
    """The shipped resource directory, or ``None`` when its headers are not all files
    on the filesystem (an import from an archive, a repackaging that dropped them)."""
    include = BUNDLED_RESOURCE_DIR / "include"
    if all((include / name).is_file() for name in BUILTIN_HEADERS):
        return BUNDLED_RESOURCE_DIR
    return None


def _xarch_reads(args: list[str]) -> frozenset[str]:
    """The ``<arch>`` names whose ``-Xarch_<arch> <arg>`` the driver reads for the
    compile ``args`` describe.

    Only a Mach-O (Apple) target reads them, and only for the architecture compiled:
    an ``-arch``, else the target's, by its Mach-O name (``arm64`` for ``aarch64``). Other targets leave
    them unused. The target is the last ``--target=`` / ``-target``, else the host
    libclang runs on. (``-Xflang`` is no clang driver option: the argument after it is
    read.)
    """
    target = None
    arches: list[str] = []
    for index, arg in enumerate(args):
        following = args[index + 1] if index + 1 < len(args) else None
        if arg.startswith("--target="):
            target = arg.removeprefix("--target=")
        elif arg == "-target" and following is not None:
            target = following
        elif arg == "-arch" and following is not None:
            arches.append(following)
    if target is None:
        macho = sys.platform == "darwin"
        arch = platform.machine()
    else:
        parts = target.split("-")
        arch = parts[0]
        macho = (len(parts) > 1 and parts[1] == "apple") or any(
            part.startswith(_MACHO_SYSTEMS) for part in parts[2:3]
        )
    if not macho:
        return frozenset()
    # the Mach-O name of the target's architecture (``arm64`` for ``aarch64``), as
    # the driver names it
    universal = {"aarch64": "arm64", "aarch64_32": "arm64_32"}.get(arch, arch)
    # an ``-arch`` replaces the target's architecture
    return frozenset(arches or [universal])


def chooses_builtin_headers(args: list[str]) -> bool:
    """Whether ``args`` choose their builtin headers themselves, as the driver reads
    them (see :data:`_CHOOSING_FLAGS`; ``-resource-dir=<dir>`` too).

    An argument the driver hands to another tool (:data:`_PASS_THROUGH`) is not
    read. One after ``-Xarch_host``, or after ``-Xarch_<arch>`` for the architecture
    being compiled on a Mach-O target (:func:`_xarch_reads`), is, unless it is one the
    driver refuses there.
    """
    reads: frozenset[str] | None = None
    index = 0
    while index < len(args):
        arg = args[index]
        value = args[index + 1] if index + 1 < len(args) else None
        if arg in _PASS_THROUGH or arg.startswith(_PASS_THROUGH_PREFIXES):
            index += 2
            continue
        if arg.startswith("-Xarch_"):
            if reads is None:
                reads = _xarch_reads(args)
            arch = arg.removeprefix("-Xarch_")
            if (arch == "host" or arch in reads) and value in _XARCH_CHOOSING_FLAGS:
                return True
            index += 2
            continue
        if arg in _CHOOSING_FLAGS or arg.startswith("-resource-dir="):
            return True
        index += 1
    return False


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


@cache
def builtin_header_names() -> frozenset[str]:
    """Every header name a default full clang install puts in its resource ``include``
    directory (``clang_resource/names.txt``); the shipped ones alone when that file
    cannot be read."""
    try:
        text = _NAMES_FILE.read_text(encoding="utf-8")
    except OSError:
        return BUILTIN_HEADERS
    return frozenset(text.split()) | BUILTIN_HEADERS


def is_builtin_header(name: str) -> bool:
    """Whether the ``#include``\\ d ``name`` is one clang installs in its resource
    ``include`` directory (:func:`builtin_header_names`), as written: ``immintrin.h``
    is, ``sys/stdint.h`` is not."""
    return name in builtin_header_names()


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
