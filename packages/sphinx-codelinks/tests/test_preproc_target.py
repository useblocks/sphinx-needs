"""Which target the libclang engine reads a C/C++ file for (``analyse/preproc/target.py``).

libclang reads no target from a compile command's compiler: left alone it reads every
file for the machine the analysis runs on. The engine reads the target the build
declares -- the entry's own ``--target``, the target its compiler's name carries, the
``[preprocessor] target`` setting -- checked against the loaded libclang, and a parse
refused with an inserted target is made again, so that a target never drops a file.
The shared extraction cases of ``tests/data/extraction/preproc_target.yaml`` pin the
markers; these tests pin the rules one by one, the warnings, and what the shared cases
cannot show on every machine.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

pytest.importorskip("clang.cindex")

from sphinx_codelinks.analyse import analyse as analyse_module
from sphinx_codelinks.analyse.analyse import SourceAnalyse
from sphinx_codelinks.analyse.preproc import libclang_parser, loader, target
from sphinx_codelinks.analyse.preproc.compile_db import (
    compiler_of,
    load_database,
    target_of_compiler,
)
from sphinx_codelinks.analyse.preproc.target import (
    HOST,
    Decision,
    NotRead,
    TargetSource,
    Unmodelled,
    decide,
    own_target,
    parse_or_again,
)
from sphinx_codelinks.config import (
    PreprocessorConfig,
    SourceAnalyseConfig,
    convert_analyse_config,
)
from sphinx_codelinks.source_discover.config import CommentType

from .test_preproc_includer import _RecordingLogger

WD = "-working-directory=/build"


@pytest.mark.parametrize(
    ("compiler", "expected"),
    [
        ("arm-none-eabi-gcc", "arm-none-eabi"),
        ("arm-none-eabi-g++", "arm-none-eabi"),
        ("arm-none-eabi-cc", "arm-none-eabi"),
        ("arm-none-eabi-c++", "arm-none-eabi"),
        ("thumbv7em-none-eabihf-clang", "thumbv7em-none-eabihf"),
        ("thumbv7em-none-eabihf-clang++", "thumbv7em-none-eabihf"),
        ("aarch64-pc-windows-msvc-clang-cl", "aarch64-pc-windows-msvc"),
        ("arm-none-eabi-gcc-13.2.1", "arm-none-eabi"),
        ("aarch64-linux-gnu-gcc-12", "aarch64-linux-gnu"),
        ("arm-none-eabi-gcc13", "arm-none-eabi"),
        ("x86_64-w64-mingw32-gcc-posix", "x86_64-w64-mingw32"),
        ("arm-none-eabi-gcc.exe", "arm-none-eabi"),
        ("ARM-NONE-EABI-GCC.EXE", "arm-none-eabi"),
        ("/opt/zephyr-sdk/bin/arm-zephyr-eabi-gcc", "arm-zephyr-eabi"),
        (r"C:\sdk\bin\riscv64-unknown-elf-gcc.exe", "riscv64-unknown-elf"),
        ("/usr/lib/ccache/arm-linux-gnueabihf-gcc", "arm-linux-gnueabihf"),
        ("avr-gcc", "avr"),
        ("xtensa-esp32-elf-gcc", "xtensa-esp32-elf"),
        ("xc32-gcc", "xc32"),
        ("arm-none-eabi-cpp", "arm-none-eabi"),
        ("musl-gcc", "musl"),
        ("afl-clang-fast", "afl"),
        ("gcc", None),
        ("g++", None),
        ("cc", None),
        ("/usr/bin/c++", None),
        ("clang", None),
        ("clang++", None),
        ("clang-18", None),
        ("/usr/bin/clang++-17", None),
        ("gcc-12", None),
        ("iccarm", None),
        ("armcl", None),
        ("cl2000", None),
        (r"C:\VS\bin\Hostx64\arm64\cl.exe", None),
        ("tiarmclang", None),
        ("ccache", None),
        ("-gcc", None),
        ("", None),
    ],
)
def test_the_compilers_name_declares(compiler: str, expected: str | None) -> None:
    """clang's program-name rule, row by row of ubCode's table (and of its unit test of
    the same rule): a triple prefix before a driver suffix, through a version, ``.exe``
    or a directory; none for a native or a vendor compiler's name."""
    assert target_of_compiler(compiler) == expected


@pytest.mark.parametrize(
    ("argv", "input_file", "expected"),
    [
        (["arm-none-eabi-gcc", "-c", "a.c"], "a.c", "arm-none-eabi-gcc"),
        (["ccache", "arm-none-eabi-gcc", "-c", "a.c"], "a.c", "arm-none-eabi-gcc"),
        (["arm-none-eabi-gcc", "foo-bar.cc", "-c"], "foo-bar.cc", "arm-none-eabi-gcc"),
        (["gcc", "/src/foo-bar.cc", "-c"], "foo-bar.cc", "gcc"),
        (["arm-none-eabi-gcc", "@args.rsp", "-c", "a.c"], "a.c", "arm-none-eabi-gcc"),
        (["-c", "a.c"], "a.c", None),
        ([], "a.c", None),
    ],
)
def test_the_compiler_of_an_entry(
    argv: list[str], input_file: str, expected: str | None
) -> None:
    """The compiler is the last leading non-option word that is neither the entry's own
    file (``foo-bar.cc`` would itself match the ``cc`` suffix) nor a response file."""
    assert compiler_of(argv, input_file) == expected


def test_the_database_reads_each_entrys_compiler(tmp_path: Path) -> None:
    """``load_database`` keeps the target an entry's compiler's name carries beside its
    arguments, which still leave the compiler out; ``command`` entries are split."""
    db = tmp_path / "compile_commands.json"
    db.write_text(
        '[{"directory": ".", "file": "a.c", "arguments": '
        '["ccache", "arm-none-eabi-gcc", "-mthumb", "-c", "a.c"]},'
        ' {"directory": ".", "file": "b.c", "command": "gcc -c b.c"}]'
    )
    database = load_database(db)
    a = database[(tmp_path / "a.c").resolve()]
    assert a.compiler_target == "arm-none-eabi"
    assert a.args == [f"-working-directory={tmp_path.resolve()}", "-mthumb"]
    assert database[(tmp_path / "b.c").resolve()].compiler_target is None


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (["--target=arm-none-eabi"], ("arm-none-eabi", "--target")),
        (["-target", "riscv64-unknown-elf"], ("riscv64-unknown-elf", "-target")),
        (["--target=a-b-c", "-target", "x-y-z"], ("x-y-z", "-target")),
        (["-Xclang", "-target", "-DX"], None),
        (["-target"], None),
        (["-DX", "-mcpu=cortex-m3"], None),
    ],
)
def test_the_entrys_own_target(
    args: list[str], expected: tuple[str, str] | None
) -> None:
    """The entry's own target is the last ``--target=`` or ``-target``, with the flag it
    was written with; the value of a pass-through option is not one."""
    assert own_target(args) == expected


#: The architectures the stand-in libclang models, as clang 18 does (``--target=<arch>``
#: alone parses); ``xtensa``, ``tricore``, ``my``, ``musl`` do not.
ARCHES = {"arm", "aarch64", "x86_64", "powerpc", "riscv32", "riscv64", "thumbv7em"}

#: The words the stand-in libclang reads as a vendor, an OS or an environment.
SYSTEMS = {"elf", "eabi", "linux", "gnu", "musl", "pc"}


def _reads_the_rest(rest: str) -> bool:
    """The stand-in libclang reads a prefix's rest when a word of it is in
    :data:`SYSTEMS`."""
    return any(word in SYSTEMS for word in rest.split("-"))


def _modelled(triple: str) -> bool:
    """The stand-in libclang: a triple is modelled when its first part is one of
    :data:`ARCHES` (libclang normalises the rest of any prefix into some triple)."""
    return triple.split("-", 1)[0] in ARCHES


def _entry(
    args: list[str], compiler: str | None = None, setting: str | None = None
) -> tuple[list[str], Decision]:
    return decide(
        args,
        entry=True,
        compiler=compiler,
        setting=setting,
        modelled=_modelled,
        reads_the_rest=_reads_the_rest,
    )


@pytest.mark.parametrize(
    ("args", "compiler", "setting", "expected", "source"),
    [
        pytest.param(
            [WD, "--target=arm-none-eabi"],
            "aarch64-linux-gnu",
            "x86_64-unknown-linux-gnu",
            [WD, "--target=arm-none-eabi"],
            TargetSource.entry,
            id="own-beats-name",
        ),
        pytest.param(
            [WD, "-mcpu=cortex-m3"],
            "arm-none-eabi",
            None,
            [WD, "--target=arm-none-eabi", "-mcpu=cortex-m3"],
            TargetSource.compiler_name,
            id="name",
        ),
        pytest.param(
            [WD],
            "arm-none-eabi",
            "x86_64-unknown-linux-gnu",
            [WD, "--target=arm-none-eabi"],
            TargetSource.compiler_name,
            id="name-beats-setting",
        ),
        pytest.param(
            [WD, "-DX"],
            None,
            "thumbv7em-none-eabihf",
            [WD, "--target=thumbv7em-none-eabihf", "-DX"],
            TargetSource.setting,
            id="setting",
        ),
        pytest.param(
            [WD],
            None,
            " thumbv7em-none-eabihf ",
            [WD, "--target=thumbv7em-none-eabihf"],
            TargetSource.setting,
            id="padded-setting",
        ),
        pytest.param([WD], None, " ", [WD], TargetSource.host, id="empty-setting"),
        pytest.param(
            [WD, "-DX"], None, None, [WD, "-DX"], TargetSource.host, id="host"
        ),
    ],
)
def test_an_entrys_target(
    args: list[str],
    compiler: str | None,
    setting: str | None,
    expected: list[str],
    source: TargetSource,
) -> None:
    """An entry: its own target wins and nothing is inserted; else its compiler's
    name's, inserted after the working directory; else the setting (trimmed); else the
    host. The setting never overrides what the entry declares."""
    args, decision = _entry(args, compiler, setting)
    assert args == expected
    assert decision.source is source
    assert decision.unmodelled is None


@pytest.mark.parametrize(
    "prefix",
    [
        "my-arm",
        "yocto-aarch64",
        "ci-arm64",
        "host-x86_64",
        "tools-mips",
        "gnu-arm",
        "my",
        "foo-bar",
        "musl",
        "afl",
    ],
)
def test_a_name_without_an_architecture_declares_nothing(prefix: str) -> None:
    """A compiler's name whose first part is not an architecture libclang models, and
    whose rest names no vendor, OS or environment, declares nothing and is not
    reported (a wrapper's name: ``my-arm-gcc``, which libclang would read as
    ``armv4t-my-unknown``); the setting then applies."""
    args, decision = _entry([WD], prefix)
    assert (args, decision) == ([WD], HOST)
    args, decision = _entry([WD], prefix, "riscv32-unknown-elf")
    assert args == [WD, "--target=riscv32-unknown-elf"]
    assert decision == Decision(TargetSource.setting, "riscv32-unknown-elf")


