"""Discover, read, and filter compile_commands.json for libclang."""

from __future__ import annotations

import json
import shlex
from pathlib import Path

from sphinx_codelinks.analyse.preproc.builtin_headers import passes_next_argument
from sphinx_codelinks.config import DEFAULT_CPP_STD

_DB_NAME = "compile_commands.json"
_BOUNDARY_MARKERS = (".git", "ubproject.toml", "pyproject.toml")

# Flags that take a following value we must also drop.
_DROP_WITH_VALUE = {"-o", "-MF", "-MT", "-MQ"}
# Exact flags to drop.
_DROP_EXACT = {"-c", "-MMD", "-MD", "-MG", "-MP"}
# Separate-form flags whose following VALUE token must be kept verbatim (never
# treated as the input source and stripped by basename).
_KEEP_WITH_VALUE = {
    "-include",
    "-isystem",
    "-iquote",
    "-idirafter",
    "-isysroot",
    "-x",
    "-I",
}
# The argument after which the driver reads every argument as an input file.
END_OF_OPTIONS = "--"
# Minimum length for joined-form flags like -MFdep.d (prefix length = 3)
_MIN_JOINED_FLAG_LEN = 3

# Suffixes a compiler builds as a translation unit. A discovered C/C++ file
# absent from compile_commands.json is skipped only when it is a TU source
# (build-excluded); all other discovered files (headers) are parsed standalone.
TU_SOURCE_SUFFIXES = {".c", ".cpp", ".cc", ".cxx"}


# @Discover compile_commands.json by walking up from the source file, IMPL_PREPROC_3, impl, [FE_PREPROC]
def find_compile_db(start: Path, project_root: Path | None = None) -> Path | None:
    """Walk up from ``start`` looking for compile_commands.json.

    Stops at (inclusive) the directory that contains the db, or at
    ``project_root`` / a directory containing a boundary marker / fs root.
    """
    current = start if start.is_dir() else start.parent
    current = current.resolve()
    root = project_root.resolve() if project_root else None
    while True:
        candidate = current / _DB_NAME
        if candidate.is_file():
            return candidate
        if root is not None and current == root:
            return None
        if any((current / m).exists() for m in _BOUNDARY_MARKERS):
            return None
        if current.parent == current:  # filesystem root
            return None
        current = current.parent


def _left_out(arg: str, input_file: str, input_base: str) -> int:
    """How many arguments, ``arg`` first, :func:`filter_args` leaves out at ``arg``:
    2 for an option whose separate value names an output (``-o out.o``, ``-MF dep.d``),
    1 for one that asks for an output or none (``-c``, ``-MD``, ``-MFdep.d``) and for
    the entry's own input, else 0."""
    if arg in _DROP_WITH_VALUE:
        return 2
    if arg in _DROP_EXACT:
        return 1
    if arg.startswith(("-MF", "-MT", "-MQ")) and len(arg) > _MIN_JOINED_FLAG_LEN:
        return 1  # joined form, e.g. -MFdep.d
    # the TU source positional (exact match, or same basename)
    if not arg.startswith("-") and (
        arg in (input_file, input_base) or Path(arg).name == input_base
    ):
        return 1
    return 0


def filter_args(argv: list[str], input_file: str) -> list[str]:
    """Keep only flags libclang needs; drop the compiler, -c/-o, depfiles, input.

    A ``--`` ends the options: every argument after it is an input, so it is left
    out with them (the entry's own file is parsed on its own, and any other input
    would make a second compiler job). libclang reads the first ``--`` of its
    arguments as the end of the options whatever precedes it, so no ``--`` is
    passed on, and one that is the value of these options ends nothing (the
    arguments after it are still read as options):

    - a pass-through option (:func:`.passes_next_argument`: ``-Xlinker``,
      ``-Xclang``, ``-mllvm``, ``-Xarch_<arch>``, ...) is left out with its ``--``.
      A real compile rejects a ``--`` that reaches the compiler or the driver that
      way (``-Xclang --``, ``-Xpreprocessor --``: "unknown argument: '--'";
      ``-Xarch_host --``: "invalid Xarch argument"), and the other options hand it
      to a tool or stage that has no say in preprocessing (the linker, the
      assembler, LLVM's backend), so this loses nothing a working entry has;
    - ``-I``, ``-include``, ``-isystem``, ``-iquote``, ``-idirafter``,
      ``-isysroot`` and ``-x`` are joined to their ``--`` (``-I--``), which the
      driver reads the same.

    Nothing is promised for another option whose separate value is ``--``
    (``-D --``, ``-imacros --``): the ``--`` is taken for the end of the options.

    Any other value of a pass-through option is kept with it, verbatim, except that
    of ``-Xarch_<arch>``, which the driver reads as one of its own options: it goes
    through the same rules as a bare option, so ``-Xarch_host -MD`` is left out like
    ``-MD`` (or the parse would write a dependency file).
    """
    out: list[str] = []
    skip_next = False
    keep_next_value = False
    pass_through: str | None = None
    input_base = Path(input_file).name
    # Skip leading non-flag tokens. argv[0] is the compiler, but a build may prefix
    # it with a launcher (ccache/sccache/distcc), so drop every leading non-flag
    # token up to the first flag — otherwise the real compiler leaks in as a
    # positional and libclang treats it as a second input (a NULL TU that silently
    # drops the file). The input source (also a non-flag positional) is stripped by
    # name below.
    in_leading = True
    for arg in argv:
        if in_leading:
            if not arg.startswith("-"):
                continue
            in_leading = False
        if skip_next:
            skip_next = False
            continue
        if keep_next_value:
            # Value of a separate-form -include/-isystem/-I/... — keep verbatim,
            # joined to its option when it is a `--` (see the docstring).
            keep_next_value = False
            if arg == END_OF_OPTIONS:
                out[-1] += arg
            else:
                out.append(arg)
            continue
        if pass_through is not None:
            # Value of -Xclang/-Xlinker/-mllvm/... — kept verbatim with its option,
            # or left out with it when it is a `--`; the value of -Xarch_<arch> is
            # one of the driver's own options, and left out as one would be.
            if arg == END_OF_OPTIONS:
                pass
            elif pass_through.startswith("-Xarch_") and (
                left_out := _left_out(arg, input_file, input_base)
            ):
                skip_next = left_out == 2
            else:
                out += [pass_through, arg]
            pass_through = None
            continue
        if arg == END_OF_OPTIONS:
            break
        if passes_next_argument(arg):
            pass_through = arg
            continue
        if left_out := _left_out(arg, input_file, input_base):
            skip_next = left_out == 2
            continue
        if arg in _KEEP_WITH_VALUE:
            out.append(arg)
            keep_next_value = True
            continue
        out.append(arg)
    if pass_through is not None:
        out.append(pass_through)  # missing its value: passed on as the entry has it
    return out


