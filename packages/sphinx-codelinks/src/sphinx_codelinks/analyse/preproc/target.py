"""Which target the libclang engine reads a C/C++ file for.

A target (a triple: ``thumbv7em-none-unknown-eabihf``, ``x86_64-pc-linux-gnu``) decides
which ``#if`` arms a file compiles (``__arm__``, ``__x86_64__``, ``__SIZEOF_LONG__``,
...). libclang reads none from a compile command's compiler: it parses with its own
``clang`` in ``argv[0]``, and the rule that reads a target from a program name
(``arm-none-eabi-gcc`` compiles for ``arm-none-eabi``) lives in clang's driver binary,
not in the library. A parse with no ``--target`` is read for the triple the libclang
build was configured with: the machine the analysis runs on.

The engine therefore decides the target of each parse itself, reading what the build
declares, in this order (:func:`decide`):

1. the entry's own ``--target=<triple>`` / ``-target <triple>`` (``entry``);
2. the target its compiler's name carries, by clang's own rule
   (:func:`.compile_db.target_of_compiler`), inserted as ``--target=``
   (``compiler_name``): only when the name's first part is an architecture the loaded
   libclang models, as clang's driver takes a prefix only when its architecture is a
   registered target (``my-arm-gcc``, ``musl-gcc`` and ``xtensa-esp32-elf-gcc``
   declare none);
3. the ``[preprocessor] target`` setting (``setting``), which is all a file with no
   entry of its own (a header, the ``defines`` path) reads;
4. else the machine the analysis runs on, a stated assumption (``host``).

Each triple is checked once per libclang against the loaded libclang
(:func:`modelled_by`): libclang refuses to parse at all for a triple it does not model
(``xtensa-esp32-elf``), so an unchecked one would drop every marker of the file. An
entry's own triple or the setting's that it does not model is treated as no
declaration and reported once per file (:attr:`Decision.unmodelled`): an entry's own
one leaves the setting to apply; its compiler's name is then not read. A compiler's
name whose first part libclang does not model but whose rest it reads as a vendor, an
OS or an environment (``xtensa-esp32-elf-gcc``: ``elf``) is reported the same way; one
whose rest it does not (``my-arm-gcc``, ``musl-gcc``) declares nothing and is not
reported. An inserted triple can still be refused with the entry's
own flags (``-mcpu=e200z4``, a CPU GCC knows and clang does not): that parse is made
again keeping the target and leaving out the entry's ``-mcpu=``, ``-march=``,
``-mtune=`` and ``-mabi=``, then, if that is refused too, for the machine the analysis
runs on without the target and those flags (:func:`parse_or_again`), so a target never
drops a file.
"""

from __future__ import annotations

import ctypes
import enum
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any, TypeVar

from sphinx_codelinks.analyse.preproc import loader
from sphinx_codelinks.analyse.preproc.builtin_headers import passes_next_argument
from sphinx_codelinks.analyse.preproc.compile_db import WORKING_DIRECTORY_FLAG

T = TypeVar("T")


class TargetSource(enum.StrEnum):
    """Where the target of a parse was taken from."""

    entry = "entry"
    """The entry's own ``--target`` / ``-target``."""
    compiler_name = "compiler_name"
    """The target the entry's compiler's name declares."""
    setting = "setting"
    """The ``[preprocessor] target`` setting."""
    host = "host"
    """None declared: libclang's default, the machine the analysis runs on."""

    @property
    def inserted(self) -> bool:
        """Whether a triple from it is inserted into the parse's arguments (the
        entry's own one is there already)."""
        return self in (TargetSource.compiler_name, TargetSource.setting)


REFUSABLE_FLAGS = ("-mcpu=", "-march=", "-mtune=", "-mabi=")
"""The entry's own flags that a parse refused with an inserted target is made again
without: those that pick a CPU or an ABI within an architecture. clang refuses some of the
values GCC knows for them (``-mcpu=e200z4``, ``-mabi=lp64`` with ``aarch64-linux-gnu``),
and has no two-word form of any of them (``-mcpu cortex-m3`` is an unknown argument it
ignores)."""


