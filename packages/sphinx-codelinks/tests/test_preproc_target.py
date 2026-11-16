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
from sphinx_codelinks.analyse.preproc import loader, target
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
    is inserted, the setting applies, and the prefix is reported."""
    args, decision = _entry([WD], prefix)
    assert args == [WD]
    reported = Unmodelled(
        prefix, TargetSource.compiler_name, why=NotRead.prefix_unmodelled
    )
    assert decision == Decision(TargetSource.host, unmodelled=reported)
    args, decision = _entry([WD], prefix, "riscv32-unknown-elf")
    assert args == [WD, "--target=riscv32-unknown-elf"]
    assert decision.source is TargetSource.setting
    assert decision.unmodelled == reported


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
            [WD, "--target=riscv32-unknown-elf"],
            TargetSource.setting,
            Unmodelled("xtensa-esp32-elf", TargetSource.entry, "--target"),
            id="own-then-setting",
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
    """A declared triple libclang does not model is no declaration: an entry's own is
    removed (libclang would refuse the parse) and its compiler's name is not read, the
    setting applies when it is modelled, else the host; the first one is reported, as
    the entry wrote it."""
    args, decision = _entry(args, compiler, setting)
    assert args == expected
    assert decision.source is source
    assert decision.unmodelled == unmodelled
    message = decision.message("src/a.c", "x86_64-pc-linux-gnu", includer=False)
    assert message is not None
    assert message.startswith("codelinks: src/a.c is read for x86_64-pc-linux-gnu (")
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
) -> tuple[Callable[[list[str]], str], list[list[str]]]:
    """A parser that refuses the arguments ``refuses`` says, and the calls it got."""
    calls: list[list[str]] = []

    def parse(args: list[str]) -> str:
        calls.append(args)
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


def test_a_target_refused_without_the_cpu_too_is_read_for_the_host() -> None:
    """Step 3: refused without the CPU flags too, the file is read for the host,
    without the target and without those flags; the decision names the triple
    refused, and its source stays where the triple came from."""
    args, decision = _entry(ENTRY, "powerpc-eabi")
    parse, calls = _parser(lambda attempt: "--target=powerpc-eabi" in attempt)
    read, used, reported = parse_or_again(args, decision, parse, _Refused)
    assert read == "read"
    assert used == [WD, "-resource-dir", "/r"]
    assert len(calls) == 3
    assert reported == Decision(
        TargetSource.compiler_name,
        "powerpc-eabi",
        unmodelled=Unmodelled(
            "powerpc-eabi", TargetSource.compiler_name, why=NotRead.target_refused
        ),
        left_out=("-mcpu=e200z4", "-mabi=spe"),
    )
    assert reported.message("a.c", "x86_64-unknown-linux-gnu", True) == (
        "codelinks: a.c is read for x86_64-unknown-linux-gnu (the machine "
        "sphinx-codelinks runs on, without `-mcpu=e200z4`, `-mabi=spe`): the libclang "
        "sphinx-codelinks loaded refused the target powerpc-eabi that its includer's "
        "compiler's name names with the entry's flags, and without `-mcpu=e200z4`, "
        "`-mabi=spe`, so the `#if` arms of the file on the target are not its build's"
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
    assert "(the machine sphinx-codelinks runs on):" in message
    assert "names with the entry's flags, so the" in message


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


@pytest.mark.parametrize(
    "args",
    [
        pytest.param([WD, "--target=arm-none-eabi", "-DX"], id="own-target"),
        pytest.param([WD, "-DX"], id="host"),
    ],
)
def test_nothing_to_leave_out_is_not_made_again(args: list[str]) -> None:
    """A parse whose target was not inserted (the entry's own, or the host) and that
    carries none of the CPU and ABI flags is not made again: its refusal is the file's,
    as before targets were read; the file is skipped with a log line and no finding."""
    args, decision = _entry(args)
    parse, calls = _parser(lambda _attempt: True)
    with pytest.raises(_Refused):
        parse_or_again(args, decision, parse, _Refused)
    assert len(calls) == 1


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
    assert (
        "(the machine sphinx-codelinks runs on, without `-march=rv32imac_zicsr`, "
        "`-mabi=ilp32`)" in message
    )
    assert "carries the target riscv-none-elf" in message
    assert (
        "; and it refused `-march=rv32imac_zicsr`, `-mabi=ilp32` for the target read "
        "instead, which is read without them" in message
    )
    # an entry's own xtensa, then the setting, inserted and refused
    args, decision = _entry(
        [WD, "--target=xtensa-esp32-elf", "-mcpu=e200z4"], None, "powerpc-eabi"
    )
    assert decision.not_read() == ("unmodelled", "xtensa-esp32-elf")
    attempts = target.again(args, decision)
    assert attempts[0][1].not_read() == ("unmodelled", "xtensa-esp32-elf")
    assert attempts[1][1].not_read() == ("target_refused", "powerpc-eabi")
    # a setting libclang does not model is said to be the setting's
    _, decision = _entry([WD], None, "tricore-elf")
    assert decision.not_read() == ("setting_unmodelled", "tricore-elf")


def test_a_refusal_at_every_step_is_the_files() -> None:
    """Refused at every step, the last refusal is raised (the caller skips the file
    with its warning, as before)."""
    args, decision = _entry(ENTRY, "powerpc-eabi")
    parse, calls = _parser(lambda _attempt: True)
    with pytest.raises(_Refused):
        parse_or_again(args, decision, parse, _Refused)
    assert len(calls) == 3


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
                compile_commands=db, std="c11", target=setting
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


#: The arms of :data:`ARMS` a machine the suite runs on reads for itself.
HOST_ARMS = {"IMPL_X86", "IMPL_A64"}


def test_libclang_refusing_the_target_without_the_cpu_reads_the_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Step 3 against the loaded libclang, on every machine: ``-mcmse`` makes clang
    refuse ``arm-none-eabi`` with or without the CPU (it needs an ARMv8-M one), while
    an x86-64, an Arm64 and a Windows host each accept it for themselves (ubCode's
    example), so the file is read for the host with its other flags. The reason is
    asserted, never the host triple's spelling (``arm64-apple-macosx14.0.0`` on a
    macOS Arm64 machine)."""
    argv = ["arm-none-eabi-gcc", "-mcpu=cortex-m4", "-mcmse", "-c", "case.c"]
    reasons: list[tuple[str, str | None]] = []
    ids, warnings = _analyse(tmp_path, monkeypatch, ARMS, argv, reasons=reasons)
    assert "IMPL_ALWAYS" in ids
    assert len(ids & HOST_ARMS) == 1
    assert ids <= {"IMPL_ALWAYS", *HOST_ARMS}
    assert reasons == [("target_refused", "arm-none-eabi")]
    [(message, subtype)] = warnings
    assert subtype == "preprocessor_target_unknown"
    assert (
        "(the machine sphinx-codelinks runs on, without `-mcpu=cortex-m4`)" in message
    )
    assert "refused the target arm-none-eabi that its compiler's name names" in message


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
    assert "without " + ", ".join(f"`{flag}`" for flag in flags) in message
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
    or an environment (ESP-IDF's ``xtensa-esp32-elf-gcc``) is reported, the file
    read for the host; a wrapper's name stays silent. Every file keeps its markers."""
    ids, warnings = _analyse(tmp_path, monkeypatch, XTENSA, [compiler, "-c", "case.c"])
    assert ids == {"IMPL_ALWAYS", "IMPL_NOT_XTENSA"}
    if reported is None:
        assert warnings == []
        return
    [(message, subtype)] = warnings
    assert subtype == "preprocessor_target_unknown"
    arch = reported.split("-", 1)[0]
    read_for, _, rest = message.partition(" (the machine sphinx-codelinks runs on): ")
    assert read_for.startswith(f"codelinks: {tmp_path / 'case.c'} is read for ")
    assert rest == (
        f"its compiler's name carries the target "
        f"{reported}, whose architecture {arch} the libclang sphinx-codelinks loaded "
        f"does not model, so the `#if` arms of the file on the target are not its "
        f"build's"
    )


def test_an_unmodelled_entry_target_is_left_out_and_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An entry's own ``--target`` libclang does not model: passed on, the parse fails
    and the file is dropped. It is left out, the file read for the setting, and the
    warning names the target and the setting."""
    argv = ["clang", "--target=xtensa-esp32-elf", "-c", "case.c"]
    ids, warnings = _analyse(tmp_path, monkeypatch, ARMS, argv, "thumbv7em-none-eabihf")
    assert ids == {"IMPL_ALWAYS", "IMPL_ARM"}
    [(message, subtype)] = warnings
    assert subtype == "preprocessor_target_unknown"
    assert (
        "is read for thumbv7em-none-unknown-eabihf (the `[preprocessor] target` "
        "setting)" in message
    )
    assert "its compilation-database entry's `--target`" in message


def test_an_unmodelled_setting_is_not_used(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A setting libclang does not model reads the file for the host, reported."""
    ids, warnings = _analyse(tmp_path, monkeypatch, XTENSA, None, "xtensa-esp32-elf")
    assert ids == {"IMPL_ALWAYS", "IMPL_NOT_XTENSA"}
    [(message, subtype)] = warnings
    assert subtype == "preprocessor_target_unknown"
    assert "the `[preprocessor] target` setting names is not one" in message


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
