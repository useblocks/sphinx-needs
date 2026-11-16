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
entry's own triple or the setting's that it does not model is left out of the parse and
reported once per file (:attr:`Decision.unmodelled`); its compiler's name is then not
read, nor, after an entry's own, the setting. A compiler's name whose first part
libclang does not model but whose rest it reads as a vendor, an OS or an environment
(``xtensa-esp32-elf-gcc``: ``elf``) is reported the same way; one whose rest it does not
(``my-arm-gcc``, ``musl-gcc``) declares nothing and is not reported. A parse can still
be refused with the entry's own flags (``-mcpu=e200z4``, a CPU GCC knows and clang does
not): any refused parse is made again keeping its target and leaving out the entry's
``-mcpu=``, ``-march=``, ``-mtune=`` and ``-mabi=``, and, for a declared triple (the
entry's own or an inserted one), then without the triple and those flags
(:func:`parse_or_again`). So a declared target never leaves a file unread that would be
read without it. A file is still skipped, as before targets were read, when its target
is known (the host's own, or a declared one read without the CPU flags) and what is
left of its flags is refused for it too (``-mfpmath=sse`` on an Arm64 machine).

A file whose build declares a target the engine cannot read (an entry's own triple
libclang does not model, the setting's for a file that takes it, a declared triple
refused even without those flags) has an unknown target (:attr:`Decision.unknown`): it
is read as written, no arm of any ``#if`` left out (useblocks/ubcode#4865 S2). The
machine the analysis runs on is not the build's target, and no other triple is: the
parse it is still given (for the comments libclang lexes) decides nothing, and when even
that parse is refused the file is read without libclang, by the tree-sitter engine. A
file whose build declares nothing is read for the host, stated (``host``).
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
"""The entry's own flags that a refused parse is made again without: those that pick a
CPU or an ABI within an architecture. clang refuses some of the values GCC knows for them
(``-mcpu=e200z4``, ``-mabi=lp64`` with ``aarch64-linux-gnu``), and has no two-word form
of any of them (``-mcpu cortex-m3`` is an unknown argument it ignores)."""


class NotRead(enum.StrEnum):
    """Why a declared target is not read as the build declares it
    (:attr:`Unmodelled.fallback` spells it as ubCode's report does)."""

    unmodelled = "unmodelled"
    """The loaded libclang does not model the triple (an entry's own, the setting's):
    the file is read for the next source."""
    prefix_unmodelled = "prefix_unmodelled"
    """The compiler's name's prefix, whose first part is not an architecture the loaded
    libclang models, and whose rest it reads as a vendor, an OS or an environment
    (:func:`reads_the_rest`): the file is read for the next source."""
    flags_refused = "flags_refused"
    """libclang refused the parse with the entry's own :data:`REFUSABLE_FLAGS`
    (:attr:`Decision.left_out`): the file is read for the target without them."""
    target_refused = "target_refused"
    """libclang refused the parse with the inserted target, with the entry's flags and
    without its :data:`REFUSABLE_FLAGS` (none when the entry has none): the file is read
    for the host, without them."""


@dataclass(frozen=True)
class Unmodelled:
    """A declared triple the file is not read for as declared
    (:attr:`Decision.unmodelled`)."""

    triple: str
    """The triple, as declared (a compiler's name's prefix, as the name rule gives it);
    empty for the host's own, whose flags were refused (:attr:`NotRead.flags_refused`
    with :attr:`TargetSource.host`)."""
    by: TargetSource
    """Who declared it."""
    flag: str = ""
    """How an entry wrote its own one: ``--target`` or ``-target``."""
    why: NotRead = NotRead.unmodelled
    """Why it is not read as declared."""

    @property
    def fallback(self) -> str:
        """Why, as ubCode's report spells it: ``unmodelled`` (an entry's own triple),
        ``setting_unmodelled``, ``prefix_unmodelled``, ``flags_refused``,
        ``target_refused``."""
        if self.why is NotRead.unmodelled and self.by is TargetSource.setting:
            return "setting_unmodelled"
        return str(self.why)

    def as_written_message(
        self,
        file: str,
        with_and_without: tuple[tuple[str, ...], tuple[str, ...]],
        includer: bool,
    ) -> str:
        """The warning for ``file``, whose target is unknown because of this
        declaration (:attr:`Decision.unknown`) and which is read as written, through its
        includer when ``includer``. A target refused names the entry's ``-m`` flags it
        was refused with and the :data:`REFUSABLE_FLAGS` it was refused without too
        (``with_and_without``); the flags left out of a parse for an unmodelled triple
        decide nothing and are not named.

        Nothing is hidden, so the remedy is to accept it, by suppressing the warning, or,
        when the setting declared the target, to set the setting to a triple libclang
        reads (the setting does not override what the build declares). Worded as
        ubCode's finding is, without its symbol inventory, which sphinx-codelinks does
        not have, and with Sphinx's ``suppress_warnings`` for its ``[lint]`` tables."""
        with_flags, left_out = with_and_without
        triple = self.triple
        declarer = self.declarer(includer)
        if self.why is NotRead.target_refused:
            refused_with = f" ({_spelled(with_flags)})" if with_flags else ""
            without = f", and without {_spelled(left_out)}" if left_out else ""
            why = (
                f"it refused the target {triple} that {declarer} names with the entry's "
                f"flags{refused_with}{without}"
            )
        elif self.why is NotRead.prefix_unmodelled:
            arch = triple.split("-", 1)[0]
            why = (
                f"{declarer} carries the target {triple}, whose architecture {arch} it "
                f"does not model"
            )
        else:
            why = f"the target {triple} that {declarer} names is not one it models"
        if self.by is TargetSource.setting and self.why is NotRead.target_refused:
            setting = (
                "; or set the `[preprocessor] target` setting to a triple that libclang "
                "accepts with those flags"
            )
        elif self.by is TargetSource.setting:
            setting = (
                "; or set the `[preprocessor] target` setting to a triple that libclang "
                "models"
            )
        else:
            setting = (
                " (the `[preprocessor] target` setting does not override what the build "
                "declares)"
            )
        return (
            f"codelinks: {file} is read as written, no `#if` arm left out, as the libclang "
            f"sphinx-codelinks loaded cannot read its build's target: {why}. Nothing is "
            f"hidden: every marker is kept, only less precisely; to accept that, add "
            f"`codelinks.preprocessor_target_unknown` to Sphinx's `suppress_warnings`"
            f"{setting}"
        )

    def declarer(self, includer: bool) -> str:
        """Who declared it, as the finding names them; ``includer`` when the file is
        read through the entry that includes it."""
        whose = "its includer's" if includer else "its"
        if self.by is TargetSource.entry:
            return f"{whose} compilation-database entry's `{self.flag}`"
        if self.by is TargetSource.compiler_name:
            return f"{whose} compiler's name"
        return "the `[preprocessor] target` setting"


_UNKNOWN = frozenset({NotRead.unmodelled, NotRead.target_refused})
"""The reasons that leave a file's target unknown (:attr:`Decision.unknown`)."""


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
    flag: str = ""
    """How the entry wrote its own triple (:attr:`TargetSource.entry`): ``--target`` or
    ``-target``; empty otherwise."""
    unmodelled: Unmodelled | None = None
    """Why the file is not read for the target its build declares, as declared: the
    first declared triple libclang does not model (the file is read for :attr:`source`
    instead), else, on a parse made :func:`again`, the refusal: the inserted triple
    refused with and without the entry's :data:`REFUSABLE_FLAGS` (read for the host),
    else those flags refused (read for the same target without them). A refusal that
    changes the target read wins over an unmodelled triple, one that leaves it does
    not; :attr:`left_out` names the flags either way."""
    left_out: tuple[str, ...] = ()
    """The entry's :data:`REFUSABLE_FLAGS` left out of the parse that read the file
    (:func:`again`); empty for a parse as decided."""
    refused_with: tuple[str, ...] = ()
    """The entry's other ``-m`` flags, which a declared triple was refused with
    (:attr:`NotRead.target_refused`), named by the warning; empty otherwise."""

    @property
    def unknown(self) -> bool:
        """Whether the file's target is unknown, so that it is read as written (every
        arm of every ``#if`` kept): the build declares a triple the loaded libclang does
        not model (an entry's own, or the setting's for a file that takes it), or
        libclang refused the declared triple (the entry's own, or one the engine
        inserted) with the entry's flags even without its :data:`REFUSABLE_FLAGS`. Not for flags refused with a target that is
        then read (:attr:`NotRead.flags_refused`), nor for a build that declares none
        (the host, stated)."""
        return self.unmodelled is not None and self.unmodelled.why in _UNKNOWN

    def not_read(self) -> tuple[str, str | None] | None:
        """Why the file is not read for the target its build declares, as ubCode's
        report spells it (:attr:`Unmodelled.fallback`), and that target (``None`` for
        the host's own); ``None`` when it is."""
        if self.unmodelled is None:
            return None
        return self.unmodelled.fallback, self.unmodelled.triple or None

    def message(self, file: str, read_for: str, includer: bool) -> str | None:
        """The message of the ``preprocessor_target_unknown`` finding about ``file``,
        read for ``read_for`` (the triple libclang parsed it for), through its includer
        when ``includer``; ``None`` when the file is read for the target its build
        declares. Worded as ubCode's finding is."""
        unmodelled = self.unmodelled
        if unmodelled is None:
            return None
        if self.unknown:
            return unmodelled.as_written_message(
                file, (self.refused_with, self.left_out), includer
            )
        nxt = (
            "the `[preprocessor] target` setting"
            if self.source is TargetSource.setting
            else "the machine sphinx-codelinks runs on"
        )
        triple = unmodelled.triple
        declarer = unmodelled.declarer(includer)
        arms = "so the `#if` arms of the file on the target are not its build's"
        flags = _spelled(self.left_out)
        without = f", without {flags}" if self.left_out else ""
        if unmodelled.why in (NotRead.unmodelled, NotRead.prefix_unmodelled):
            instead = f"{nxt}{without}"
            if unmodelled.why is NotRead.unmodelled:
                why = (
                    f"the target {triple} that {declarer} names is not one the libclang "
                    f"sphinx-codelinks loaded models, {arms}"
                )
            else:
                arch = triple.split("-", 1)[0]
                why = (
                    f"{declarer} carries the target {triple}, whose architecture {arch} "
                    f"the libclang sphinx-codelinks loaded does not model, {arms}"
                )
            if self.left_out:
                why += (
                    f"; and it refused {flags} for the target read instead, which is "
                    f"read without them"
                )
        elif unmodelled.why is NotRead.flags_refused and not triple:
            instead = f"the machine sphinx-codelinks runs on{without}"
            why = (
                f"the libclang sphinx-codelinks loaded refused {flags} for it, so the "
                f"`#if` arms of the file on the CPU and the ABI are its defaults, not its "
                f"build's"
            )
        elif unmodelled.why is NotRead.flags_refused:
            instead = f"the target {triple} that {declarer} names{without}"
            why = (
                f"the libclang sphinx-codelinks loaded refused {flags} with that target, "
                f"so the `#if` arms of the file on the CPU and the ABI are the target's "
                f"defaults, not its build's"
            )
        else:
            instead = f"the machine sphinx-codelinks runs on{without}"
            why = (
                f"the libclang sphinx-codelinks loaded refused the target {triple} that "
                f"{declarer} names with the entry's flags"
                + (f", and without {flags}" if self.left_out else "")
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
        # the build's own declaration left the target unknown: nothing is read after it
        if unmodelled is not None and unmodelled.why in _UNKNOWN:
            break
        if modelled(triple):
            if source.inserted:
                args = _with_target(args, triple)
            return args, Decision(source, triple, flag, unmodelled)
        if source is TargetSource.entry:
            args = _without_own_target(args)
        if unmodelled is None:
            unmodelled = Unmodelled(triple, source, flag)
    return args, Decision(TargetSource.host, None, unmodelled=unmodelled)


def again(args: list[str], decision: Decision) -> list[tuple[list[str], Decision]]:
    """The parses to make again, in order, when the parse of ``args`` for ``decision``
    is refused, each with the decision that reports it.

    Whatever the target's source, keeping the target the parse had and leaving out the
    entry's :data:`REFUSABLE_FLAGS`, when it has any (:attr:`NotRead.flags_refused`:
    clang refuses CPUs and ABIs GCC knows, and the same ones on every machine, so the
    architecture is kept); then, for a declared triple (the entry's own or an inserted
    one), without the triple and those flags (:attr:`NotRead.target_refused`: another
    of the entry's flags refuses the triple, so the target is unknown, and that parse is
    for the file's comments only). The decision's source stays where the target came
    from. None when the parse carries none of those flags and no declared triple:
    nothing is left to leave out but what the build itself passes.
    """
    kept, flags = _without_refusable_flags(args)
    attempts: list[tuple[list[str], Decision]] = []
    if flags:
        unmodelled = decision.unmodelled or Unmodelled(
            decision.declared or "",
            decision.source,
            decision.flag,
            NotRead.flags_refused,
        )
        attempts.append(
            (kept, replace(decision, unmodelled=unmodelled, left_out=flags))
        )
    triple = decision.declared
    if triple is not None:
        if decision.source.inserted:
            inserted = f"--target={triple}"
            without = [arg for arg in kept if arg != inserted]
        else:
            without = _without_own_target(kept)
        refused = Unmodelled(
            triple, decision.source, decision.flag, NotRead.target_refused
        )
        attempts.append(
            (
                without,
                replace(
                    decision,
                    unmodelled=refused,
                    left_out=flags,
                    refused_with=_machine_flags(kept),
                ),
            )
        )
    return attempts


class AllRefused(Exception):
    """Every parse :func:`parse_or_again` made was refused; :attr:`decision` reports
    the last one made, which says whether the file's target is unknown (it is then
    read as written without libclang) or known (it is skipped)."""

    def __init__(self, decision: Decision) -> None:
        super().__init__(f"every parse was refused ({decision.not_read()})")
        self.decision = decision
        """The decision of the last parse made."""


def parse_or_again(
    args: list[str],
    decision: Decision,
    parse: Callable[[list[str], Decision], T],
    refusal: type[Exception] | tuple[type[Exception], ...],
) -> tuple[T, list[str], Decision]:
    """``parse`` of ``args`` for ``decision``, made :func:`again` while it is refused
    (raises ``refusal``): the read, the arguments it was made with and the decision that
    reports it. Each parse is given the decision it is made for, so that one whose
    target is unknown reads the file as written (:attr:`Decision.unknown`). So a
    declared target never leaves a file unread that would be read without it.

    :raises AllRefused: When every parse is refused, with the decision of the last
        one made: the caller reads a file whose target it leaves unknown without
        libclang, and skips any other with a warning (its target is known, and a
        refused flag of its own decides its arms).
    """
    try:
        return parse(args, decision), args, decision
    except refusal as error:
        last: BaseException = error
    refused = decision
    for attempt, refused in again(args, decision):
        try:
            return parse(attempt, refused), attempt, refused
        except refusal as error:
            last = error
    raise AllRefused(refused) from last


def _machine_flags(args: list[str]) -> tuple[str, ...]:
    """The ``-m`` flags of ``args`` (``-mcmse``, ``-mfpmath=vfp``), which pick the
    target's machine, in order; not an option that hands the next argument on
    (``-mllvm``), nor such an option's value."""
    flags: list[str] = []
    arguments = iter(args)
    for arg in arguments:
        if passes_next_argument(arg):
            next(arguments, None)
        elif arg.startswith("-m"):
            flags.append(arg)
    return tuple(flags)


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