class NotRead(enum.StrEnum):
    """Why a declared target is not read as the build declares it."""

    unmodelled = "unmodelled"
    """The loaded libclang does not model the triple (an entry's own, the setting's):
    the file is read for the next source."""
    prefix_unmodelled = "prefix_unmodelled"
    """The compiler's name's prefix, whose first part is not an architecture the loaded
    libclang models, and whose rest it reads as a vendor, an OS or an environment
    (:func:`reads_the_rest`): the file is read for the next source."""
    flags_refused = "flags_refused"
    """libclang refused the parse with the entry's own flags, :attr:`Unmodelled.flags`
    of them: the file is read for the target without them."""
    target_refused = "target_refused"
    """libclang refused the parse with the target, with the entry's flags and without
    :attr:`Unmodelled.flags` of them (none when the entry has none): the file is read
    for the host, without them."""


@dataclass(frozen=True)
class Unmodelled:
    """A declared triple the file is not read for as declared
    (:attr:`Decision.unmodelled`)."""

    triple: str
    """The triple, as declared (a compiler's name's prefix, as the name rule gives
    it)."""
    by: TargetSource
    """Who declared it."""
    flag: str = ""
    """How an entry wrote its own one: ``--target`` or ``-target``."""
    why: NotRead = NotRead.unmodelled
    """Why it is not read as declared."""
    flags: tuple[str, ...] = ()
    """The entry's :data:`REFUSABLE_FLAGS` the file was read without, when it was
    refused."""

    def declarer(self, includer: bool) -> str:
        """Who declared it, as the finding names them; ``includer`` when the file is
        read through the entry that includes it."""
        whose = "its includer's" if includer else "its"
        if self.by is TargetSource.entry:
            return f"{whose} compilation-database entry's `{self.flag}`"
        if self.by is TargetSource.compiler_name:
            return f"{whose} compiler's name"
        return "the `[preprocessor] target` setting"


def _spelled(flags: tuple[str, ...]) -> str:
    """``flags`` as a finding names them: each in backticks, joined by ``, ``."""
    return ", ".join(f"`{flag}`" for flag in flags)


@dataclass(frozen=True)
class Decision:
    """The target decided for one parse (:func:`decide`)."""

    source: TargetSource
    """Where it was taken from."""
    declared: str | None = None
    """The triple as declared (the parse's own triple is libclang's normalised form of
    it, refined by flags such as ``-mcpu``); ``None`` for :attr:`TargetSource.host`."""
    unmodelled: Unmodelled | None = None
    """The first declared triple the file is not read for as declared: the file is
    read for :attr:`source` instead (not modelled), or for that triple without the
    entry's refused flags, or for the host (:func:`again`: refused)."""

    def message(self, file: str, read_for: str, includer: bool) -> str | None:
        """The message of the ``preprocessor_target_unknown`` finding about ``file``,
        read for ``read_for`` (the triple libclang parsed it for), through its includer
        when ``includer``; ``None`` when the file is read for the target its build
        declares. Worded as ubCode's finding is."""
        unmodelled = self.unmodelled
        if unmodelled is None:
            return None
        nxt = (
            "the `[preprocessor] target` setting"
            if self.source is TargetSource.setting
            else "the machine sphinx-codelinks runs on"
        )
        triple = unmodelled.triple
        declarer = unmodelled.declarer(includer)
        arms = "so the `#if` arms of the file on the target are not its build's"
        flags = _spelled(unmodelled.flags)
        if unmodelled.why is NotRead.unmodelled:
            instead = nxt
            why = (
                f"the target {triple} that {declarer} names is not one the libclang "
                f"sphinx-codelinks loaded models, {arms}"
            )
        elif unmodelled.why is NotRead.prefix_unmodelled:
            instead = nxt
            arch = triple.split("-", 1)[0]
            why = (
                f"{declarer} carries the target {triple}, whose architecture {arch} the "
                f"libclang sphinx-codelinks loaded does not model, {arms}"
            )
        elif unmodelled.why is NotRead.flags_refused:
            instead = f"the target {triple} that {declarer} names, without {flags}"
            why = (
                f"the libclang sphinx-codelinks loaded refused {flags} with that target, "
                f"so the `#if` arms of the file on the CPU and the ABI are the target's "
                f"defaults, not its build's"
            )
        else:
            instead = "the machine sphinx-codelinks runs on" + (
                f", without {flags}" if flags else ""
            )
            why = (
                f"the libclang sphinx-codelinks loaded refused the target {triple} that "
                f"{declarer} names with the entry's flags"
                + (f", and without {flags}" if flags else "")
                + f", {arms}"
            )
        return f"codelinks: {file} is read for {read_for} ({instead}): {why}"