@pytest.mark.parametrize(
    "prefix", ["xtensa-esp32-elf", "xtensa-lx106-elf", "tricore-elf", "sh-elf"]
)
def test_a_gcc_triple_of_an_unmodelled_architecture_is_reported(prefix: str) -> None:
    """A compiler's name whose first part libclang does not model, but whose rest it
    reads as a vendor, an OS or an environment, is a GCC triple of an
    architecture libclang does not have (ESP-IDF's ``xtensa-esp32-elf-gcc``): nothing
    is inserted, the prefix is reported, and (decision 3) the target is unknown, the
    setting not read either."""
    args, decision = _entry([WD], prefix)
    assert args == [WD]
    reported = Unmodelled(
        prefix, TargetSource.compiler_name, why=NotRead.prefix_unmodelled
    )
    assert decision == Decision(TargetSource.host, unmodelled=reported)
    # decision 3: the build's target, unknown, so the file is read as written
    assert decision.unknown
    # the setting is not read either: it does not override what the build declares
    args, decision = _entry([WD], prefix, "riscv32-unknown-elf")
    assert args == [WD]
    assert decision.source is TargetSource.host
    assert decision.unmodelled == reported
    assert decision.unknown


@pytest.mark.parametrize(
    ("args", "compiler", "setting", "expected", "source", "unmodelled"),
    [
        pytest.param(
            [WD, "-target", "xtensa-esp32-elf", "-DX"],
            "arm-none-eabi",
            None,
            [WD, "-DX"],
            TargetSource.host,
            Unmodelled("xtensa-esp32-elf", TargetSource.entry, "-target"),
            id="own",
        ),
        pytest.param(
            [WD, "--target=xtensa-esp32-elf"],
            None,
            "riscv32-unknown-elf",
            [WD],
            TargetSource.host,
            Unmodelled("xtensa-esp32-elf", TargetSource.entry, "--target"),
            id="own-not-the-setting",
        ),
        pytest.param(
            [WD],
            None,
            "tricore-elf",
            [WD],
            TargetSource.host,
            Unmodelled("tricore-elf", TargetSource.setting),
            id="setting",
        ),
        pytest.param(
            [WD, "--target=xtensa-esp32-elf"],
            None,
            "tricore-elf",
            [WD],
            TargetSource.host,
            Unmodelled("xtensa-esp32-elf", TargetSource.entry, "--target"),
            id="own-and-setting",
        ),
    ],
)
def test_an_unmodelled_triple_is_no_declaration(
    args: list[str],
    compiler: str | None,
    setting: str | None,
    expected: list[str],
    source: TargetSource,
    unmodelled: Unmodelled,
) -> None:
    """A declared triple libclang does not model is not read: an entry's own is
    removed (libclang would refuse the parse), and neither its compiler's name nor the
    setting is then read (S2 fix round 1: the build's own declaration wins, and leaves
    the target unknown); a setting libclang does not model leaves the host's parse. The
    first one is reported, as the entry wrote it."""
    args, decision = _entry(args, compiler, setting)
    assert args == expected
    assert decision.source is source
    assert decision.unmodelled == unmodelled
    message = decision.message("src/a.c", "x86_64-pc-linux-gnu", includer=False)
    assert message is not None
    # S2: the target is unknown, the file read as written, whatever was parsed for
    assert decision.unknown
    assert message.startswith(
        "codelinks: src/a.c is read as written, no `#if` arm left out"
    )
    assert "x86_64" not in message
    assert unmodelled.triple in message


def test_a_file_without_an_entry_reads_the_setting_alone() -> None:
    """A file with no entry of its own (a header, the defines path): the setting,
    inserted first (there is no working directory), else the host; a compiler's name
    is not its, and its arguments' own ``--target`` is not read."""
    args, decision = decide(
        ["-x", "c"],
        entry=False,
        compiler="aarch64-linux-gnu",
        setting="thumbv7em-none-eabihf",
        modelled=_modelled,
    )
    assert args == ["--target=thumbv7em-none-eabihf", "-x", "c"]
    assert decision.source is TargetSource.setting
    args, decision = decide(
        ["-x", "c"], entry=False, compiler="aarch64-linux-gnu", modelled=_modelled
    )
    assert (args, decision) == (["-x", "c"], HOST)


def test_the_check_decides_what_is_inserted() -> None:
    """Mutation proof for the libclang check: with every triple accepted, an unmodelled
    one would be inserted (and the parse refused)."""
    args, decision = decide(
        [WD], entry=True, compiler="xtensa-esp32-elf", modelled=lambda _t: True
    )
    assert args == [WD, "--target=xtensa-esp32-elf"]
    assert decision.source is TargetSource.compiler_name
    assert _entry([WD], "xtensa-esp32-elf")[0] == [WD]


class _Refused(Exception):
    """The injected parser's refusal (``TranslationUnitLoadError``)."""


def _parser(
    refuses: Callable[[list[str]], bool],
    as_written: list[bool] | None = None,
) -> tuple[Callable[[list[str], Decision], str], list[list[str]]]:
    """A parser that refuses the arguments ``refuses`` says, and the calls it got;
    ``as_written`` collects whether each parse was made for an unknown target."""
    calls: list[list[str]] = []

    def parse(args: list[str], decision: Decision) -> str:
        calls.append(args)
        if as_written is not None:
            as_written.append(decision.unknown)
        if refuses(args):
            raise _Refused
        return "read"

    return parse, calls


ENTRY = [WD, "-mcpu=e200z4", "-mabi=spe", "-resource-dir", "/r"]


@pytest.mark.parametrize(
    ("compiler", "setting", "triple", "by"),
    [
        pytest.param(
            "powerpc-eabi", None, "powerpc-eabi", TargetSource.compiler_name, id="name"
        ),
        pytest.param(
            None,
            "thumbv7em-none-eabihf",
            "thumbv7em-none-eabihf",
            TargetSource.setting,
            id="setting",
        ),
    ],
)
def test_a_refused_insertion_is_read_without_the_entrys_cpu(
    compiler: str | None, setting: str | None, triple: str, by: TargetSource
) -> None:
    """Step 2 of the chain: a parse refused with an inserted target is made again
    keeping the target, without the entry's ``-mcpu=`` / ``-march=`` / ``-mtune=`` /
    ``-mabi=``, and the decision names the flags left out; its source stays."""
    args, decision = _entry(ENTRY, compiler, setting)
    parse, calls = _parser(lambda attempt: "-mcpu=e200z4" in attempt)
    read, used, reported = parse_or_again(args, decision, parse, _Refused)
    assert read == "read"
    assert used == [WD, f"--target={triple}", "-resource-dir", "/r"]
    assert len(calls) == 2
    assert reported.source is by
    assert reported.unmodelled == Unmodelled(triple, by, why=NotRead.flags_refused)
    assert reported.left_out == ("-mcpu=e200z4", "-mabi=spe")
    assert reported.not_read() == ("flags_refused", triple)
    assert reported.message("a.c", "powerpc-unknown-unknown-eabi", False) == (
        f"codelinks: a.c is read for powerpc-unknown-unknown-eabi (the target {triple} "
        f"that {reported.unmodelled.declarer(False)} names, without `-mcpu=e200z4`, "
        f"`-mabi=spe`): the libclang sphinx-codelinks loaded refused `-mcpu=e200z4`, "
        f"`-mabi=spe` with that target, so the `#if` arms of the file on the CPU and "
        f"the ABI are the target's defaults, not its build's"
    )


def test_a_target_refused_without_the_cpu_too_is_read_as_written() -> None:
    """Step 3: refused without the CPU flags too, the file is parsed without the target
    and those flags, for its comments only: its target is unknown, and it is read as
    written (S2: the host is not the build's target). Each parse is given the decision
    it is made for: only the last is read as written. The decision names the triple
    refused, and its source stays where the triple came from."""
    args, decision = _entry(ENTRY, "powerpc-eabi")
    as_written: list[bool] = []
    parse, calls = _parser(
        lambda attempt: "--target=powerpc-eabi" in attempt, as_written
    )
    read, used, reported = parse_or_again(args, decision, parse, _Refused)
    assert read == "read"
    assert used == [WD, "-resource-dir", "/r"]
    assert len(calls) == 3
    assert as_written == [False, False, True]
    assert reported.unknown
    assert reported == Decision(
        TargetSource.compiler_name,
        "powerpc-eabi",
        unmodelled=Unmodelled(
            "powerpc-eabi", TargetSource.compiler_name, why=NotRead.target_refused
        ),
        left_out=("-mcpu=e200z4", "-mabi=spe"),
        refused_with=(),
    )
    assert reported.message("a.c", "x86_64-unknown-linux-gnu", True) == (
        "codelinks: a.c is read as written, no `#if` arm left out, as the libclang "
        "sphinx-codelinks loaded cannot read its build's target: it refused the target "
        "powerpc-eabi that its includer's compiler's name names with the entry's flags, "
        "and without `-mcpu=e200z4`, `-mabi=spe`. Nothing is hidden: every marker is "
        "kept, only less precisely; to accept that, add "
        "`codelinks.preprocessor_target_unknown` to Sphinx's `suppress_warnings` (the "
        "`[preprocessor] target` setting does not override what the build declares)"
    )


def test_without_cpu_flags_the_chain_goes_to_the_host() -> None:
    """An entry with no flag to leave out has no step 2 (the same parse again)."""
    args, decision = _entry([WD, "-DX"], "powerpc-eabi")
    parse, calls = _parser(lambda attempt: "--target=powerpc-eabi" in attempt)
    _, used, reported = parse_or_again(args, decision, parse, _Refused)
    assert used == [WD, "-DX"]
    assert len(calls) == 2
    assert reported.not_read() == ("target_refused", "powerpc-eabi")
    assert reported.left_out == ()
    message = reported.message("a.c", "x86_64-unknown-linux-gnu", False)
    assert message is not None
    assert "is read as written" in message
    assert "names with the entry's flags. Nothing is hidden" in message


@pytest.mark.parametrize(
    ("args", "triple", "flag", "instead"),
    [
        pytest.param(
            [WD, "-target", "aarch64-linux-gnu", "-mcpu=cortex-x925", "-DX"],
            "aarch64-linux-gnu",
            "-target",
            "(the target aarch64-linux-gnu that its compilation-database entry's "
            "`-target` names, without `-mcpu=cortex-x925`)",
            id="own",
        ),
        pytest.param(
            [WD, "-march=rv32imac_zicsr", "-DX"],
            None,
            "",
            "(the machine sphinx-codelinks runs on, without `-march=rv32imac_zicsr`): "
            "the libclang sphinx-codelinks loaded refused `-march=rv32imac_zicsr` for it",
            id="host",
        ),
    ],
)
def test_a_target_not_inserted_is_kept_without_the_flags(
    args: list[str], triple: str | None, flag: str, instead: str
) -> None:
    """ubCode fix round 3: a target the decision did not insert (an entry's own, the
    host's) is kept, and the parse made again without the CPU and ABI flags alone,
    never for the host without the target; reported as ``flags_refused``, naming the
    entry's own triple as it wrote it, or no triple for the host."""
    args, decision = _entry(args)
    parse, calls = _parser(lambda attempt: any("-m" in arg for arg in attempt))
    _, used, reported = parse_or_again(args, decision, parse, _Refused)
    assert len(calls) == 2
    assert used == [arg for arg in args if not arg.startswith(("-mcpu=", "-march="))]
    assert reported.source is decision.source
    assert reported.not_read() == ("flags_refused", triple)
    assert reported.unmodelled is not None
    assert reported.unmodelled.flag == flag
    message = reported.message("a.c", "x86_64-pc-linux-gnu", False)
    assert message is not None
    assert instead in message