WORKING_DIRECTORY_FLAG = "-working-directory="
"""The libclang flag every database entry's arguments start with (see
:func:`load_flags_map`)."""


# @Resolve per-file compiler flags from the compilation database, IMPL_PREPROC_4, impl, [FE_PREPROC]
def load_flags_map(db_path: Path) -> dict[Path, list[str]]:
    """Parse compile_commands.json -> {absolute file path: filtered args}.

    Each entry's arguments start with ``-working-directory=<directory>``, the entry's
    ``directory`` (a relative one is taken against the database file's own directory),
    so that a relative ``-I``, ``-iquote``, ``-isystem``, ``-include`` or ``-imacros``
    resolves as the build resolves it, not against the process' working directory.
    """
    entries = json.loads(db_path.read_text())
    db_dir = db_path.absolute().parent
    flags: dict[Path, list[str]] = {}
    for entry in entries:
        if "file" not in entry or "directory" not in entry:
            continue  # malformed entry: skip, keep going
        if "arguments" in entry:
            argv = list(entry["arguments"])
        elif "command" in entry:
            argv = shlex.split(entry["command"])
        else:
            continue
        # an absolute ``directory`` replaces ``db_dir`` in the join
        directory = (db_dir / entry["directory"]).resolve()
        file_field = entry["file"]
        abs_file = (directory / file_field).resolve()
        flags[abs_file] = [
            f"{WORKING_DIRECTORY_FLAG}{directory}",
            *filter_args(argv, file_field),
        ]
    return flags


def working_directory(args: list[str]) -> Path:
    """The working directory ``args`` name with ``-working-directory=``, or, without
    one, the process' working directory, as libclang takes it: the last one wins, so
    an entry whose own arguments carry one overrides the one :func:`load_flags_map`
    puts first."""
    for arg in reversed(args):
        if arg.startswith(WORKING_DIRECTORY_FLAG):
            return Path(arg[len(WORKING_DIRECTORY_FLAG) :])
    return Path.cwd()


# @Parse headers standalone from configured defines and includes, IMPL_PREPROC_5, impl, [FE_PREPROC]
def defines_to_args(
    defines: list[str], includes: list[Path], std: str = DEFAULT_CPP_STD
) -> list[str]:
    """Build a global flag list for parsing a file standalone.

    Used for headers and files absent from a compile DB. libclang infers the
    language from the file extension, so a C-inferred file (``.h`` / ``.c`` /
    ``.inc``) handed a C++ ``-std`` makes clang reject the combination and return
    a NULL translation unit (surfacing as ``TranslationUnitLoadError``). Pin the
    language to match ``std`` with ``-x`` so such files — e.g. a ``.h`` header
    carrying oneline need markers — parse and extract instead of failing. (C
    sources parse as C++ well enough for comment/marker extraction.)
    """
    lang = "c++" if std.startswith(("c++", "gnu++")) else "c"
    args = ["-x", lang, f"-std={std}"]
    args += [f"-D{d}" for d in defines]
    args += [f"-I{inc}" for inc in includes]
    return args


def is_translation_unit_source(path: Path) -> bool:
    """True if ``path`` is a compiled translation-unit source (not a header).

    compile_commands.json lists one entry per compiled TU; headers are never
    entries. So a discovered file absent from the DB is read through an entry that
    includes it, or skipped, only when it is a TU source; header-like files are
    parsed standalone (see _resolve_preproc_args).
    """
    return path.suffix.lower() in TU_SOURCE_SUFFIXES