HOST = Decision(TargetSource.host)
"""The host decision, nothing declared."""


def own_target(args: list[str]) -> tuple[str, str] | None:
    """The entry's own target in ``args`` (a compile's arguments): the last
    ``--target=<triple>`` or ``-target <triple>``, as clang takes it, with the flag it
    was written with. The value of an option whose next argument the driver hands on
    (``-Xclang -target``) is not one."""
    target = None
    arguments = iter(args)
    for arg in arguments:
        if arg.startswith("--target="):
            target = (arg.removeprefix("--target="), "--target")
        elif arg == "-target":
            triple = next(arguments, None)
            if triple is not None:
                target = (triple, "-target")
        elif passes_next_argument(arg):
            next(arguments, None)
    return target


def _without_own_target(args: list[str]) -> list[str]:
    """``args`` without the entry's own targets (:func:`own_target`, each one)."""
    kept: list[str] = []
    arguments = iter(args)
    for arg in arguments:
        if arg.startswith("--target="):
            continue
        if arg == "-target":
            next(arguments, None)
            continue
        kept.append(arg)
        if passes_next_argument(arg):
            value = next(arguments, None)
            if value is not None:
                kept.append(value)
    return kept


def _with_target(args: list[str], triple: str) -> list[str]:
    """``args`` with ``--target=<triple>`` inserted where the engine's own leading
    arguments end: after the ``-working-directory=`` an entry's arguments start with,
    else first. Before every argument of the entry's own, so that a pass-through option
    the entry leaves without its value (``-Xlinker`` last) does not take it."""
    at = 1 if args and args[0].startswith(WORKING_DIRECTORY_FLAG) else 0
    return [*args[:at], f"--target={triple}", *args[at:]]


def _without_refusable_flags(args: list[str]) -> tuple[list[str], tuple[str, ...]]:
    """``args`` without the entry's :data:`REFUSABLE_FLAGS`, and those left out; the
    value of an option that hands its argument on (``-Xclang``) is kept."""
    kept: list[str] = []
    left_out: list[str] = []
    arguments = iter(args)
    for arg in arguments:
        if arg.startswith(REFUSABLE_FLAGS):
            left_out.append(arg)
            continue
        kept.append(arg)
        if passes_next_argument(arg):
            value = next(arguments, None)
            if value is not None:
                kept.append(value)
    return kept, tuple(left_out)


def _names_an_architecture(prefix: str, modelled: Callable[[str], bool]) -> bool:
    """Whether the first part of ``prefix`` (the target a compiler's name carries) is
    an architecture ``modelled`` accepts as a target on its own (``arm``, ``aarch64``,
    ``x86_64``, ``riscv64``; not ``my``, ``musl``, ``xtensa``). clang's driver takes a
    name's prefix only when its architecture is a registered target; libclang, given
    any prefix, normalises it into some triple (``my-arm`` as ``armv4t-my-unknown``)."""
    arch = prefix.split("-", 1)[0]
    return bool(arch) and modelled(arch)


def _names_a_system(prefix: str, reads_the_rest: Callable[[str], bool]) -> bool:
    """Whether ``prefix`` (a compiler's name's, whose first part is not an architecture
    libclang models) has a rest after its first part that ``reads_the_rest`` reads a
    vendor, an OS or an environment in: a target libclang cannot read
    (``xtensa-esp32-elf``, ``tricore-elf``), not a wrapper's name (``my-arm``,
    ``foo-bar``; ``musl`` and ``my`` have no rest)."""
    _, _, rest = prefix.partition("-")
    return bool(rest) and reads_the_rest(rest)