def test_the_host_with_nothing_to_leave_out_is_not_made_again() -> None:
    """A parse for the host, nothing declared, that carries none of the CPU and ABI
    flags is not made again: its refusal is the file's, as before targets were read;
    its target known, the file is read as written (:meth:`.Decision.refused`)."""
    args, decision = _entry([WD, "-DX"])
    parse, calls = _parser(lambda _attempt: True)
    with pytest.raises(target.AllRefused) as refused:
        parse_or_again(args, decision, parse, _Refused)
    assert len(calls) == 1
    assert not refused.value.decision.unknown


@pytest.mark.parametrize(
    ("args", "flag", "steps"),
    [
        pytest.param([WD, "--target=arm-none-eabi", "-mcmse"], "--target", 2, id="own"),
        pytest.param(
            [WD, "-target", "arm-none-eabi", "-mcpu=cortex-m4", "-mcmse"],
            "-target",
            3,
            id="own-with-cpu",
        ),
    ],
)
def test_an_entrys_own_target_refused_without_the_cpu_too_is_unknown(
    args: list[str], flag: str, steps: int
) -> None:
    """ubCode S2 fix round 1: an entry's own target clang refuses with its flags, even
    without its CPU flags, is unknown too (``target_refused``, declared by the entry):
    the last parse leaves out the target and those flags, for the comments only, and
    names the ``-m`` flags it was refused with."""
    args, decision = _entry(args)
    as_written: list[bool] = []
    parse, calls = _parser(
        lambda attempt: any(arg.startswith(("--target", "-target")) for arg in attempt),
        as_written,
    )
    _, used, reported = parse_or_again(args, decision, parse, _Refused)
    assert len(calls) == steps
    assert as_written[-1] and not any(as_written[:-1])
    assert used == [WD, "-mcmse"]
    assert reported.source is TargetSource.entry
    assert reported.not_read() == ("target_refused", "arm-none-eabi")
    assert reported.refused_with == ("-mcmse",)
    message = reported.message("a.c", "", False)
    assert message is not None
    assert (
        f"it refused the target arm-none-eabi that its compilation-database entry's "
        f"`{flag}` names with the entry's flags (its `-m` flags: `-mcmse`)" in message
    )


def test_the_reason_that_decides_the_target_read_wins() -> None:
    """Which reason is given where there are two: an unmodelled triple wins over flags
    left out with the target read instead (the target is the same; the warning names
    both), and a refused inserted triple wins over an unmodelled one (it changes the
    target again)."""
    args, decision = _entry(
        [WD, "-march=rv32imac_zicsr", "-mabi=ilp32"], "riscv-none-elf"
    )
    assert decision.not_read() == ("prefix_unmodelled", "riscv-none-elf")
    [(_, refused)] = target.again(args, decision)
    assert refused.not_read() == ("prefix_unmodelled", "riscv-none-elf")
    message = refused.message("a.c", "x86_64-pc-linux-gnu", False)
    assert message is not None
    # read as written (decision 3), the flags left out of the parse decide nothing,
    # and are not named
    assert "is read as written" in message
    assert "carries the target riscv-none-elf" in message
    assert "-march" not in message
    # an entry's own xtensa: the setting is not read, nothing is inserted, and its CPU
    # flags left out keep the reason
    args, decision = _entry(
        [WD, "--target=xtensa-esp32-elf", "-mcpu=e200z4"], None, "powerpc-eabi"
    )
    assert args == [WD, "-mcpu=e200z4"]
    assert decision.not_read() == ("unmodelled", "xtensa-esp32-elf")
    [(_, refused)] = target.again(args, decision)
    assert refused.not_read() == ("unmodelled", "xtensa-esp32-elf")
    # an inserted target refused without the CPU flags too wins over an unmodelled
    # setting's reason: it changes the target read again
    unmodelled = Decision(
        TargetSource.compiler_name,
        "powerpc-eabi",
        unmodelled=Unmodelled("tricore-elf", TargetSource.setting),
    )
    attempts = target.again([WD, "--target=powerpc-eabi", "-mcpu=e200z4"], unmodelled)
    assert attempts[0][1].not_read() == ("setting_unmodelled", "tricore-elf")
    assert attempts[1][1].not_read() == ("target_refused", "powerpc-eabi")
    # a setting libclang does not model is said to be the setting's
    _, decision = _entry([WD], None, "tricore-elf")
    assert decision.not_read() == ("setting_unmodelled", "tricore-elf")


def test_a_refusal_at_every_step_is_the_files() -> None:
    """Refused at every step, :class:`.target.AllRefused` is raised with the decision of
    the last parse made: here an unknown one, so the caller reads the file as written
    without libclang."""
    args, decision = _entry(ENTRY, "powerpc-eabi")
    parse, calls = _parser(lambda _attempt: True)
    with pytest.raises(target.AllRefused) as refused:
        parse_or_again(args, decision, parse, _Refused)
    assert len(calls) == 3
    assert refused.value.decision.unknown
    assert refused.value.decision.not_read() == ("target_refused", "powerpc-eabi")


#: The opening of a ``preprocessor_parse_refused`` warning about ``a.c``, up to whose
#: flags it names, for a flag refused for the target (``CXError_Failure``).
REFUSED_OPENING = (
    "codelinks: a.c is read as written, no `#if` arm left out, without libclang: the "
    "libclang sphinx-codelinks loaded refused every parse of it for the machine "
    "sphinx-codelinks runs on (its build names no target) with the flags of "
)


@pytest.mark.parametrize(
    ("args", "whose", "fix_in", "says"),
    [
        pytest.param(
            [WD, "-mfpmath=vfp", "-DX"],
            "its compilation-database entry",
            "the compilation database",
            "its compilation-database entry (its `-m` flags: `-mfpmath=vfp`) (",
            id="own-entry",
        ),
        pytest.param(
            [WD, "-mcpu=cortex-r52plus", "-mfpmath=vfp"],
            "the compilation-database entry of its includer /m.c",
            "the compilation database",
            "the compilation-database entry of its includer /m.c (its `-m` flags: "
            "`-mfpmath=vfp`), and without `-mcpu=cortex-r52plus` (",
            id="cpu-left-out",
        ),
        pytest.param(
            [WD, "-DX"],
            "its compilation-database entry",
            "the compilation database",
            "its compilation-database entry (",
            id="no-machine-flag",
        ),
    ],
)
def test_every_parse_refused_reads_as_written_for_a_known_target(
    args: list[str], whose: str, fix_in: str, says: str
) -> None:
    """useblocks/ubcode#4862 (ubCode's
    ``every_parse_refused_reads_as_written_for_a_known_target``): a file whose every
    parse libclang refused for a target it reads, with a flag (``CXError_Failure``; the
    host's, after the CPU flags were left out too), is ``parse_refused``: read as
    written, its target known (``host``, not unknown), naming the entry's ``-m`` flags
    and the CPU flags left out, and the remedy, through the arguments ``whose`` names.
    A decision whose parse read gives no such message, and the refused one no
    ``preprocessor_target_unknown`` one."""
    args, decision = _entry(args)
    assert decision.refused_message("a.c", whose, fix_in) is None
    # the parse made again without the CPU flags, refused too, is the decision the
    # refusal is read from when there is one
    attempts = target.again(args, decision)
    last = attempts[-1][1] if attempts else decision
    refused = last.refused(args, command=False)
    assert refused.parse_refused
    assert not refused.unknown
    assert refused.source is TargetSource.host
    assert refused.not_read() == ("parse_refused", None)
    assert refused.command == ()
    assert refused.message("a.c", "", False) is None
    assert refused.refused_message("a.c", whose, fix_in) == (
        f"{REFUSED_OPENING}{says}libclang does not say which flag it refused). Nothing "
        f"is hidden: every marker is kept, only less precisely. To read it for its "
        f"target, remove or change the refused flag in {fix_in}; to accept it as "
        f"written, add `codelinks.preprocessor_parse_refused` to Sphinx's "
        f"`suppress_warnings`"
    )


#: The opening of a ``preprocessor_parse_refused`` warning about ``a.c`` whose
#: command libclang refused (``CXError_ASTReadError``), for its own entry.
COMMAND_OPENING = (
    "codelinks: a.c is read as written, no `#if` arm left out, without libclang: the "
    "libclang sphinx-codelinks loaded refused the arguments of its compilation-database "
    "entry, which hold a flag or an input file it does not take "
)

#: The end of a ``preprocessor_parse_refused`` warning whose command libclang
#: refused, after the arguments it lists.
COMMAND_CLOSING = (
    " Nothing is hidden: every marker is kept, only less precisely. To read it, remove "
    "or change what libclang does not take in {fix_in}; to accept it as written, add "
    "`codelinks.preprocessor_parse_refused` to Sphinx's `suppress_warnings`"
)


@pytest.mark.parametrize(
    ("args", "says"),
    [
        pytest.param(
            [WD, "-O2", "-D", "X", "-include", "pre.h", "b.c", "-resource-dir", "/r"],
            "(libclang does not say which; input files besides this one: `b.c`): "
            "`-O2`, `-D`, `X`, `-include`, `pre.h`, `b.c`.",
            id="second-input",
        ),
        pytest.param(
            [WD, "-std=gnu2y", "-mfpmath=vfp"],
            "(libclang does not say which): `-std=gnu2y`, `-mfpmath=vfp`.",
            id="unknown-std",
        ),
        pytest.param(
            [WD, *(f"-a{n}" for n in range(1, 15))],
            "(libclang does not say which): `-a1`, `-a2`, `-a3`, `-a4`, `-a5`, `-a6`, "
            "`-a7`, `-a8`, `-a9`, `-a10`, `-a11`, `-a12`, and 2 more.",
            id="bounded",
        ),
        pytest.param(
            [WD, *(f"-a{n}" for n in range(1, 13))],
            "(libclang does not say which): `-a1`, `-a2`, `-a3`, `-a4`, `-a5`, `-a6`, "
            "`-a7`, `-a8`, `-a9`, `-a10`, `-a11`, `-a12`.",
            id="twelve-all-listed",
        ),
        pytest.param(
            [WD, "-Xclang", "-foo", "-Xlinker", "lib.a", "-o", "app", "-arch", "arm64"],
            "(libclang does not say which): `-Xclang`, `-foo`, `-Xlinker`, `lib.a`, "
            "`-o`, `app`, `-arch`, `arm64`.",
            id="option-values-are-no-inputs",
        ),
        pytest.param(
            [WD, "b.c", "c.c"],
            "(libclang does not say which; input files besides this one: `b.c`, "
            "`c.c`): `b.c`, `c.c`.",
            id="two-more-inputs",
        ),
        pytest.param([WD], "(libclang does not say which): none.", id="none"),
    ],
)
def test_a_refused_command_lists_its_arguments(args: list[str], says: str) -> None:
    """ubCode's ``a_refused_command_lists_its_arguments``: a command libclang refused
    whatever the target (a second input file, a ``-std`` it does not know) is
    ``command_refused``, read as the target's refusal is; its warning lists the entry's
    arguments (not the engine's own: the working directory, the resource directory), at
    most twelve, names the input files besides the entry's own (not an option's value,
    nor what an option hands on), and names no target and no ``-m`` flag."""
    args, decision = _entry(args)
    refused = decision.refused(args, command=True)
    assert refused.parse_refused and not refused.unknown
    assert refused.not_read() == ("command_refused", None)
    assert refused.refused_with == () and refused.left_out == ()
    assert refused.message("a.c", "", False) is None
    assert refused.refused_message(
        "a.c", "its compilation-database entry", "the compilation database"
    ) == (
        f"{COMMAND_OPENING}{says}"
        f"{COMMAND_CLOSING.format(fix_in='the compilation database')}"
    )


