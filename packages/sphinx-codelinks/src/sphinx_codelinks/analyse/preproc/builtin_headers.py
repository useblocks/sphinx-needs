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
from collections.abc import Iterator
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
#: nothing. ``-Xarch_device`` is the offloading device's, never the host compile's, and
#: ``-mllvm`` hands its argument to LLVM's own option processing.
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
        "-mllvm",
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


def _driver_choices(args: list[str]) -> Iterator[str]:
    """Each argument of ``args`` with which the driver chooses the builtin headers
    (see :data:`_CHOOSING_FLAGS`; ``-resource-dir=<dir>`` is yielded as
    ``-resource-dir``), in order, as clang 18's driver reads them.

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
                yield value
            index += 2
            continue
        if arg in _CHOOSING_FLAGS:
            yield arg
        elif arg.startswith("-resource-dir="):
            yield "-resource-dir"
        index += 1


def chooses_builtin_headers(args: list[str]) -> bool:
    """Whether ``args`` choose their builtin headers themselves, as the driver reads
    them: their own resource directory, or none (:func:`_driver_choices`)."""
    return next(_driver_choices(args), None) is not None


def excluding_flag(args: list[str]) -> str | None:
    """The argument of ``args`` with which the driver leaves clang's builtin headers
    out altogether (``-nostdinc``, ``--no-standard-includes``, ``-nobuiltininc``), if
    any: no resource directory brings them back."""
    return next(
        (flag for flag in _driver_choices(args) if flag in _XARCH_CHOOSING_FLAGS), None
    )


def passes_next_argument(arg: str) -> bool:
    """Whether the driver takes the argument after ``arg`` as ``arg``'s value, for
    another tool (:data:`_PASS_THROUGH`, ``-Xopenmp-target=<triple>``,
    ``-Xoffload-linker-<triple>``) or for one architecture's compile
    (``-Xarch_<arch>``): that argument is not one of the driver's own, and a ``--``
    there does not end the options."""
    return (
        arg in _PASS_THROUGH
        or arg.startswith(_PASS_THROUGH_PREFIXES)
        or arg.startswith("-Xarch_")
    )


def _end_of_options(args: list[str]) -> int:
    """The index of the ``--`` after which the driver reads every argument as an input
    file, else ``len(args)``. A ``--`` handed to another tool (``-Xlinker --``) is
    not it.

    A compilation database entry's arguments carry no ``--`` by the time they get
    here (``compile_db.filter_args`` leaves every one out); arguments from anywhere
    else are still placed correctly."""
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "--":
            return index
        index += 2 if passes_next_argument(arg) else 1
    return len(args)


def _with_resource_dir(args: list[str], directory: Path) -> list[str]:
    """``args`` with ``-resource-dir <directory>``, before the end of the options
    (:func:`_end_of_options`)."""
    at = _end_of_options(args)
    return [*args[:at], "-resource-dir", str(directory), *args[at:]]


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
        return _with_resource_dir(args, configured), False
    if chooses_builtin_headers(args):
        return args, False
    bundled = bundled_resource_dir()
    if bundled is None:
        return args, True
    return _with_resource_dir(args, bundled), False


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


def _is_angled(file: Path, offset: int) -> bool | None:
    """Whether the include whose name starts at byte ``offset`` of ``file`` (where
    libclang places a missing include's diagnostic) is written in angle brackets,
    ``<name>``, rather than in quotes; ``None`` when that cannot be told: the file
    cannot be read, or the name is a macro's (``#include HDR``)."""
    try:
        with file.open("rb") as handle:
            handle.seek(offset)
            first = handle.read(1)
    except OSError:
        return None
    return {b"<": True, b'"': False}.get(first)


def missing_builtin_header(
    tu: Any, working_directory: Path | None = None
) -> tuple[str, str | None, int] | None:
    """The first builtin header a parse could not find: its name, and the file and
    line of the ``#include`` (``None`` and 0 when libclang gives no location).

    Only an angled include (``#include <cpuid.h>``) of a builtin header's name counts:
    a quoted one (``#include "cpuid.h"``) names the project's own header, and one
    whose form cannot be told (``#include HDR``, a file that cannot be read) is not
    reported, rather than reported wrongly. One with no location at all is a compile
    command's own (``-include immintrin.h``) and counts. Only the first missing header
    is reported by libclang as an error; a later one fails without a diagnostic.

    :param working_directory: The parse's working directory, against which a file
        libclang names relatively is read.
    """
    for diagnostic in tu.diagnostics:
        match = _NOT_FOUND.match(diagnostic.spelling)
        if match is None or not is_builtin_header(match["name"]):
            continue
        location = diagnostic.location
        file = location.file.name if location.file is not None else None
        if file is not None:
            path = (working_directory or Path.cwd()) / file
            if not _is_angled(path, location.offset):
                continue
        return match["name"], file, location.line
    return None