def decide(
    args: list[str],
    *,
    entry: bool,
    compiler: str | None = None,
    setting: str | None = None,
    modelled: Callable[[str], bool],
    reads_the_rest: Callable[[str], bool] = lambda _rest: False,
) -> tuple[list[str], Decision]:
    """The arguments of a parse with its target decided, and the decision.

    :param args: The parse's own arguments: an entry's (``entry``: its own ``--target``
        is read from them, and ``compiler``) or the ``defines`` path's (the setting
        alone).
    :param compiler: The target the entry's compiler's name carries.
    :param setting: The ``[preprocessor] target`` setting (``""`` and spaces alone are
        unset; spaces around it are not part of it).
    :param modelled: Whether the loaded libclang models a triple (:func:`modelled_by`).
    :param reads_the_rest: Whether the loaded libclang reads a vendor, an OS or an
        environment in what follows the first part of a name's prefix
        (:func:`reads_the_rest`).

    The sources are tried in the order the module docs give; the first that names a
    triple ``modelled`` accepts wins, and is inserted unless it is the entry's own. An
    entry's own triple libclang does not model is removed from the arguments, since
    libclang refuses to parse for it, and the compiler's name is then not read.
    """
    setting = setting.strip() if setting is not None else None
    own = own_target(args) if entry else None
    unmodelled: Unmodelled | None = None
    candidates: list[tuple[str, TargetSource, str]] = []
    if own is not None:
        candidates.append((own[0], TargetSource.entry, own[1]))
    elif entry and compiler:
        if _names_an_architecture(compiler, modelled):
            candidates.append((compiler, TargetSource.compiler_name, ""))
        elif _names_a_system(compiler, reads_the_rest):
            # a GCC triple of an architecture libclang does not have (xtensa-esp32-elf):
            # declared, not read, and so reported; a wrapper's name (my-arm) is silent
            unmodelled = Unmodelled(
                compiler, TargetSource.compiler_name, why=NotRead.prefix_unmodelled
            )
    if setting:
        candidates.append((setting, TargetSource.setting, ""))
    for triple, source, flag in candidates:
        if modelled(triple):
            if source.inserted:
                args = _with_target(args, triple)
            return args, Decision(source, triple, unmodelled)
        if source is TargetSource.entry:
            args = _without_own_target(args)
        if unmodelled is None:
            unmodelled = Unmodelled(triple, source, flag)
    return args, Decision(TargetSource.host, None, unmodelled)


def again(args: list[str], decision: Decision) -> list[tuple[list[str], Decision]]:
    """The parses to make again, in order, when the parse of ``args`` with the triple
    ``decision`` inserted is refused, each with the decision that reports it: keeping
    the triple and leaving out the entry's :data:`REFUSABLE_FLAGS` (when it has any:
    clang refuses CPUs and ABIs GCC knows, and the same ones on every machine, so the
    architecture is kept); then for the host, without the triple and those flags
    (another of its flags refuses the triple). The decision's source stays where the
    triple came from. None when nothing was inserted: an entry's own triple, which the
    build itself passes, or the host's."""
    triple = decision.declared
    if triple is None or not decision.source.inserted:
        return []
    kept, flags = _without_refusable_flags(args)

    def refused(why: NotRead) -> Decision:
        return replace(
            decision,
            unmodelled=Unmodelled(
                triple, decision.source, "--target", why=why, flags=flags
            ),
        )

    attempts: list[tuple[list[str], Decision]] = []
    if flags:
        attempts.append((kept, refused(NotRead.flags_refused)))
    inserted = f"--target={triple}"
    host = [arg for arg in kept if arg != inserted]
    attempts.append((host, refused(NotRead.target_refused)))
    return attempts


def parse_or_again(
    args: list[str],
    decision: Decision,
    parse: Callable[[list[str]], T],
    refusal: type[Exception] | tuple[type[Exception], ...],
) -> tuple[T, list[str], Decision]:
    """``parse`` of ``args`` for ``decision``, made :func:`again` while it is refused
    (raises ``refusal``) and its triple was inserted: the read, the arguments it was
    made with and the decision that reports it. A target never drops a file: the last
    parse is the one the file had before targets were read, without the flags its
    target was refused with.

    :raises refusal: When the last parse is refused too, or the first one is and
        nothing was inserted.
    """
    try:
        return parse(args), args, decision
    except refusal:
        attempts = again(args, decision)
        if not attempts:
            raise
    for position, (attempt, refused) in enumerate(attempts):
        try:
            return parse(attempt), attempt, refused
        except refusal:
            if position == len(attempts) - 1:
                raise
    raise AssertionError("unreachable")  # pragma: no cover