def test_a_refused_command_leaves_out_only_the_engines_own_arguments() -> None:
    """The arguments a refused command's warning lists are the entry's: the
    ``--target=`` the engine inserted for a compiler's name is left out, while an
    entry's own ``--target=`` is kept (it is the entry's), as are its values."""
    args, decision = _entry([WD, "-std=gnu2y"], compiler="arm-none-eabi-gcc")
    assert f"--target={decision.declared}" in args
    assert decision.refused(args, command=True).command == ("-std=gnu2y",)
    args, decision = _entry([WD, "--target=arm-none-eabi", "-std=gnu2y"])
    assert decision.refused(args, command=True).command == (
        "--target=arm-none-eabi",
        "-std=gnu2y",
    )


def test_a_refused_decision_keeps_where_its_target_came_from() -> None:
    """:meth:`.Decision.refused` keeps the decision's source, triple and flag, names
    the triple when one is declared (the message then says which), and lists the
    ``-m`` flags of the parse's own arguments: not the value of an option that hands
    its argument on (``-mllvm``), nor the :data:`.target.REFUSABLE_FLAGS`, which it
    lists as left out."""
    args, decision = _entry(
        [WD, "--target=arm-none-eabi", "-mllvm", "-mx", "-march=armv7", "-mthumb"]
    )
    refused = decision.refused(args, command=False)
    assert refused.parse_refused and not refused.unknown
    assert (refused.source, refused.declared, refused.flag) == (
        TargetSource.entry,
        "arm-none-eabi",
        "--target",
    )
    assert refused.not_read() == ("parse_refused", "arm-none-eabi")
    assert refused.refused_with == ("-mthumb",)
    assert refused.left_out == ("-march=armv7",)
    message = refused.refused_message("a.c", "x", "y")
    assert message is not None
    assert (
        "refused every parse of it for the target arm-none-eabi with the flags of x"
        in (message)
    )


@pytest.mark.parametrize(
    ("args", "code"),
    [
        pytest.param(["-mfpmath=vfp"], loader.ParseError.failure, id="mfpmath-vfp"),
        pytest.param(["other.c"], loader.ParseError.ast_read_error, id="second-input"),
        pytest.param(["-std=gnu2y"], loader.ParseError.ast_read_error, id="gnu2y"),
        pytest.param(["-std=c99x"], loader.ParseError.ast_read_error, id="c99x"),
        pytest.param(
            ["-Xclang", "-foo"], loader.ParseError.ast_read_error, id="xclang-foo"
        ),
    ],
)
def test_libclang_says_why_it_refused_a_parse(
    tmp_path: Path, args: list[str], code: loader.ParseError
) -> None:
    """What decides a refused parse's wording, measured with the pinned libclang (18.1):
    ``clang_parseTranslationUnit2`` reports ``CXError_Failure`` for a flag the target
    does not take (``-mfpmath=vfp``, on every machine), and ``CXError_ASTReadError``
    for a command it cannot run at all, whatever the target (a second input file, a
    ``-std`` it does not know, an unknown ``-Xclang`` flag);
    :func:`.loader.refused_by_command` tells the two apart. A parse that reads raises
    nothing."""
    (tmp_path / "a.c").write_text("int a;\n")
    (tmp_path / "other.c").write_text("int other;\n")
    wd = f"-working-directory={tmp_path}"
    assert libclang_parser.parse_translation_unit(tmp_path / "a.c", [wd]) is not None
    with pytest.raises(loader.load_clang_cindex().TranslationUnitLoadError) as error:
        libclang_parser.parse_translation_unit(tmp_path / "a.c", [wd, *args])
    assert loader.parse_error(error.value) is code
    assert loader.refused_by_command(error.value) is (
        code is not loader.ParseError.failure
    )
    assert not loader.refused_by_command(ValueError("no code"))


def test_a_pass_through_value_is_not_left_out() -> None:
    """The value of an option that hands its argument on is kept with it."""
    args, decision = _entry([WD, "-Xclang", "-mcpu=x", "-march=y"], "powerpc-eabi")
    attempts = target.again(args, decision)
    assert attempts[0][0] == [WD, "--target=powerpc-eabi", "-Xclang", "-mcpu=x"]


# --- against the loaded libclang ------------------------------------------------------


@pytest.mark.parametrize(
    ("triple", "modelled"),
    [
        ("arm-none-eabi", True),
        ("thumbv7em-none-eabihf", True),
        ("powerpc-eabi", True),
        ("arm", True),
        ("xtensa-esp32-elf", False),
        ("tricore-elf", False),
        ("xtensa", False),
        ("my", False),
        ("musl", False),
    ],
)
def test_the_loaded_libclang_decides_what_is_modelled(
    triple: str, modelled: bool
) -> None:
    """The check asks the loaded libclang (an empty in-memory parse per triple)."""
    assert target.modelled_by(triple) is modelled


@pytest.mark.parametrize(
    ("rest", "reads"),
    [
        ("esp32-elf", True),
        ("lx106-elf", True),
        ("elf", True),
        ("linux-gnu", True),
        ("musl", True),
        ("pc", True),
        ("arm", False),
        ("bar", False),
        ("aarch64", False),
        ("x86_64", False),
    ],
)
def test_the_loaded_libclang_reads_the_rest(rest: str, reads: bool) -> None:
    """A name prefix's rest names a vendor, an OS or an environment when libclang moves
    a word of it into its slot as it normalises ``x86_64-unknown-unknown-unknown-<rest>``
    (ubCode's probe); a word it does not read stays where it is."""
    assert target.reads_the_rest(rest) is reads


def test_each_check_asks_the_loaded_libclang_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The checks are memoised per libclang (its version string) and question: a
    second ask of the same triple or rest parses nothing."""
    assert target._version().startswith("clang version ")
    assert target._version() == target._version()
    probes: list[list[str]] = []
    probe = target._probe

    def counting(args: list[str]) -> object:
        probes.append(args)
        return probe(args)

    monkeypatch.setattr(target, "_probe", counting)
    monkeypatch.setattr(target, "_MODELLED", {})
    monkeypatch.setattr(target, "_SYSTEMS", {})
    for _ in range(2):
        assert target.modelled_by("arm-none-eabi")
        assert target.reads_the_rest("esp32-elf")
    assert len(probes) == 2


def _analyse(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source: str,
    argv: list[str] | None,
    setting: str | None = None,
    name: str = "case.c",
    reasons: list[tuple[str, str | None]] | None = None,
    std: str = "c11",
) -> tuple[set[str], list[tuple[str, str]]]:
    """Run the libclang engine on ``source`` (one entry of ``argv``, or none: the
    defines path) and return the ids extracted and the warnings; ``reasons`` collects
    each warned file's reason and declared triple, as ubCode's report names them
    (:meth:`.Decision.not_read`)."""
    src = tmp_path / name
    src.write_text(source)
    db = None
    if argv is not None:
        db = tmp_path / "compile_commands.json"
        db.write_text(
            json.dumps([{"directory": str(tmp_path), "file": name, "arguments": argv}])
        )
    recorder = _RecordingLogger()
    monkeypatch.setattr(analyse_module, "logger", recorder)
    if reasons is not None:
        warn = SourceAnalyse._warn_target

        def recording(
            self: SourceAnalyse,
            path: Path,
            decision: Decision,
            read_for: str,
            *,
            includer: bool,
        ) -> None:
            not_read = decision.not_read()
            if not_read is not None:
                reasons.append(not_read)
            warn(self, path, decision, read_for, includer=includer)

        monkeypatch.setattr(SourceAnalyse, "_warn_target", recording)
    analyse = SourceAnalyse(
        SourceAnalyseConfig(
            src_files=[src],
            src_dir=tmp_path,
            comment_type=CommentType.cpp,
            get_oneline_needs=True,
            preprocessor=PreprocessorConfig(
                compile_commands=db, std=std, target=setting
            ),
        )
    )
    analyse.git_remote_url = None
    analyse.git_commit_rev = None
    analyse.run()
    ids = {need.need["id"] for need in analyse.oneline_needs}
    return ids, recorder.warnings


ARMS = (
    "// @Always, IMPL_ALWAYS, impl\n"
    "#if defined(__x86_64__)\n// @x86, IMPL_X86, impl\n"
    "#elif defined(__aarch64__)\n// @a64, IMPL_A64, impl\n"
    "#elif defined(__PPC__)\n// @ppc, IMPL_PPC, impl\n"
    "#elif defined(__arm__)\n// @arm, IMPL_ARM, impl\n"
    "#else\n// @other, IMPL_OTHER, impl\n#endif\n"
)


@pytest.mark.parametrize(
    ("argv", "arm", "refused"),
    [
        pytest.param(
            ["powerpc-eabi-gcc", "-mcpu=e200z4", "-c", "case.c"],
            "IMPL_PPC",
            "-mcpu=e200z4",
            id="powerpc-e200z4",
        ),
        pytest.param(
            ["arm-none-eabi-gcc", "-mcpu=cortex-r52plus", "-c", "case.c"],
            "IMPL_ARM",
            "-mcpu=cortex-r52plus",
            id="arm-cortex-r52plus",
        ),
        pytest.param(
            ["aarch64-linux-gnu-gcc", "-mcpu=cortex-a76.cortex-a55", "-c", "case.c"],
            "IMPL_A64",
            "-mcpu=cortex-a76.cortex-a55",
            id="aarch64-big-little",
        ),
    ],
)
def test_a_cpu_clang_refuses_keeps_the_file_and_its_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    argv: list[str],
    arm: str,
    refused: str,
) -> None:
    """A CPU GCC knows and clang 18 refuses with the target the compiler's name carries
    (ubCode fix rounds 1 and 2): the file is not dropped, and it is read for that
    target without the CPU, so the markers are the same on every machine; the warning
    names the triple and the flag."""
    ids, warnings = _analyse(tmp_path, monkeypatch, ARMS, argv)
    assert ids == {"IMPL_ALWAYS", arm}
    [(message, subtype)] = warnings
    assert subtype == "preprocessor_target_unknown"
    assert f"names, without `{refused}`): " in message
    assert f"loaded refused `{refused}` with that target" in message


#: Every marker of :data:`ARMS`: the file read as written.
ALL_ARMS = {"IMPL_ALWAYS", "IMPL_X86", "IMPL_A64", "IMPL_PPC", "IMPL_ARM", "IMPL_OTHER"}


def test_libclang_refusing_the_target_without_the_cpu_reads_as_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Step 3 against the loaded libclang, on every machine: ``-mcmse`` makes clang
    refuse ``arm-none-eabi`` with or without the CPU (it needs an ARMv8-M one), while
    an x86-64, an Arm64 and a Windows host each accept it for themselves (ubCode's
    example), so the file is parsed for the host with its other flags, for its
    comments only: its target is unknown and it is read as written (S2), every arm
    kept. The reason is asserted, never the host triple's spelling."""
    argv = ["arm-none-eabi-gcc", "-mcpu=cortex-m4", "-mcmse", "-c", "case.c"]
    reasons: list[tuple[str, str | None]] = []
    ids, warnings = _analyse(tmp_path, monkeypatch, ARMS, argv, reasons=reasons)
    assert ids == ALL_ARMS
    assert reasons == [("target_refused", "arm-none-eabi")]
    [(message, subtype)] = warnings
    assert subtype == "preprocessor_target_unknown"
    assert "is read as written, no `#if` arm left out" in message
    assert (
        "refused the target arm-none-eabi that its compiler's name names with the "
        "entry's flags (its `-m` flags: `-mcmse`), and without `-mcpu=cortex-m4`"
        in message
    )


