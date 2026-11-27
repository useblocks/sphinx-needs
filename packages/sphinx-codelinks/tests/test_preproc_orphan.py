"""A header no compilation-database entry includes leaves out only the arms its
configuration decides (useblocks/ubcode#4866, slice 2).

Such a header (``no_includer``) is read with the ``[preprocessor]`` table, a
configuration no entry compiles it with: an arm the build compiles, on a ``-D`` of the
entries' own or for their target, would be hidden. So of the ranges its parse skipped,
only an arm whose whole conditional chain the table decides stays left out
(``analyse/preproc/decided.py``), and every other arm is read as written, with one
information-level note per compilation database naming the headers.

The twins of ubCode's tests in ``rust/ubc_codelinks/tests/preproc_test.rs``; the rule's
pieces are ``test_preproc_decided.py``'s.
"""

from __future__ import annotations

import json
import os
import pickle
from collections.abc import Callable
from pathlib import Path

import pytest
from sphinx.testing.util import SphinxTestApp
from sphinx.util.console import strip_colors

from sphinx_needs_testkit import build_warnings

pytest.importorskip("clang.cindex")

from sphinx_codelinks.analyse import analyse as analyse_module
from sphinx_codelinks.analyse.analyse import SourceAnalyse
from sphinx_codelinks.config import PreprocessorConfig, SourceAnalyseConfig

from .test_need_id_refs import _SHOWS_WARNING_TYPES, _build, _json, _project

#: the note's code, which its message names last
CODE = "[codelinks.preprocessor_no_includer]"


class _Recorder:
    """Records the analysis module's information lines (with their location) and
    warnings (the real logger is slotted, so the module-level one is swapped)."""

    def __init__(self) -> None:
        self.infos: list[tuple[str, str | None]] = []
        self.warnings: list[tuple[str, str]] = []

    def info(self, msg: str, *, location: str | None = None) -> None:
        self.infos.append((msg, location))

    def warning(
        self, msg: str, *, subtype: str = "", location: str | None = None
    ) -> None:
        self.warnings.append((msg, subtype))

    def debug(self, *_a: object, **_k: object) -> None:
        pass

    @property
    def notes(self) -> list[tuple[str, str | None]]:
        """The ``preprocessor_no_includer`` notes."""
        return [(msg, at) for msg, at in self.infos if msg.endswith(CODE)]


@pytest.fixture
def recorder(monkeypatch: pytest.MonkeyPatch) -> _Recorder:
    recorder = _Recorder()
    monkeypatch.setattr(analyse_module, "logger", recorder)
    return recorder


#: the recon's header: a ``CONFIG_X`` arm the entries' ``-DCONFIG_X=1`` compiles and a
#: ``__arm__`` arm their ``arm-none-eabi`` target compiles, neither of which a header
#: no entry includes can know
ORPHAN_HEADER = (
    "#pragma once\n// @Base, O_BASE, impl\n"
    "#ifdef CONFIG_X\n// @X, O_X, impl\n#endif\n"
    "#if defined(__arm__)\n// @Arm, O_ARM, impl\n#endif\n"
)