_PROBE_FILE = "codelinks-target-probe.c"
"""The name of the empty in-memory file the libclang checks parse."""

_MODELLED: dict[tuple[str, str], bool] = {}
"""Whether a libclang (by its version string) models a triple: memoised."""

_SYSTEMS: dict[tuple[str, str], bool] = {}
"""Whether a libclang reads a vendor, an OS or an environment in a name prefix's rest."""

_VERSION: list[str] = []
"""The loaded libclang's version string, read once."""

_TARGET_INFO: list[Any] = []
"""The three ``clang_TargetInfo`` functions, bound once."""


def _probe(args: list[str]) -> Any:
    """An empty in-memory file parsed with ``args``; ``None`` when libclang refuses."""
    cx = loader.load_clang_cindex()
    try:
        return cx.Index.create().parse(
            _PROBE_FILE, args=args, unsaved_files=[(_PROBE_FILE, "")]
        )
    except cx.TranslationUnitLoadError:
        return None


def _version() -> str:
    """The loaded libclang's version string (``clang_getClangVersion``), read once: the
    ``clang.cindex`` binding of it returns no string, so it is bound here."""
    if not _VERSION:
        cx = loader.load_clang_cindex()
        # a function pointer of its own (``CDLL.__getitem__`` makes a new one)
        function = cx.conf.lib["clang_getClangVersion"]
        function.argtypes = []
        function.restype = cx._CXString
        _VERSION.append(str(cx._CXString.from_result(function())))
    return _VERSION[0]


def triple_of(tu: Any) -> str:
    """The triple libclang parsed ``tu`` for (``clang_getTranslationUnitTargetInfo``,
    which the ``clang.cindex`` bindings do not expose)."""
    cx = loader.load_clang_cindex()
    if not _TARGET_INFO:
        lib = cx.conf.lib
        # functions of their own (``CDLL.__getitem__`` makes a new pointer)
        info = lib["clang_getTranslationUnitTargetInfo"]
        info.argtypes = [cx.TranslationUnit]
        info.restype = ctypes.c_void_p
        get_triple = lib["clang_TargetInfo_getTriple"]
        get_triple.argtypes = [ctypes.c_void_p]
        get_triple.restype = cx._CXString
        dispose = lib["clang_TargetInfo_dispose"]
        dispose.argtypes = [ctypes.c_void_p]
        dispose.restype = None
        _TARGET_INFO.extend((info, get_triple, dispose))
    info, get_triple, dispose = _TARGET_INFO
    target_info = info(tu)
    try:
        return str(cx._CXString.from_result(get_triple(target_info)))
    finally:
        dispose(target_info)


def modelled_by(triple: str) -> bool:
    """Whether the loaded libclang models ``triple``: an empty in-memory file parses
    for ``--target=<triple>`` (libclang refuses to parse at all for a triple it does not
    model). Asked once per triple and libclang for the process."""
    key = (_version(), triple)
    if key not in _MODELLED:
        _MODELLED[key] = _probe([f"--target={triple}"]) is not None
    return _MODELLED[key]


_REST_PROBE = "x86_64-unknown-unknown-unknown"
"""What :func:`reads_the_rest` puts a prefix's rest behind: an architecture libclang
models, and its vendor, OS and environment as ``unknown``, which libclang reads as no
word (as ubCode's ``REST_PROBE``)."""


def reads_the_rest(rest: str) -> bool:
    """Whether the loaded libclang reads a word of ``rest`` (what follows the first part
    of a compiler's name's prefix) as a vendor, an OS or an environment.

    It normalises ``<_REST_PROBE>-<rest>``, and a word it reads moves into its slot
    (``x86_64-unknown-unknown-unknown-esp32-elf`` is
    ``x86_64-unknown-unknown-elf-unknown-esp32``), while words it does not read stay
    where they are (``...-unknown-arm``). A probe it refuses to parse for is read too: a
    word it reads made it refuse. Asked once per rest and libclang for the process."""
    key = (_version(), rest)
    if key not in _SYSTEMS:
        probe = f"{_REST_PROBE}-{rest}"
        tu = _probe([f"--target={probe}"])
        _SYSTEMS[key] = tu is None or triple_of(tu) != probe
    return _SYSTEMS[key]