NEED_REFS = "// @Always, IMPL_ALWAYS, impl\nint f(void) { return 0; }\n"


@pytest.mark.parametrize(
    ("argv", "fallback", "declared", "flags"),
    [
        pytest.param(
            [
                "clang",
                "--target=aarch64-linux-gnu",
                "-mcpu=cortex-x925",
                "-c",
                "case.c",
            ],
            "flags_refused",
            "aarch64-linux-gnu",
            ["-mcpu=cortex-x925"],
            id="entry-own",
        ),
        pytest.param(
            [
                "riscv-none-elf-gcc",
                "-march=rv32imac_zicsr",
                "-mabi=ilp32",
                "-c",
                "case.c",
            ],
            "prefix_unmodelled",
            "riscv-none-elf",
            ["-march=rv32imac_zicsr", "-mabi=ilp32"],
            id="xpack-riscv",
        ),
        pytest.param(
            ["gcc", "-march=rv32imac_zicsr", "-mabi=ilp32", "-c", "case.c"],
            "flags_refused",
            None,
            ["-march=rv32imac_zicsr", "-mabi=ilp32"],
            id="native",
        ),
    ],
)
def test_a_refused_cpu_is_left_out_whatever_the_targets_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    argv: list[str],
    fallback: str,
    declared: str | None,
    flags: list[str],
) -> None:
    """ubCode fix round 3: the CPU and ABI flags are left out of ANY refused parse that
    carries them, keeping its target: an entry's own target (a database from a newer
    clang naming a CPU clang 18 does not know); a compiler whose name is no target
    libclang reads (xPack's ``riscv-none-elf-gcc``: ``riscv`` alone is no architecture
    of libclang's, so the host is read, which refuses RISC-V's ``-march``); a native
    compiler (the host's own target). Each was dropped before, on every machine. The
    native row passes ``-mabi=ilp32`` too, as ubCode's does: libclang refuses
    ``-march=rv32imac_zicsr`` for an x86-64 host but only warns for an Arm64 one, which
    refuses ``-mabi=ilp32`` instead, so the pair is refused on every machine. Where the
    target is not the build's for another reason too (``prefix_unmodelled``), that
    reason is given, and the warning names both."""
    reasons: list[tuple[str, str | None]] = []
    ids, warnings = _analyse(tmp_path, monkeypatch, NEED_REFS, argv, reasons=reasons)
    assert ids == {"IMPL_ALWAYS"}, "the file is read, never dropped"
    assert reasons == [(fallback, declared)]
    [(message, subtype)] = warnings
    assert subtype == "preprocessor_target_unknown"
    spelled = "without " + ", ".join(f"`{flag}`" for flag in flags)
    if fallback == "prefix_unmodelled":
        # decision 3: read as written, the flags left out decide nothing
        assert "is read as written" in message
        assert spelled not in message
    else:
        assert spelled in message
    if declared is not None:
        assert declared in message


def test_the_setting_with_a_native_entrys_host_only_flags_keeps_the_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A native entry with the setting and a host-only flag (``gcc -march=native``,
    setting ``thumbv7em-none-eabihf``) is read for the setting's target on every
    machine: clang reports the flag, or refuses it and the chain leaves it out."""
    argv = ["gcc", "-march=native", "-c", "case.c"]
    ids, _ = _analyse(tmp_path, monkeypatch, ARMS, argv, "thumbv7em-none-eabihf")
    assert ids == {"IMPL_ALWAYS", "IMPL_ARM"}


XTENSA = (
    "// @Always, IMPL_ALWAYS, impl\n"
    "#if defined(__XTENSA__)\n// @xtensa, IMPL_XTENSA, impl\n"
    "#else\n// @not xtensa, IMPL_NOT_XTENSA, impl\n#endif\n"
)


@pytest.mark.parametrize(
    ("compiler", "reported"),
    [
        ("xtensa-esp32-elf-gcc", "xtensa-esp32-elf"),
        ("xtensa-lx106-elf-gcc", "xtensa-lx106-elf"),
        ("tricore-elf-gcc", "tricore-elf"),
        ("sh-elf-gcc", "sh-elf"),
        ("nios2-elf-gcc", "nios2-elf"),
        ("nios2-unknown-linux-gnu-gcc", "nios2-unknown-linux-gnu"),
        ("musl-gcc", None),
        ("afl-clang-fast", None),
        ("my-arm-gcc", None),
        ("foo-bar-gcc", None),
        ("my-gcc", None),
    ],
)
def test_a_name_of_an_unmodelled_architecture_is_reported(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    compiler: str,
    reported: str | None,
) -> None:
    """Against the loaded libclang (ubCode fix round 2, ruling 3): a compiler's name
    whose first part libclang does not model and whose rest it reads as a vendor, an OS
    or an environment (ESP-IDF's ``xtensa-esp32-elf-gcc``) is the build's target, one
    libclang cannot read (decision 3): the file is read as written on every machine, the
    arm only Xtensa takes kept too, and reported. A wrapper's name declares nothing and
    stays silent, its file read for the host."""
    ids, warnings = _analyse(tmp_path, monkeypatch, XTENSA, [compiler, "-c", "case.c"])
    if reported is None:
        assert ids == {"IMPL_ALWAYS", "IMPL_NOT_XTENSA"}
        assert warnings == []
        return
    assert ids == {"IMPL_ALWAYS", "IMPL_XTENSA", "IMPL_NOT_XTENSA"}
    [(message, subtype)] = warnings
    assert subtype == "preprocessor_target_unknown"
    arch = reported.split("-", 1)[0]
    assert message == (
        f"codelinks: {tmp_path / 'case.c'} is read as written, no `#if` arm left out, "
        f"as the libclang sphinx-codelinks loaded cannot read its build's target: its "
        f"compiler's name carries the target {reported}, whose architecture {arch} it "
        f"does not model. Nothing is hidden: every marker is kept, only less precisely; "
        f"to accept that, add `codelinks.preprocessor_target_unknown` to Sphinx's "
        f"`suppress_warnings` (the `[preprocessor] target` setting does not override "
        f"what the build declares)"
    )


def test_an_unmodelled_entry_target_is_left_out_and_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An entry's own ``--target`` libclang does not model: passed on, the parse fails
    and the file is dropped. It is left out of the parse, and as the setting does not
    override what the entry declares, the file's target is unknown: it is read as
    written, every arm kept, and the warning names the target and says nothing needs
    doing."""
    argv = ["clang", "--target=xtensa-esp32-elf", "-c", "case.c"]
    reasons: list[tuple[str, str | None]] = []
    ids, warnings = _analyse(
        tmp_path, monkeypatch, ARMS, argv, "thumbv7em-none-eabihf", reasons=reasons
    )
    assert ids == ALL_ARMS
    assert reasons == [("unmodelled", "xtensa-esp32-elf")]
    [(message, subtype)] = warnings
    assert subtype == "preprocessor_target_unknown"
    assert message == (
        f"codelinks: {tmp_path / 'case.c'} is read as written, no `#if` arm left out, "
        f"as the libclang sphinx-codelinks loaded cannot read its build's target: the "
        f"target xtensa-esp32-elf that its compilation-database entry's `--target` "
        f"names is not one it models. Nothing is hidden: every marker is kept, only "
        f"less precisely; to accept that, add `codelinks.preprocessor_target_unknown` "
        f"to Sphinx's `suppress_warnings` (the `[preprocessor] target` setting does not "
        f"override what the build declares)"
    )


def test_an_unmodelled_setting_is_not_used(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A setting libclang does not model, for a file that takes it: the target is
    unknown, the file read as written, and the warning gives the remedy."""
    ids, warnings = _analyse(tmp_path, monkeypatch, XTENSA, None, "xtensa-esp32-elf")
    assert ids == {"IMPL_ALWAYS", "IMPL_XTENSA", "IMPL_NOT_XTENSA"}
    [(message, subtype)] = warnings
    assert subtype == "preprocessor_target_unknown"
    assert "the `[preprocessor] target` setting names is not one" in message
    assert message.endswith(
        "; or set the `[preprocessor] target` setting to a triple that libclang models"
    )


def test_a_source_read_through_its_includer_takes_its_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A compiled source with no entry, read through the entry that includes it, is
    read for the includer's target, which its compiler's name carries."""
    (tmp_path / "unity.c").write_text('#include "case.c"\n')
    src = tmp_path / "case.c"
    src.write_text(ARMS)
    db = tmp_path / "compile_commands.json"
    db.write_text(
        json.dumps(
            [
                {
                    "directory": str(tmp_path),
                    "file": "unity.c",
                    "arguments": ["arm-none-eabi-gcc", "-c", "unity.c"],
                }
            ]
        )
    )
    analyse = SourceAnalyse(
        SourceAnalyseConfig(
            src_files=[src],
            src_dir=tmp_path,
            comment_type=CommentType.cpp,
            get_oneline_needs=True,
            preprocessor=PreprocessorConfig(compile_commands=db, std="c11"),
        )
    )
    analyse.git_remote_url = None
    analyse.git_commit_rev = None
    monkeypatch.setattr(analyse_module, "logger", _RecordingLogger())
    analyse.run()
    assert {need.need["id"] for need in analyse.oneline_needs} == {
        "IMPL_ALWAYS",
        "IMPL_ARM",
    }


def test_the_triple_a_unit_was_parsed_for() -> None:
    """``triple_of`` reads ``clang_getTranslationUnitTargetInfo``."""
    cx = loader.load_clang_cindex()
    tu = cx.Index.create().parse(
        "t.c",
        args=["--target=arm-none-eabi", "-mcpu=cortex-m3"],
        unsaved_files=[("t.c", "")],
    )
    assert target.triple_of(tu) == "thumbv7m-none-unknown-eabi"


# --- the setting ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("thumbv7em-none-eabihf", "thumbv7em-none-eabihf"),
        ("  thumbv7em-none-eabihf ", "thumbv7em-none-eabihf"),
        ("", None),
        ("   ", None),
    ],
)
def test_the_target_setting_is_read_trimmed(value: str, expected: str | None) -> None:
    """``[preprocessor] target`` is trimmed, and ``""`` is unset."""
    config = convert_analyse_config({"preprocessor": {"target": value}})
    assert config.preprocessor is not None
    assert config.preprocessor.target == expected