def _orphan_project(root: Path, header: str) -> Path:
    """A project whose one entry (``arm-none-eabi-gcc -DCONFIG_X=1``, ``main.c``) does
    not include ``orphan.h``, which holds ``header``; returns the database."""
    (root / "orphan.h").write_text(header, encoding="utf-8")
    (root / "main.c").write_text("int main(void) { return 0; }\n", encoding="utf-8")
    db = root / "compile_commands.json"
    db.write_text(
        json.dumps(
            [
                {
                    "directory": str(root),
                    "file": "main.c",
                    "arguments": [
                        "arm-none-eabi-gcc",
                        "-DCONFIG_X=1",
                        "-c",
                        "main.c",
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )
    return db


def _ids(
    root: Path,
    db: Path | None,
    defines: list[str] | None = None,
    target: str | None = None,
) -> list[str]:
    """The need ids of ``orphan.h`` read with ``db`` and the ``[preprocessor]`` table's
    ``defines`` and ``target``, in order."""
    analyse = SourceAnalyse(
        SourceAnalyseConfig(
            src_files=[root / "orphan.h"],
            src_dir=root,
            get_need_id_refs=False,
            get_oneline_needs=True,
            get_multiline_needs=False,
            preprocessor=PreprocessorConfig(
                compile_commands=db, defines=defines or [], std="c11", target=target
            ),
        )
    )
    analyse.git_remote_url = None
    analyse.git_commit_rev = None
    analyse.run(log_summary=False)
    return [need.need["id"] for need in analyse.oneline_needs]


def test_an_orphan_header_keeps_the_arms_the_configuration_does_not_decide(
    tmp_path: Path, recorder: _Recorder
) -> None:
    """The issue's case: a header no entry includes is read with the ``[preprocessor]``
    table, which states neither ``CONFIG_X`` nor a target. Its ``#ifdef CONFIG_X`` and
    ``#if defined(__arm__)`` arms are on conditions the table does not decide, so both
    are read (they were left out: the build compiles both), with one note at the
    database naming the header and counting the two arms. An edit that defines the
    macro in the header changes nothing: a header's own ``#define`` decides nothing."""
    db = _orphan_project(tmp_path, ORPHAN_HEADER)
    assert _ids(tmp_path, db) == ["O_BASE", "O_X", "O_ARM"]
    ((message, location),) = recorder.notes
    assert location == f"{db}:1"
    assert message == (
        "codelinks: 1 header that no entry of this compilation database includes is "
        "read with the `[preprocessor]` table, and 2 `#if` arms on a condition the "
        "table does not decide are read as written rather than left out: `orphan.h`. "
        "To leave out what the build leaves out, state the macros in `[preprocessor] "
        "defines` and the target in `target`, or include it from an entry's file. "
        f"{CODE}"
    )
    assert recorder.warnings == []

    recorder.infos.clear()
    (tmp_path / "orphan.h").write_text(
        f"#define CONFIG_X 1\n{ORPHAN_HEADER}", encoding="utf-8"
    )
    assert _ids(tmp_path, db) == ["O_BASE", "O_X", "O_ARM"]
    assert len(recorder.notes) == 1


def test_a_stated_define_decides_an_orphan_arm_and_an_unstated_one_does_not(
    tmp_path: Path, recorder: _Recorder
) -> None:
    """What the table states decides: ``CONFIG_X=0`` leaves out the ``#if CONFIG_X``
    arm (the build's ``-DCONFIG_X=1`` is no includer's), and a stated ``CONFIG_Z``
    decides ``!defined(CONFIG_Z)``, while ``CONFIG_Y``, which nothing states, leaves both
    of its arms read. Every condition stated: no arm is read for an undecided one, and
    there is no note."""
    header = (
        "#pragma once\n"
        "#if CONFIG_X\n// @X on, O_X_ON, impl\n#else\n// @X off, O_X_OFF, impl\n#endif\n"
        "#if !defined(CONFIG_Z)\n// @Z off, O_Z_OFF, impl\n#endif\n"
        "#ifdef CONFIG_Y\n// @Y on, O_Y_ON, impl\n#else\n// @Y off, O_Y_OFF, impl\n"
        "#endif\n"
    )
    db = _orphan_project(tmp_path, header)
    assert _ids(tmp_path, db, ["CONFIG_X=0", "CONFIG_Z"]) == [
        "O_X_OFF",
        "O_Y_ON",
        "O_Y_OFF",
    ]
    assert len(recorder.notes) == 1

    recorder.infos.clear()
    assert _ids(tmp_path, db, ["CONFIG_X=0", "CONFIG_Z", "CONFIG_Y"]) == [
        "O_X_OFF",
        "O_Y_ON",
    ]
    assert recorder.notes == []


def test_a_stated_define_whose_value_is_unstated_is_undecided_in_an_orphan(
    tmp_path: Path, recorder: _Recorder
) -> None:
    """A stated macro decides its value only when its value is decided: ``A=B`` with
    ``B`` unstated leaves ``#if A`` read, while ``#ifndef A`` (its definedness alone) and
    ``C=D`` with ``D`` stated decide."""
    header = (
        "#pragma once\n"
        "#if A\n// @A, O_A, impl\n#endif\n"
        "#ifndef A\n// @Not A, O_NOT_A, impl\n#endif\n"
        "#if C\n// @C, O_C, impl\n#endif\n"
    )
    db = _orphan_project(tmp_path, header)
    assert _ids(tmp_path, db, ["A=B", "C=D", "D=0"]) == ["O_A"]
    assert len(recorder.notes) == 1


def test_a_stated_target_decides_its_identity_in_an_orphan_and_a_guessed_one_does_not(
    tmp_path: Path, recorder: _Recorder
) -> None:
    """The target's own macros decide only when the ``target`` setting states the
    target: with ``x86_64-unknown-linux-gnu``, ``__arm__`` (absent) and ``__x86_64__``
    (predefined) decide their arms, and ``__LP64__``'s definedness does; with no setting
    the target is a guess (the machine the analysis runs on), and every arm on them is
    read."""
    header = (
        "#pragma once\n"
        "#if defined(__arm__)\n// @Arm, O_ARM, impl\n#else\n"
        "// @Not arm, O_NOT_ARM, impl\n#endif\n"
        "#ifdef __x86_64__\n// @X86, O_X86, impl\n#else\n// @Not x86, O_NOT_X86, impl\n"
        "#endif\n"
        "#ifdef __LP64__\n// @Lp64, O_LP64, impl\n#else\n"
        "// @Not lp64, O_NOT_LP64, impl\n#endif\n"
    )
    db = _orphan_project(tmp_path, header)
    assert _ids(tmp_path, db, target="x86_64-unknown-linux-gnu") == [
        "O_NOT_ARM",
        "O_X86",
        "O_LP64",
    ]
    assert recorder.notes == []

    assert _ids(tmp_path, db) == [
        "O_ARM",
        "O_NOT_ARM",
        "O_X86",
        "O_NOT_X86",
        "O_LP64",
        "O_NOT_LP64",
    ]
    assert len(recorder.notes) == 1


def test_a_stated_target_decides_only_its_identity_in_an_orphan(
    tmp_path: Path, recorder: _Recorder
) -> None:
    """With the ``target`` setting stated, only the target's identity decides. A name a
    build defines (``__ZEPHYR__``) is not the target's, nor is the compiler's identity
    (``__GNUC__``: clang's is 4, and the build's compiler is not clang), nor clang's own
    spelling (``__LITTLE_ENDIAN__``, which GCC does not set on x86-64), nor a data-model
    VALUE (``__SIZEOF_LONG__``, which a flag can change): each of their skipped arms is
    read, and the note counts them (four)."""
    header = (
        "#pragma once\n"
        "#ifdef __ZEPHYR__\n// @Zephyr, O_ZEPHYR, impl\n#endif\n"
        "#if __GNUC__ >= 7\n// @Gnuc7, O_GNUC7, impl\n#endif\n"
        "#ifdef __LITTLE_ENDIAN__\n// @Le, O_LE, impl\n#else\n"
        "// @Not le, O_NOT_LE, impl\n#endif\n"
        "#if __SIZEOF_LONG__ == 8\n// @Long8, O_LONG8, impl\n#else\n"
        "// @Long4, O_LONG4, impl\n#endif\n"
    )
    db = _orphan_project(tmp_path, header)
    assert _ids(tmp_path, db, target="x86_64-unknown-linux-gnu") == [
        "O_ZEPHYR",
        "O_GNUC7",
        "O_LE",
        "O_NOT_LE",
        "O_LONG8",
        "O_LONG4",
    ]
    ((message, _),) = recorder.notes
    assert "4 `#if` arms" in message


def test_a_macro_the_orphan_defines_itself_decides_nothing(
    tmp_path: Path, recorder: _Recorder
) -> None:
    """A macro the header itself ``#define``\\ s (or ``#undef``\\ s) decides nothing,
    even one the table states: whether a condition reads it before or after the
    header's own definition is not read. A stated macro the header leaves alone
    decides."""
    header = (
        "#pragma once\n#define LOCAL 0\n"
        "#if LOCAL\n// @Local on, O_LOCAL_ON, impl\n#else\n"
        "// @Local off, O_LOCAL_OFF, impl\n#endif\n"
        "#if STATED\n// @Stated on, O_STATED_ON, impl\n#else\n"
        "// @Stated off, O_STATED_OFF, impl\n#endif\n"
        "#undef GONE\n#ifdef GONE\n// @Gone, O_GONE, impl\n#endif\n"
    )
    db = _orphan_project(tmp_path, header)
    assert _ids(tmp_path, db, ["STATED=1", "GONE"]) == [
        "O_LOCAL_ON",
        "O_LOCAL_OFF",
        "O_STATED_ON",
        "O_GONE",
    ]
    assert len(recorder.notes) == 1


def test_constants_and_has_include_decide_an_orphan_arm(
    tmp_path: Path, recorder: _Recorder
) -> None:
    """Constants decide: ``#if 0`` stays left out and ``#if 1``'s ``#else`` too; a
    ``__has_include`` of a header name decides (the stated ``includes`` say what is
    found). In one chain, an arm before the first undecided condition stays left out,
    and every arm from it on is read."""
    header = (
        "#pragma once\n"
        "#if 0\n// @Zero, O_ZERO, impl\n#endif\n"
        "#if 1\n// @One, O_ONE, impl\n#else\n// @Not one, O_NOT_ONE, impl\n#endif\n"
        "#if (2 + 3) * 4 > 30\n// @Arith, O_ARITH, impl\n#endif\n"
        "#if __has_include(<ubc_no_such_header.h>)\n// @Has, O_HAS, impl\n#else\n"
        "// @Has not, O_HAS_NOT, impl\n#endif\n"
        "#if 0\n// @Chain zero, O_C0, impl\n#elif defined(UNSTATED)\n"
        "// @Chain unstated, O_C1, impl\n#else\n// @Chain else, O_C2, impl\n#endif\n"
    )
    db = _orphan_project(tmp_path, header)
    assert _ids(tmp_path, db) == ["O_ONE", "O_HAS_NOT", "O_C1", "O_C2"]
    assert len(recorder.notes) == 1


def test_has_include_of_a_macro_is_undecided_in_an_orphan(
    tmp_path: Path, recorder: _Recorder
) -> None:
    """``__has_include`` of a macro decides only when the macro is stated; of a literal
    header name, always."""
    header = (
        "#pragma once\n"
        "#if __has_include(CFG_HDR)\n// @Macro, O_HI_MACRO, impl\n#endif\n"
        '#if __has_include("ubc_no_such_header.h")\n'
        "// @Literal, O_HI_LITERAL, impl\n#endif\n"
        "#if __has_include(<ubc_no_such_header.h>)\n"
        "// @Angled, O_HI_ANGLED, impl\n#endif\n"
    )
    db = _orphan_project(tmp_path, header)
    assert _ids(tmp_path, db) == ["O_HI_MACRO"]
    assert len(recorder.notes) == 1


def test_a_digraph_directive_is_scanned_in_an_orphan(
    tmp_path: Path, recorder: _Recorder
) -> None:
    """A directive spelled with the ``%:`` digraph is one: the ``#else`` of a digraph
    ``%:ifndef`` on an unstated macro is read, not taken for the ``#else`` of the
    enclosing, decided chain."""
    header = (
        "#pragma once\n#ifdef STATED\n%:ifndef UNSTATED_D\n// @A, O_DG_A, impl\n"
        "#else\n// @B, O_DG_B, impl\n#endif\n#endif\n"
    )
    db = _orphan_project(tmp_path, header)
    assert _ids(tmp_path, db, ["STATED"]) == ["O_DG_A", "O_DG_B"]
    assert len(recorder.notes) == 1


def test_a_decided_taken_arm_settles_its_chain_in_an_orphan(
    tmp_path: Path, recorder: _Recorder
) -> None:
    """An arm decided and taken decides every later arm of its chain, an unstated
    ``#elif`` too: both later arms stay left out, and there is no note."""
    header = (
        "#pragma once\n"
        "#if STATED_TRUE\n// @One, O_S1, impl\n#elif UNSTATED\n// @Two, O_S2, impl\n"
        "#else\n// @Three, O_S3, impl\n#endif\n"
    )
    db = _orphan_project(tmp_path, header)
    assert _ids(tmp_path, db, ["STATED_TRUE=1"]) == ["O_S1"]
    assert recorder.notes == []


def test_the_notes_are_folded_per_compilation_database(
    tmp_path: Path, recorder: _Recorder
) -> None:
    """Two headers no entry of the one database includes: one note, at the database,
    naming both relative to its directory (``..`` for one outside it) and counting
    every arm read for an undecided condition. A third whose arms the table decides is
    not named."""
    root = tmp_path.resolve()
    (root / "build").mkdir()
    (root / "src").mkdir()
    db = _orphan_project(root / "build", ORPHAN_HEADER)
    (root / "src" / "other.h").write_text(
        "#pragma once\n#ifdef OTHER\n// @Other, O_OTHER, impl\n#endif\n",
        encoding="utf-8",
    )
    (root / "src" / "decided.h").write_text(
        "#pragma once\n#if 0\n// @Never, O_NEVER, impl\n#endif\n", encoding="utf-8"
    )
    analyse = SourceAnalyse(
        SourceAnalyseConfig(
            src_files=[
                root / "build" / "orphan.h",
                root / "src" / "other.h",
                root / "src" / "decided.h",
            ],
            src_dir=root,
            get_oneline_needs=True,
            preprocessor=PreprocessorConfig(compile_commands=db, std="c11"),
        )
    )
    analyse.git_remote_url = None
    analyse.git_commit_rev = None
    analyse.run(log_summary=False)
    assert sorted(need.need["id"] for need in analyse.oneline_needs) == [
        "O_ARM",
        "O_BASE",
        "O_OTHER",
        "O_X",
    ]
    ((message, location),) = recorder.notes
    assert location == f"{db}:1"
    assert message.startswith(
        "codelinks: 2 headers that no entry of this compilation database includes are "
        "read with the `[preprocessor]` table, and 3 `#if` arms on a condition the "
        "table does not decide are read as written rather than left out: `orphan.h`, "
        "`../src/other.h`. "
    )
    assert "include them from an entry's file" in message


def test_a_header_with_no_database_at_all_keeps_the_defines_read(
    tmp_path: Path, recorder: _Recorder
) -> None:
    """With no compilation database anywhere, a header is read with the
    ``[preprocessor]`` table as every other file is (its ``defines`` ARE the build's
    configuration): its arms are left out as that parse decides, with no note. The
    rule is for a header the database's entries could have included."""
    (tmp_path / "orphan.h").write_text(ORPHAN_HEADER, encoding="utf-8")
    assert _ids(tmp_path, None) == ["O_BASE"]
    assert recorder.notes == []


#: :data:`ORPHAN_HEADER` with ids the build's regex takes (``^[A-Z0-9_]{5,}``)
PROJECT_HEADER = ORPHAN_HEADER.replace("O_X,", "O_CONFIG_X,")

#: a ``src-trace`` project whose database (in ``build/``) compiles ``refs.cpp`` for
#: ``arm-none-eabi`` with ``-DCONFIG_X=1``, and whose ``orphan.h`` no entry includes
ORPHAN_PROJECT = {
    "toml_extra": (
        "\n[codelinks.projects.src.analyse.preprocessor]\n"
        'compile_commands = "../build/compile_commands.json"\n'
    ),
    "files": {
        "build/compile_commands.json": json.dumps(
            [
                {
                    "directory": "../src",
                    "file": "refs.cpp",
                    "arguments": [
                        "arm-none-eabi-g++",
                        "-DCONFIG_X=1",
                        "-c",
                        "refs.cpp",
                    ],
                }
            ]
        ),
        # the fixture's own, without its dangling reference
        "src/refs.cpp": "// @need-ids: REQ_001\nvoid implements_a() {}\n",
        "src/orphan.h": PROJECT_HEADER,
    },
}


def test_the_note_does_not_fail_a_warnings_as_errors_build(
    tmp_path: Path, make_app: Callable[..., SphinxTestApp]
) -> None:
    """A ``-W`` build over a project with a header no entry includes: its undecided
    arms are read, and the note is an information line on the status stream, not a
    warning, so the build passes. (It can over-report, never hide: nothing is left for
    the user to fix.)"""
    _project(tmp_path, **ORPHAN_PROJECT)
    app = _build(tmp_path, make_app, warningiserror=True)

    assert app.statuscode == 0
    assert build_warnings(app) == []
    needs = _json(app)["needs"]
    assert {"O_BASE", "O_CONFIG_X", "O_ARM"} <= set(needs)
    status = strip_colors(app._status.getvalue())
    database = tmp_path / "build" / "compile_commands.json"
    assert (
        f"{database}:1: codelinks: 1 header that no entry of this compilation database "
        "includes is read with the `[preprocessor]` table, and 2 `#if` arms"
    ) in status
    assert status.count(CODE) == 1


def _later(path: Path) -> None:
    later = path.stat().st_mtime + 10
    os.utime(path, (later, later))


def test_an_edit_to_an_orphan_header_reads_it_again(
    tmp_path: Path, make_app: Callable[..., SphinxTestApp]
) -> None:
    """An incremental build after an edit to the header no entry includes reads it
    again, under the same rule: the arm the edit adds, on a macro the table does not
    state, is read."""
    _project(tmp_path, **ORPHAN_PROJECT)
    app = _build(tmp_path, make_app)
    assert "O_CONFIG_Y" not in _json(app)["needs"]

    header = tmp_path / "src" / "orphan.h"
    header.write_text(
        PROJECT_HEADER + "#ifdef CONFIG_Y\n// @Y, O_CONFIG_Y, impl\n#endif\n",
        encoding="utf-8",
    )
    _later(header)
    app = _build(tmp_path, make_app, freshenv=False)

    needs = _json(app)["needs"]
    assert {"O_BASE", "O_CONFIG_X", "O_ARM", "O_CONFIG_Y"} <= set(needs)


def test_an_environment_pickled_at_env_version_10_is_read_again(
    tmp_path: Path, make_app: Callable[..., SphinxTestApp]
) -> None:
    """An environment of ``env_version`` 10 holds the records of a header no entry
    includes with every arm its parse skipped left out, where the arms the
    configuration does not decide are now read. Nothing in the sources or the
    configuration changed: ``env_version`` 11 is what has the build discard it and read
    every document again."""
    _project(tmp_path, **ORPHAN_PROJECT)
    app = _build(tmp_path, make_app)
    pickled = Path(app.doctreedir, "environment.pickle")
    env = pickle.loads(pickled.read_bytes())
    env.version["sphinx_codelinks"] = 10
    pickled.write_bytes(pickle.dumps(env, pickle.HIGHEST_PROTOCOL))

    app = _build(tmp_path, make_app, freshenv=False)

    status = strip_colors(app._status.getvalue())
    assert (
        "loading pickled environment... failed: build environment version not current"
        in status
    )


def test_a_header_looked_for_in_several_databases_is_noted_at_none(
    tmp_path: Path, recorder: _Recorder
) -> None:
    """A header with no database of its own is looked for in every database the
    analysis found; with two, its note is anchored at none of them (no location), says
    no compilation-database entry includes it, and names it by its canonical path."""
    root = tmp_path.resolve()
    for board in ("a", "b"):
        (root / board).mkdir()
        (root / board / "main.c").write_text("int main(void) { return 0; }\n")
        (root / board / "compile_commands.json").write_text(
            json.dumps(
                [
                    {
                        "directory": str(root / board),
                        "file": "main.c",
                        "arguments": ["clang", "-c", "main.c"],
                    }
                ]
            ),
            encoding="utf-8",
        )
    (root / "inc").mkdir()
    (root / "inc" / "orphan.h").write_text(ORPHAN_HEADER, encoding="utf-8")
    analyse = SourceAnalyse(
        SourceAnalyseConfig(
            src_files=[
                root / "a" / "main.c",
                root / "b" / "main.c",
                root / "inc" / "orphan.h",
            ],
            src_dir=root,
            get_oneline_needs=True,
            preprocessor=PreprocessorConfig(std="c11"),
        )
    )
    analyse.git_remote_url = None
    analyse.git_commit_rev = None
    analyse.run(log_summary=False)
    assert [need.need["id"] for need in analyse.oneline_needs] == [
        "O_BASE",
        "O_X",
        "O_ARM",
    ]
    ((message, location),) = recorder.notes
    assert location is None
    assert message.startswith(
        "codelinks: 1 header that no compilation-database entry includes is read with "
        "the `[preprocessor]` table, and 2 `#if` arms on a condition the table does not "
        f"decide are read as written rather than left out: `{(root / 'inc' / 'orphan.h').as_posix()}`. "
    )


def test_the_note_names_five_headers_and_counts_the_rest(
    tmp_path: Path, recorder: _Recorder
) -> None:
    """Seven headers no entry includes, one undecided arm each: the note names the
    first five, by path, and counts the other two, and counts every arm."""
    db = _orphan_project(tmp_path, ORPHAN_HEADER)
    names = [f"h{n}.h" for n in range(1, 8)]
    for name in names:
        (tmp_path / name).write_text(
            f"#pragma once\n#ifdef ONLY_{name[:2].upper()}\nint x;\n#endif\n",
            encoding="utf-8",
        )
    analyse = SourceAnalyse(
        SourceAnalyseConfig(
            src_files=[tmp_path / name for name in names],
            src_dir=tmp_path,
            get_oneline_needs=True,
            preprocessor=PreprocessorConfig(compile_commands=db, std="c11"),
        )
    )
    analyse.git_remote_url = None
    analyse.git_commit_rev = None
    analyse.run(log_summary=False)
    ((message, _),) = recorder.notes
    assert message.startswith(
        "codelinks: 7 headers that no entry of this compilation database includes are "
        "read with the `[preprocessor]` table, and 7 `#if` arms on a condition the "
        "table does not decide are read as written rather than left out: `h1.h`, "
        "`h2.h`, `h3.h`, `h4.h`, `h5.h` and 2 more. "
    )


def test_a_header_is_noted_once_per_build(
    tmp_path: Path, make_app: Callable[..., SphinxTestApp]
) -> None:
    """Two ``src-trace`` directives read the same header no entry includes (the
    project's on ``index``, and one of its file on ``page1``): the build notes it once,
    as ubCode does, not once per directive."""
    files = dict(ORPHAN_PROJECT["files"])
    files["src/quiet.h"] = "#pragma once\n#ifdef CONFIG_Q\nint q;\n#endif\n"
    files["docs/page1.rst"] = (
        "Page 1\n======\n\n.. src-trace::\n   :project: src\n   :file: quiet.h\n"
    )
    _project(tmp_path, toml_extra=ORPHAN_PROJECT["toml_extra"], files=files)
    app = _build(tmp_path, make_app)

    assert build_warnings(app) == []
    status = strip_colors(app._status.getvalue())
    assert status.count(CODE) == 1
    assert "2 headers that no entry of this compilation database includes" in status


#: two exclusive arms that implement one need, one per board
BOARD_HEADER = (
    "#pragma once\n"
    "#ifdef BOARD_A\n// @Board impl, IMPL_SAME, impl\n"
    "#else\n// @Board impl, IMPL_SAME, impl\n#endif\n"
)


@pytest.mark.parametrize("stated", [False, True], ids=["unstated", "stated"])
def test_an_undecided_pair_of_arms_can_define_one_need_twice(
    tmp_path: Path, make_app: Callable[..., SphinxTestApp], stated: bool
) -> None:
    """A marker in an arm read as written is a need like any other: the same id in two
    exclusive arms on a macro the table does not state is now defined twice, a
    ``codelinks.duplicate_need`` warning that fails a ``-W`` build. Stating the macro in
    ``[preprocessor] defines`` decides the chain, and the warning goes."""
    files = dict(ORPHAN_PROJECT["files"])
    files["src/orphan.h"] = BOARD_HEADER
    toml = ORPHAN_PROJECT["toml_extra"] + ('defines = ["BOARD_A"]\n' if stated else "")
    _project(tmp_path, toml_extra=toml, files=files)
    # (``warningiserror`` only where nothing warns: Sphinx 7 raises at the warning)
    app = _build(tmp_path, make_app, warningiserror=stated)

    assert "IMPL_SAME" in _json(app)["needs"]
    if stated:
        assert build_warnings(app) == []
        assert app.statuscode == 0
    else:
        (warning,) = build_warnings(app)
        assert warning.startswith(
            "src/orphan.h:5: WARNING: one-line need 'IMPL_SAME' is already defined"
        )
        assert warning.endswith(
            "(give the markers distinct ids)"
            + (" [codelinks.duplicate_need]" if _SHOWS_WARNING_TYPES else "")
        )


@pytest.mark.skipif(
    os.name == "nt", reason="a symbolic link needs privileges on Windows"
)
def test_the_note_names_canonical_paths(tmp_path: Path, recorder: _Recorder) -> None:
    """The database and the header named through a symbolic link to their directory:
    the note is anchored at the database's canonical path and names the header relative
    to its canonical directory, as ubCode's does."""
    real = (tmp_path / "real").resolve()
    real.mkdir()
    db = _orphan_project(real, ORPHAN_HEADER)
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    analyse = SourceAnalyse(
        SourceAnalyseConfig(
            src_files=[link / "orphan.h"],
            src_dir=link,
            get_oneline_needs=True,
            preprocessor=PreprocessorConfig(
                compile_commands=link / "compile_commands.json", std="c11"
            ),
        )
    )
    analyse.git_remote_url = None
    analyse.git_commit_rev = None
    analyse.run(log_summary=False)
    ((message, location),) = recorder.notes
    assert location == f"{db}:1"
    assert "rather than left out: `orphan.h`. " in message