def test_the_target_setting_defaults_to_unset() -> None:
    config = convert_analyse_config({"preprocessor": {}})
    assert config.preprocessor is not None
    assert config.preprocessor.target is None


def test_a_target_setting_that_is_not_a_string_is_rejected() -> None:
    with pytest.raises(TypeError, match=r"\[preprocessor\] target must be a string"):
        convert_analyse_config({"preprocessor": {"target": ["arm-none-eabi"]}})


# --- S2: a file whose target cannot be read is read as written -------------------------


@pytest.mark.parametrize(
    ("args", "compiler", "setting", "unknown"),
    [
        pytest.param([WD], None, None, False, id="host"),
        pytest.param([WD], "arm-none-eabi", None, False, id="name"),
        pytest.param([WD, "--target=xtensa-esp32-elf"], None, None, True, id="own"),
        pytest.param(
            [WD, "--target=xtensa-esp32-elf"],
            None,
            "thumbv7em-none-eabihf",
            True,
            id="own-with-setting",
        ),
        pytest.param([WD], None, "tricore-elf", True, id="setting"),
        pytest.param([WD], None, "thumbv7em-none-eabihf", False, id="modelled-setting"),
        pytest.param([WD], "my-arm", None, False, id="wrapper"),
        pytest.param([WD], "xtensa-esp32-elf", None, True, id="prefix"),
        pytest.param(
            [WD],
            "xtensa-esp32-elf",
            "thumbv7em-none-eabihf",
            True,
            id="prefix-with-setting",
        ),
    ],
)
def test_which_targets_are_unknown(
    args: list[str], compiler: str | None, setting: str | None, unknown: bool
) -> None:
    """ubCode S2: an entry's own triple libclang does not model (even with a setting
    it models: the setting does not override what the build declares), the setting's
    for a file that takes it, and an inserted triple refused without the CPU flags too
    leave the target unknown. Not a native build (the host, stated), a wrapper's name,
    a modelled declaration, nor flags refused with a target then read."""
    _, decision = _entry(args, compiler, setting)
    assert decision.unknown is unknown
    if compiler is None and len(args) == 1:
        # a file with no entry: the setting's alone
        _, decision = decide(
            ["-x", "c"], entry=False, setting=setting, modelled=_modelled
        )
        assert decision.unknown is unknown
    args, decision = _entry([*args, "-mcpu=x"], compiler, setting)
    attempts = target.again(args, decision)
    assert attempts[0][1].unknown is unknown
    if len(attempts) > 1:
        assert attempts[1][1].unknown
        assert attempts[1][1].not_read() == ("target_refused", decision.declared)


@pytest.mark.parametrize(
    ("args", "setting", "declarer", "remedy"),
    [
        pytest.param(
            [WD],
            "tricore-elf",
            "the `[preprocessor] target` setting names",
            "; or set the `[preprocessor] target` setting to a triple that libclang "
            "models",
            id="setting",
        ),
        pytest.param(
            [WD, "--target=xtensa-esp32-elf"],
            "thumbv7em-none-eabihf",
            "its compilation-database entry's `--target` names",
            " (the `[preprocessor] target` setting does not override what the build "
            "declares)",
            id="entry",
        ),
    ],
)
def test_the_warning_of_a_file_read_as_written_gives_the_remedy(
    args: list[str], setting: str, declarer: str, remedy: str
) -> None:
    """The warning for a file read as written gives the remedy: to suppress it
    (Sphinx's ``suppress_warnings``), or, when the setting declared the target, a
    setting naming a triple libclang models (the setting does not override the build's
    declaration); never the target parsed for."""
    _, decision = _entry(args, None, setting)
    not_read = decision.not_read()
    assert not_read is not None
    message = decision.message("src/a.c", "thumbv7em-none-unknown-eabihf", False)
    assert message == (
        f"codelinks: src/a.c is read as written, no `#if` arm left out, as the libclang "
        f"sphinx-codelinks loaded cannot read its build's target: the target "
        f"{not_read[1]} that {declarer} is not one it models. Nothing is hidden: every marker is kept, only less precisely; to accept that, add `codelinks.preprocessor_target_unknown` to Sphinx's `suppress_warnings`"
        f"{remedy}"
    )


def test_a_source_read_through_an_unknown_includer_is_read_as_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A compiled source with no entry, read through an entry whose own ``--target``
    libclang does not model, is read as written too: the arm only Xtensa takes and the
    one the machine running the analysis takes are both kept, and the warning names the
    includer's declaration."""
    (tmp_path / "unity.c").write_text('#include "case.c"\n')
    src = tmp_path / "case.c"
    src.write_text(XTENSA)
    db = tmp_path / "compile_commands.json"
    db.write_text(
        json.dumps(
            [
                {
                    "directory": str(tmp_path),
                    "file": "unity.c",
                    "arguments": [
                        "clang",
                        "--target=xtensa-esp32-elf",
                        "-c",
                        "unity.c",
                    ],
                }
            ]
        )
    )
    recorder = _RecordingLogger()
    monkeypatch.setattr(analyse_module, "logger", recorder)
    analyse = SourceAnalyse(
        SourceAnalyseConfig(
            src_files=[src],
            src_dir=tmp_path,
            comment_type=CommentType.cpp,
            get_oneline_needs=True,
            preprocessor=PreprocessorConfig(compile_commands=db, std="c11"),
        )
    )
    analyse.git_remote_url = None
    analyse.git_commit_rev = None
    analyse.run()
    assert {need.need["id"] for need in analyse.oneline_needs} == {
        "IMPL_ALWAYS",
        "IMPL_XTENSA",
        "IMPL_NOT_XTENSA",
    }
    [(message, subtype)] = recorder.warnings
    assert subtype == "preprocessor_target_unknown"
    assert "is read as written" in message
    assert "its includer's compilation-database entry's `--target`" in message


# --- S2 fix round 1: no file whose target is unknown is lost to a refused parse ----------

#: Markers on every arm an Xtensa or a 32-bit Arm build takes, none directly above a
#: conditional's line (ubCode's ``XTENSA_ARM``).
XTENSA_ARM = (
    "// @all, IMPL_ALL, impl\n"
    "int all;\n"
    "#ifdef __XTENSA__\n"
    "// @xtensa, IMPL_XT, impl\n"
    "int xt(void) { return 1; }\n"
    "#endif\n"
    "#if defined(__arm__)\n"
    "// @arm, IMPL_ARM, impl\n"
    "int arm(void) { return 2; }\n"
    "#endif\n"
)
XTENSA_ARM_IDS = {"IMPL_ALL", "IMPL_XT", "IMPL_ARM"}


@pytest.mark.parametrize(
    ("argv", "setting", "why", "declared", "says"),
    [
        pytest.param(
            ["clang", "--target=arm-none-eabi", "-mcmse", "-c", "case.c"],
            None,
            "target_refused",
            "arm-none-eabi",
            "refused the target arm-none-eabi that its compilation-database entry's "
            "`--target` names with the entry's flags (its `-m` flags: `-mcmse`)",
            id="own-refused",
        ),
        pytest.param(
            [
                "clang",
                "--target=arm-none-eabi",
                "-mcmse",
                "-mfpmath=vfp",
                "-c",
                "case.c",
            ],
            None,
            "target_refused",
            "arm-none-eabi",
            "names with the entry's flags (its `-m` flags: `-mcmse`, `-mfpmath=vfp`)",
            id="own-refused-everywhere",
        ),
        pytest.param(
            ["clang", "--target=xtensa-esp32-elf", "-mfpmath=vfp", "-c", "case.c"],
            None,
            "unmodelled",
            "xtensa-esp32-elf",
            "the target xtensa-esp32-elf that its compilation-database entry's "
            "`--target` names is not one it models",
            id="unmodelled-refused-everywhere",
        ),
        pytest.param(
            ["arm-none-eabi-gcc", "-mcmse", "-mfpmath=vfp", "-c", "case.c"],
            None,
            "target_refused",
            "arm-none-eabi",
            "refused the target arm-none-eabi that its compiler's name names with the "
            "entry's flags (its `-m` flags: `-mcmse`, `-mfpmath=vfp`)",
            id="name-refused-everywhere",
        ),
        pytest.param(
            ["gcc", "-mfpmath=vfp", "-c", "case.c"],
            "tricore-elf",
            "setting_unmodelled",
            "tricore-elf",
            "the target tricore-elf that the `[preprocessor] target` setting names is "
            "not one it models",
            id="setting-refused-everywhere",
        ),
        # decision 3: a compiler's name's GCC triple of an architecture libclang does
        # not model leaves the target unknown, so its refused parse does not drop the
        # file either, a modelled setting not inserted
        pytest.param(
            ["tricore-elf-gcc", "-mfpmath=vfp", "-c", "case.c"],
            None,
            "prefix_unmodelled",
            "tricore-elf",
            "its compiler's name carries the target tricore-elf, whose architecture "
            "tricore it does not model",
            id="prefix-refused-everywhere",
        ),
        pytest.param(
            ["xtensa-esp32-elf-gcc", "-mcmse", "-c", "case.c"],
            "thumbv7em-none-eabihf",
            "prefix_unmodelled",
            "xtensa-esp32-elf",
            "its compiler's name carries the target xtensa-esp32-elf, whose architecture "
            "xtensa it does not model",
            id="prefix-with-setting",
        ),
    ],
)
def test_no_unknown_target_file_is_dropped_for_a_refused_parse(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    argv: list[str],
    setting: str | None,
    why: str,
    declared: str,
    says: str,
) -> None:
    """ubCode S2 fix round 1, MUST 2: an entry's own target clang refuses with its
    flags, without a CPU flag to leave out (``--target=arm-none-eabi -mcmse``), is
    unknown (``target_refused``, declared by the entry), as an inserted one is: the file
    is read as written. And a file whose target is unknown and whose every parse is
    refused, by a flag clang refuses on every machine that runs the tests
    (``-mfpmath=vfp``), is read as written without libclang, by the tree-sitter engine:
    every marker kept, the same warning."""
    reasons: list[tuple[str, str | None]] = []
    ids, warnings = _analyse(
        tmp_path, monkeypatch, XTENSA_ARM, argv, setting, reasons=reasons
    )
    assert ids == XTENSA_ARM_IDS, "the file is read, never dropped"
    assert reasons == [(why, declared)]
    [(message, subtype)] = warnings
    assert subtype == "preprocessor_target_unknown"
    assert "is read as written, no `#if` arm left out" in message
    assert says in message


#: The end of a ``preprocessor_parse_refused`` warning, after the flags it names.
REFUSED_CLOSING = (
    "libclang does not say which flag it refused). Nothing is hidden: every marker is "
    "kept, only less precisely. To read it for its target, remove or change the "
    "refused flag in {fix_in}; to accept it as written, add "
    "`codelinks.preprocessor_parse_refused` to Sphinx's `suppress_warnings`"
)

#: What a ``preprocessor_parse_refused`` warning says after ``the libclang
#: sphinx-codelinks loaded refused`` for a flag refused for the host, with
#: ``{flags}`` (whose flags, and which) before :data:`REFUSED_CLOSING`.
REFUSED_FOR_THE_HOST = (
    "every parse of it for the machine sphinx-codelinks runs on (its build names no "
    "target) with the flags of {flags}"
)

#: The tail of a ``preprocessor_parse_refused`` warning about a command libclang
#: refused, for the compilation database.
REFUSED_COMMAND_CLOSING = (
    "Nothing is hidden: every marker is kept, only less precisely. To read it, remove "
    "or change what libclang does not take in {fix_in}; to accept it as written, add "
    "`codelinks.preprocessor_parse_refused` to Sphinx's `suppress_warnings`"
)


@pytest.mark.parametrize(
    ("argv", "name", "std", "says"),
    [
        # CXError_Failure: a flag the host does not take
        pytest.param(
            ["gcc", "-mfpmath=vfp", "-c", "case.c"],
            "case.c",
            "c11",
            REFUSED_FOR_THE_HOST.format(
                flags="its compilation-database entry (its `-m` flags: `-mfpmath=vfp`) ("
            )
            + REFUSED_CLOSING.format(fix_in="the compilation database"),
            id="native",
        ),
        pytest.param(
            ["gcc", "-mcpu=cortex-r52plus", "-mfpmath=vfp", "-c", "case.c"],
            "case.c",
            "c11",
            REFUSED_FOR_THE_HOST.format(
                flags="its compilation-database entry (its `-m` flags: `-mfpmath=vfp`), "
                "and without `-mcpu=cortex-r52plus` ("
            )
            + REFUSED_CLOSING.format(fix_in="the compilation database"),
            id="native-cpu-left-out",
        ),
        # a wrapper's name declares no target: the host's, a target libclang reads
        pytest.param(
            ["my-arm-gcc", "-mfpmath=vfp", "-c", "case.c"],
            "case.c",
            "c11",
            REFUSED_FOR_THE_HOST.format(
                flags="its compilation-database entry (its `-m` flags: `-mfpmath=vfp`) ("
            )
            + REFUSED_CLOSING.format(fix_in="the compilation database"),
            id="wrapper",
        ),
        # CXError_ASTReadError: a second input file, whatever the target
        pytest.param(
            ["clang", "-O2", "other.c", "-c", "case.c"],
            "case.c",
            "c11",
            "the arguments of its compilation-database entry, which hold a flag or an "
            "input file it does not take (libclang does not say which; input files "
            "besides this one: `other.c`): `-O2`, `other.c`. "
            + REFUSED_COMMAND_CLOSING.format(fix_in="the compilation database"),
            id="second-input",
        ),
        # CXError_ASTReadError: a `-std` clang does not know (a newer GCC's)
        pytest.param(
            ["gcc", "-std=gnu2y", "-c", "case.c"],
            "case.c",
            "c11",
            "the arguments of its compilation-database entry, which hold a flag or an "
            "input file it does not take (libclang does not say which): `-std=gnu2y`. "
            + REFUSED_COMMAND_CLOSING.format(fix_in="the compilation database"),
            id="unknown-std",
        ),
        # more than twelve arguments: the first twelve, the rest counted; the
        # resource directory the engine adds is not the entry's
        pytest.param(
            [
                "gcc",
                "-std=gnu2y",
                *(f"-DA{n}" for n in range(1, 14)),
                "-c",
                "case.c",
            ],
            "case.c",
            "c11",
            "the arguments of its compilation-database entry, which hold a flag or an "
            "input file it does not take (libclang does not say which): `-std=gnu2y`, "
            "`-DA1`, `-DA2`, `-DA3`, `-DA4`, `-DA5`, `-DA6`, `-DA7`, `-DA8`, `-DA9`, "
            "`-DA10`, `-DA11`, and 2 more. "
            + REFUSED_COMMAND_CLOSING.format(fix_in="the compilation database"),
            id="bounded",
        ),
        # a header with no entry: the `[preprocessor]` table's arguments, a `std`
        # clang does not know, whatever the target
        pytest.param(
            None,
            "case.h",
            "c99x",
            "the arguments of the `[preprocessor]` table, which hold a flag or an input "
            "file it does not take (libclang does not say which): `-x`, `c`, "
            "`-std=c99x`. "
            + REFUSED_COMMAND_CLOSING.format(fix_in="the `[preprocessor]` table"),
            id="header-std",
        ),
    ],
)
def test_a_known_target_file_whose_every_parse_is_refused_is_read_as_written(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    argv: list[str] | None,
    name: str,
    std: str,
    says: str,
) -> None:
    """useblocks/ubcode#4862: a file whose target is known (a native compiler's or a
    wrapper's, the host, stated; a header's, the ``[preprocessor]`` table's) and whose
    every parse is refused, on every machine that runs the tests, is no longer
    skipped: no parse decides an arm, so it is read as written without libclang, by
    the tree-sitter engine, every marker kept, with one ``preprocessor_parse_refused``
    warning (no ``preprocessor_target_unknown``), worded by what libclang reported
    (ubCode's ``a_refused_parse_is_worded_by_what_libclang_reported``). A flag the
    target does not take (``CXError_Failure``: ``-mfpmath=vfp``, with or without its
    CPU) names the target, whose flags they are, their ``-m`` flags and the CPU left
    out; a command libclang does not run at all (``CXError_ASTReadError``: a second
    input file, a ``-std`` it does not know) names whose arguments they are, lists them
    (at most twelve, the engine's own left out) and the other input files, and no
    target. Each text exactly."""
    (tmp_path / "other.c").write_text("int other;\n")
    reasons: list[tuple[str, str | None]] = []
    ids, warnings = _analyse(
        tmp_path, monkeypatch, XTENSA_ARM, argv, name=name, reasons=reasons, std=std
    )
    assert ids == XTENSA_ARM_IDS, "the file is read, never dropped"
    assert reasons == [], "no preprocessor_target_unknown warning"
    src = tmp_path / name
    assert warnings == [
        (
            f"codelinks: {src} is read as written, no `#if` arm left out, without "
            f"libclang: the libclang sphinx-codelinks loaded refused {says}",
            "preprocessor_parse_refused",
        )
    ]


#: A unity file including one source at the top, one in an arm only Xtensa takes and
#: one in an arm only 32-bit Arm takes.
UNITY_XTENSA_ARM = (
    '#include "top.c"\n'
    "#ifdef __XTENSA__\n"
    '#include "src.c"\n'
    "#endif\n"
    "#if defined(__arm__)\n"
    '#include "arm.c"\n'
    "#endif\n"
)


@pytest.mark.parametrize(
    ("argv", "setting", "why"),
    [
        pytest.param(
            ["clang", "--target=xtensa-esp32-elf"], None, "unmodelled", id="own"
        ),
        pytest.param(
            ["clang", "--target=xtensa-esp32-elf", "-mfpmath=vfp"],
            None,
            "unmodelled",
            id="own-refused-everywhere",
        ),
        pytest.param(["gcc"], "tricore-elf", "setting_unmodelled", id="setting"),
        pytest.param(
            ["arm-none-eabi-gcc", "-mcmse"], None, "target_refused", id="refused"
        ),
        # decision 3
        pytest.param(
            ["xtensa-esp32-elf-gcc", "-mlongcalls"],
            "thumbv7em-none-eabihf",
            "prefix_unmodelled",
            id="prefix",
        ),
        pytest.param(
            ["my-linux-gcc"], None, "prefix_unmodelled", id="wrapper-of-a-system"
        ),
    ],
)
def test_an_unknown_includer_confirms_by_its_include_lines(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    argv: list[str],
    setting: str | None,
    why: str,
) -> None:
    """ubCode S2 fix round 1, MUST 1: a source a unity entry whose target is unknown
    includes is confirmed by the entry's ``#include`` lines, not by its parse, which
    decides no arm: one included in an arm only Xtensa takes, one in an arm only 32-bit
    Arm takes and one at the top are each read as written through it, every marker
    kept, on every machine, never skipped as ``not_in_compile_database``. Whether the
    target is unknown as declared (an entry's own Xtensa, alone or with a flag every
    machine refuses, a setting libclang does not model) or after its parse was refused
    (``arm-none-eabi`` with ``-mcmse``)."""
    (tmp_path / "unity.c").write_text(UNITY_XTENSA_ARM)
    files = [tmp_path / name for name in ("src.c", "arm.c", "top.c")]
    for file in files:
        file.write_text(XTENSA_ARM.replace("IMPL_", f"IMPL_{file.stem.upper()}_"))
    db = tmp_path / "compile_commands.json"
    db.write_text(
        json.dumps(
            [
                {
                    "directory": str(tmp_path),
                    "file": "unity.c",
                    "arguments": [*argv, "-c", "unity.c"],
                }
            ]
        )
    )
    recorder = _RecordingLogger()
    monkeypatch.setattr(analyse_module, "logger", recorder)
    reasons: list[tuple[str, str | None]] = []
    warn = SourceAnalyse._warn_target

    def recording(
        self: SourceAnalyse,
        path: Path,
        decision: Decision,
        read_for: str,
        *,
        includer: bool,
    ) -> None:
        not_read = decision.not_read()
        if not_read is not None:
            reasons.append((not_read[0], path.name))
        warn(self, path, decision, read_for, includer=includer)

    monkeypatch.setattr(SourceAnalyse, "_warn_target", recording)
    analyse = SourceAnalyse(
        SourceAnalyseConfig(
            src_files=files,
            src_dir=tmp_path,
            comment_type=CommentType.cpp,
            get_oneline_needs=True,
            preprocessor=PreprocessorConfig(
                compile_commands=db, std="c11", target=setting
            ),
        )
    )
    analyse.git_remote_url = None
    analyse.git_commit_rev = None
    analyse.run()
    assert {need.need["id"] for need in analyse.oneline_needs} == {
        f"IMPL_{file.stem.upper()}_{marker}"
        for file in files
        for marker in ("ALL", "XT", "ARM")
    }
    assert sorted(reasons) == sorted((why, file.name) for file in files)
    assert len(recorder.warnings) == len(files)
    for message, subtype in recorder.warnings:
        assert subtype == "preprocessor_target_unknown"
        assert "is read as written, no `#if` arm left out" in message
        assert (
            "the `[preprocessor] target` setting names"
            if why == "setting_unmodelled"
            else "its includer's"
        ) in message


#: A source whose markers say which arm it was read for: Arm, not Arm, or both.
SRC_ARM = (
    "// @all, IMPL_SRC_ALL, impl\n"
    "int all;\n"
    "#if defined(__arm__)\n"
    "// @arm, IMPL_SRC_ARM, impl\n"
    "int arm(void) { return 1; }\n"
    "#else\n"
    "// @not arm, IMPL_SRC_NOT_ARM, impl\n"
    "int not_arm(void) { return 2; }\n"
    "#endif\n"
)

XTENSA_ENTRY = ["clang", "--target=xtensa-esp32-elf"]
ARM_ENTRY = ["arm-none-eabi-gcc", "-mcpu=cortex-m4"]
IN_IF_0 = '#if 0\n#include "src.c"\n#endif\n'
INCLUDED = '#include "src.c"\n'


@pytest.mark.parametrize(
    ("entries", "unknown_triple"),
    [
        pytest.param(
            [("a_unity.c", XTENSA_ENTRY, IN_IF_0), ("b_main.c", ARM_ENTRY, INCLUDED)],
            None,
            id="known-wins",
        ),
        pytest.param(
            [("a_main.c", ARM_ENTRY, INCLUDED), ("b_unity.c", XTENSA_ENTRY, IN_IF_0)],
            None,
            id="known-wins-first-by-path",
        ),
        pytest.param(
            [
                (
                    "a_main.c",
                    ARM_ENTRY,
                    '#ifdef __XTENSA__\n#include "src.c"\n#endif\n',
                ),
                ("b_unity.c", XTENSA_ENTRY, INCLUDED),
            ],
            "xtensa-esp32-elf",
            id="known-in-a-skipped-arm",
        ),
        pytest.param(
            [
                ("a_unity.c", XTENSA_ENTRY, IN_IF_0),
                ("b_unity.c", ["clang", "--target=tricore-elf"], INCLUDED),
            ],
            "xtensa-esp32-elf",
            id="unknown-alone",
        ),
    ],
)
def test_a_known_includer_that_confirms_wins_over_an_unknown_ones_text(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    entries: list[tuple[str, list[str], str]],
    unknown_triple: str | None,
) -> None:
    """ubCode S2 fix round 2: a candidate includer whose target is known and whose
    parse confirms the inclusion is taken before any candidate whose target is
    unknown, which confirms by its ``#include`` lines only when no known one confirms
    (path order within each). So ``src.c``, which an Xtensa unity includes in ``#if 0``
    and an Arm entry includes for real, is read for Arm through the Arm entry,
    whichever comes first by path: the markers of its Arm arm, not its ``#else``, and
    no warning. A known includer whose ``#include`` sits in an arm its parse skips
    still does not confirm, so the unknown one reads the source as written, every
    marker kept; with unknown includers alone, the first by path does (its triple is
    the one the warning names)."""
    for name, _, text in entries:
        (tmp_path / name).write_text(text)
    src = tmp_path / "src.c"
    src.write_text(SRC_ARM)
    db = tmp_path / "compile_commands.json"
    db.write_text(
        json.dumps(
            [
                {
                    "directory": str(tmp_path),
                    "file": name,
                    "arguments": [*argv, "-c", name],
                }
                for name, argv, _ in entries
            ]
        )
    )
    recorder = _RecordingLogger()
    monkeypatch.setattr(analyse_module, "logger", recorder)
    analyse = SourceAnalyse(
        SourceAnalyseConfig(
            src_files=[src],
            src_dir=tmp_path,
            comment_type=CommentType.cpp,
            get_oneline_needs=True,
            preprocessor=PreprocessorConfig(compile_commands=db, std="c11"),
        )
    )
    analyse.git_remote_url = None
    analyse.git_commit_rev = None
    analyse.run()
    ids = {need.need["id"] for need in analyse.oneline_needs}
    if unknown_triple is None:
        assert ids == {"IMPL_SRC_ALL", "IMPL_SRC_ARM"}
        assert recorder.warnings == []
        return
    assert ids == {"IMPL_SRC_ALL", "IMPL_SRC_ARM", "IMPL_SRC_NOT_ARM"}
    [(message, subtype)] = recorder.warnings
    assert subtype == "preprocessor_target_unknown"
    assert "is read as written" in message
    assert f"the target {unknown_triple} that its includer's" in message


def test_a_refused_setting_gives_the_remedy_for_the_entrys_flags() -> None:
    """ubCode S2 fix round 2: a setting refused with the entry's flags is said to be
    refused with them, listing its ``-m`` flags without claiming one was refused
    (libclang does not say which), and the remedy is a triple libclang accepts with the
    entry's flags."""
    args, decision = _entry([WD, "-mcmse"], None, "thumbv7em-none-eabihf")
    [(_, refused)] = target.again(args, decision)
    message = refused.message("src/a.c", "", False)
    assert message is not None
    assert (
        "it refused the target thumbv7em-none-eabihf that the `[preprocessor] target` "
        "setting names with the entry's flags (its `-m` flags: `-mcmse`)" in message
    )
    assert message.endswith(
        "; or set the `[preprocessor] target` setting to a triple that libclang accepts "
        "with the entry's flags"
    )


class _LocatingLogger(_RecordingLogger):
    """Records each warning's location too (``locations``)."""

    def __init__(self) -> None:
        super().__init__()
        self.locations: list[object] = []

    def warning(self, msg: str, *, subtype: str = "", **kwargs: object) -> None:
        super().warning(msg, subtype=subtype)
        self.locations.append(kwargs.get("location"))


#: An entry whose every parse clang refuses, on every machine that runs the tests, for
#: a flag the target does not take (``CXError_Failure``).
REFUSED_ENTRY = ["gcc", "-mfpmath=vfp"]

#: An entry whose every parse clang refuses, on every machine that runs the tests, for
#: a command it does not run at all (``CXError_ASTReadError``).
COMMAND_REFUSED_ENTRY = ["gcc", "-std=gnu2y"]


@pytest.mark.parametrize(
    ("entries", "read_as_written_through"),
    [
        pytest.param(
            [
                (
                    "unity.c",
                    REFUSED_ENTRY,
                    '#ifdef __XTENSA__\n#include "src.c"\n#endif\n',
                )
            ],
            "unity.c",
            id="refused-alone",
        ),
        pytest.param(
            [("a_unity.c", REFUSED_ENTRY, INCLUDED), ("b_main.c", ARM_ENTRY, INCLUDED)],
            None,
            id="known-wins",
        ),
        pytest.param(
            [("a_main.c", ARM_ENTRY, INCLUDED), ("b_unity.c", REFUSED_ENTRY, INCLUDED)],
            None,
            id="known-wins-first-by-path",
        ),
        pytest.param(
            [
                (
                    "a_main.c",
                    ARM_ENTRY,
                    '#ifdef __XTENSA__\n#include "src.c"\n#endif\n',
                ),
                ("b_unity.c", REFUSED_ENTRY, INCLUDED),
            ],
            "b_unity.c",
            id="known-in-a-skipped-arm",
        ),
        pytest.param(
            [
                (
                    "unity.c",
                    COMMAND_REFUSED_ENTRY,
                    '#ifdef __XTENSA__\n#include "src.c"\n#endif\n',
                )
            ],
            "unity.c",
            id="command-refused-alone",
        ),
    ],
)
def test_a_refused_includer_confirms_by_its_include_lines(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    entries: list[tuple[str, list[str], str]],
    read_as_written_through: str | None,
) -> None:
    """useblocks/ubcode#4862: an includer whose target is known and whose every parse
    is refused (``-mfpmath=vfp``) no longer includes nothing: no parse decides which of
    its ``#include`` lines it compiles, so its ``#include`` lines confirm, as an
    unknown includer's do, and ``src.c`` is read as written through it, every marker
    kept, with one ``preprocessor_parse_refused`` warning at its first line naming its
    includer, worded by what libclang reported (a flag the target does not take, or a
    command it does not run: ``-std=gnu2y``), not skipped as
    ``not_in_compile_database``. An includer
    whose target is known and whose parse confirms (``arm-none-eabi-gcc``) still wins,
    whichever comes first by path: ``src.c`` is read for Arm, no warning; one whose
    ``#include`` sits in an arm its parse skips does not confirm, so the refused one
    does."""
    for name, _, text in entries:
        (tmp_path / name).write_text(text)
    src = tmp_path / "src.c"
    src.write_text(SRC_ARM)
    db = tmp_path / "compile_commands.json"
    db.write_text(
        json.dumps(
            [
                {
                    "directory": str(tmp_path),
                    "file": name,
                    "arguments": [*argv, "-c", name],
                }
                for name, argv, _ in entries
            ]
        )
    )
    recorder = _LocatingLogger()
    monkeypatch.setattr(analyse_module, "logger", recorder)
    analyse = SourceAnalyse(
        SourceAnalyseConfig(
            src_files=[src],
            src_dir=tmp_path,
            comment_type=CommentType.cpp,
            get_oneline_needs=True,
            preprocessor=PreprocessorConfig(compile_commands=db, std="c11"),
        )
    )
    analyse.git_remote_url = None
    analyse.git_commit_rev = None
    analyse.run()
    ids = {need.need["id"] for need in analyse.oneline_needs}
    if read_as_written_through is None:
        assert ids == {"IMPL_SRC_ALL", "IMPL_SRC_ARM"}
        assert recorder.warnings == []
        return
    assert ids == {"IMPL_SRC_ALL", "IMPL_SRC_ARM", "IMPL_SRC_NOT_ARM"}
    includer = (tmp_path / read_as_written_through).resolve()
    whose = f"the compilation-database entry of its includer {includer}"
    if any(argv is COMMAND_REFUSED_ENTRY for _, argv, _ in entries):
        says = (
            f"the arguments of {whose}, which hold a flag or an input file it does not "
            f"take (libclang does not say which): `-std=gnu2y`. "
            f"{REFUSED_COMMAND_CLOSING.format(fix_in='the compilation database')}"
        )
    else:
        says = (
            f"every parse of it for the machine sphinx-codelinks runs on (its build "
            f"names no target) with the flags of {whose} (its `-m` flags: "
            f"`-mfpmath=vfp`) "
            f"({REFUSED_CLOSING.format(fix_in='the compilation database')}"
        )
    assert recorder.warnings == [
        (
            f"codelinks: {src} is read as written, no `#if` arm left out, without "
            f"libclang: the libclang sphinx-codelinks loaded refused {says}",
            "preprocessor_parse_refused",
        )
    ]
    assert recorder.locations == [f"{src}:1"]
    assert analyse.dependencies >= {db, tmp_path / read_as_written_through}
