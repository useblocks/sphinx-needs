"""`bump.py`: the rewrites, the changelog's two conventions, and the order of the run.

Every rewrite is a pure function -- text in, text out -- so the assertions here need no
`uv`, no `git` and no network, which is what makes them cheap enough to be run. The steps
that DO shell out go through one `Runner`, and the fake below records the commands in
order: what this file asserts about the orchestration is the sequence, because the order is
the part of the recipe that matters (`--no-sync` before `uv lock`, the floors before the
lock, nothing at all before the cleanliness check).

The changelog is tested in BOTH conventions this repository actually has, because the whole
design of `stamp_changelog` is that it mirrors the file rather than imposing one shape:
sphinx-needs' entries carry a `:Full Changelog:` line and a `DD.MM.YYYY` date and there is
no `Unreleased` section; sphinx-mounts' carry neither the link nor that date format, and an
`Unreleased` section is what a release converts.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from sn_tools import bump

pytestmark = pytest.mark.filterwarnings("error")


NEEDS_STYLE = """\
.. _ubcode: https://ubcode.useblocks.com/
.. _changelog:

Changelog
=========

.. _`release:8.5.0`:

8.5.0
-----

:Released: 03.09.2026
:Full Changelog: `v8.4.0...v8.5.0 <https://github.com/useblocks/sphinx-needs/compare/8.4.0...8.5.0>`__

This release is about charts.

Improvements
............

- something (:pr:`1831`)

.. _`release:8.4.0`:

8.4.0
-----

:Released: 27.08.2026
"""

MOUNTS_STYLE = """\
.. _changelog:

Changelog
=========

Unreleased
----------

- **Python 3.11 is supported again**: the floor moves down from 3.12 to 3.11.

- **A second bullet**, so that dropping one is visible.

.. _`release:0.2.0`:

0.2.0
-----

:Released: 2026-08-27

- the previous release.
"""

WHEN = date(2026, 9, 6)


class FakeRunner:
    """Records the commands in order and answers the ones whose output is read."""

    def __init__(self, answers: dict[str, str] | None = None) -> None:
        self.calls: list[list[str]] = []
        self.answers = answers or {}

    def run(self, command: list[str], *, quiet: bool = False) -> str:
        self.calls.append(command)
        joined = " ".join(command)
        for key, value in self.answers.items():
            if key in joined:
                return value
        return ""


def uv_runner(
    manifest: Path, old: str, new: str, name: str = "acme-core", tags: str = ""
) -> FakeRunner:
    """A fake `uv version` with both halves `bump` depends on, plus a fake tag list.

    `bump` PREVIEWS the new version with `uv version --dry-run` in its compute phase and
    READS IT BACK from the manifest after the real call, and it refuses if the two
    disagree. So the fake has to answer the preview with uv's own
    `<name> <old> => <new>` line AND move the manifest on the real call; a fake that did
    only one of those would make every integration test below about the wrong version.
    """

    class Uv(FakeRunner):
        def run(self, command: list[str], *, quiet: bool = False) -> str:
            recorded = super().run(command, quiet=quiet)
            if command[:2] == ["uv", "version"]:
                if "--dry-run" in command:
                    return f"{name} {old} => {new}\n"
                manifest.write_text(
                    manifest.read_text(encoding="utf-8").replace(
                        f'version = "{old}"', f'version = "{new}"'
                    ),
                    encoding="utf-8",
                )
            elif command[:2] == ["git", "tag"]:
                return tags
            return recorded

    return Uv()


# --- the `__version__` literal -------------------------------------------------------------


def test_the_module_literal_moves() -> None:
    text = '"""A module."""\n\n__version__ = "8.5.0"\n\nX = 1\n'
    assert bump.rewrite_module_literal(text, "8.5.0", "8.6.0") == (
        '"""A module."""\n\n__version__ = "8.6.0"\n\nX = 1\n'
    )


def test_an_annotated_literal_in_single_quotes_moves_too() -> None:
    text = "__version__: str = '0.2.0'\n"
    assert bump.rewrite_module_literal(text, "0.2.0", "0.3.0") == (
        "__version__: str = '0.3.0'\n"
    )


def test_nothing_else_that_mentions_the_version_is_touched() -> None:
    """The match is anchored to the assignment, not to the number: a docstring or a
    fallback carrying the same string must not move with it."""
    text = (
        '"""Version 8.5.0 of the thing."""\n\n__version__ = "8.5.0"\nOTHER = "8.5.0"\n'
    )
    got = bump.rewrite_module_literal(text, "8.5.0", "8.6.0")
    assert (
        got
        == '"""Version 8.5.0 of the thing."""\n\n__version__ = "8.6.0"\nOTHER = "8.5.0"\n'
    )


@pytest.mark.parametrize(
    ("text", "count"),
    [
        ('__version__ = "8.5.0"\nif True:\n    pass\n__version__ = "8.5.0"\n', 2),
        # two DIFFERING assignments: the readers -- this one and
        # `check_workspace.module_version` -- both take the first, while Python leaves the
        # second in `__version__` at import time and stamps it into `needs.json`. Counting
        # every assignment rather than the matching ones is what refuses it
        ('__version__ = "8.5.0"\n__version__ = "2.0"\n', 2),
        ("X = 1\n", 0),
    ],
)
def test_anything_but_exactly_one_assignment_is_refused(text: str, count: int) -> None:
    with pytest.raises(bump.BumpError) as caught:
        bump.rewrite_module_literal(text, "8.5.0", "8.6.0", "src/m/__init__.py")
    assert f"found {count}" in str(caught.value)
    assert "src/m/__init__.py" in str(caught.value)


def test_a_literal_that_disagrees_with_the_manifest_is_refused_naming_both() -> None:
    """The defect this closes: the rewrite used to be keyed on the literal's OWN value, so
    `old` matched by construction and a drifted literal was silently overwritten -- healing
    the one drift `check-workspace` was shouting about, without anyone seeing which of the
    two numbers won."""
    with pytest.raises(bump.BumpError) as caught:
        bump.rewrite_module_literal(
            '__version__ = "8.4.9"\n', "8.5.0", "8.6.0", "src/m/__init__.py"
        )
    message = str(caught.value)
    assert '`__version__` is "8.4.9"' in message
    assert 'the manifest declares "8.5.0"' in message
    assert "src/m/__init__.py" in message
    assert "will not guess" in message


# --- the docker workflow's NEEDS_VERSION fallback --------------------------------------------

DOCKER = """\
env:
  # a comment mentioning 8.5.0
  NEEDS_VERSION: ${{ startsWith(github.ref, 'refs/tags/') && github.ref_name || '8.5.0' }}
  DEPLOY_IMAGE: ${{ github.event_name != 'pull_request' }}
"""


def test_the_docker_fallback_becomes_the_prefixed_tag() -> None:
    """It is a git REF, not a version: the Dockerfile checks it out. AGENTS.md's release
    recipe says `sphinx-needs-v<version>`, and a bare version would be a ref that resolves
    to the tag of a tree in which `packages/sphinx-needs` does not exist."""
    got = bump.rewrite_docker_literal(DOCKER, "sphinx-needs-v8.6.0")
    assert "|| 'sphinx-needs-v8.6.0' }}" in got
    assert "# a comment mentioning 8.5.0" in got  # only the literal moves
    assert "DEPLOY_IMAGE" in got


def test_no_needs_version_line_is_refused() -> None:
    with pytest.raises(bump.BumpError) as caught:
        bump.rewrite_docker_literal("env:\n  OTHER: 1\n", "sphinx-needs-v8.6.0")
    assert "found 0" in str(caught.value)


# --- dependant detection ----------------------------------------------------------------


def test_dependants_are_found_through_both_dependency_tables() -> None:
    """check (4)'s edge rule: `dependencies` AND every `optional-dependencies` list."""
    projects = {
        "acme-core": {"name": "acme-core", "dependencies": []},
        "acme-plugin": {"name": "acme-plugin", "dependencies": ["acme-core>=1,<2"]},
        "acme-extra": {
            "name": "acme-extra",
            "dependencies": ["sphinx"],
            "optional-dependencies": {"all": ["acme-core>=1,<2"]},
        },
        "acme-other": {"name": "acme-other", "dependencies": ["sphinx"]},
    }
    assert bump.dependants(projects, "acme-core") == ["acme-extra", "acme-plugin"]
    assert bump.dependants(projects, "acme-other") == []


# --- the changelog, in sphinx-needs' convention -------------------------------------------


def test_a_needs_style_entry_is_inserted_with_the_files_date_format() -> None:
    got, what = bump.stamp_changelog(
        NEEDS_STYLE,
        version="8.6.0",
        when=WHEN,
        previous_tag="8.5.0",
        new_tag="sphinx-needs-v8.6.0",
    )
    head = got.splitlines()[:14]
    assert head == [
        ".. _ubcode: https://ubcode.useblocks.com/",
        ".. _changelog:",
        "",
        "Changelog",
        "=========",
        "",
        ".. _`release:8.6.0`:",
        "",
        "8.6.0",
        "-----",
        "",
        ":Released: 06.09.2026",
        ":Full Changelog: `8.5.0...sphinx-needs-v8.6.0 <https://github.com/useblocks/sphinx-needs/compare/8.5.0...sphinx-needs-v8.6.0>`__",
        "",
    ]
    # the file's own format, DD.MM.YYYY -- not ISO
    assert ":Released: 2026-09-06" not in got
    # nothing is invented under the heading, and the old entry is untouched
    assert ".. _`release:8.5.0`:" in got
    assert "This release is about charts." in got
    assert "TODO" not in got
    assert "summary paragraph is yours to write" in what


def test_the_bare_previous_tag_is_used_verbatim_in_both_halves_of_the_link() -> None:
    """sphinx-needs' releases before the monorepo move are bare tags and the new one is
    prefixed, so the compare link legitimately mixes the two namespaces. Rendering either
    half from the version instead would produce a 404."""
    got, _ = bump.stamp_changelog(
        NEEDS_STYLE,
        version="8.6.0",
        when=WHEN,
        previous_tag="8.5.0",
        new_tag="sphinx-needs-v8.6.0",
    )
    line = next(
        line for line in got.splitlines() if line.startswith(":Full Changelog:")
    )
    assert line.count("8.5.0...sphinx-needs-v8.6.0") == 2  # the text and the URL
    assert line.endswith("`__")


def test_a_missing_previous_tag_refuses_rather_than_link_to_nothing() -> None:
    with pytest.raises(bump.BumpError) as caught:
        bump.stamp_changelog(
            NEEDS_STYLE,
            version="8.6.0",
            when=WHEN,
            previous_tag="",
            new_tag="sphinx-needs-v8.6.0",
            path="docs/changelog.rst",
        )
    assert "docs/changelog.rst" in str(caught.value)
    assert "git fetch --tags" in str(caught.value)


# --- the changelog, in sphinx-mounts' convention ------------------------------------------


def test_a_mounts_style_unreleased_section_is_converted_keeping_every_bullet() -> None:
    got, what = bump.stamp_changelog(
        MOUNTS_STYLE,
        version="0.3.0",
        when=WHEN,
        previous_tag="sphinx-mounts-v0.2.0",
        new_tag="sphinx-mounts-v0.3.0",
    )
    head = got.splitlines()[:11]
    assert head == [
        ".. _changelog:",
        "",
        "Changelog",
        "=========",
        "",
        ".. _`release:0.3.0`:",
        "",
        "0.3.0",
        "-----",
        "",
        ":Released: 2026-09-06",
    ]
    assert "Unreleased" not in got
    # every bullet the section carried IS the release's changelog
    assert "**Python 3.11 is supported again**" in got
    assert "**A second bullet**" in got
    assert "2 top-level bullets kept" in what


def test_a_mounts_style_entry_gets_no_compare_line() -> None:
    """The rule is the file's own: emit the link iff the newest existing entry has one.
    sphinx-mounts' entries do not, and a release must not start a convention."""
    got, _ = bump.stamp_changelog(
        MOUNTS_STYLE,
        version="0.3.0",
        when=WHEN,
        previous_tag="sphinx-mounts-v0.2.0",
        new_tag="sphinx-mounts-v0.3.0",
    )
    assert ":Full Changelog:" not in got


def test_the_iso_date_format_is_read_off_the_file_not_assumed() -> None:
    for text, expected in (
        (NEEDS_STYLE, ":Released: 06.09.2026"),
        (MOUNTS_STYLE, ":Released: 2026-09-06"),
    ):
        assert bump.released_line(text, WHEN) == expected
    # a file with no `:Released:` at all falls back to ISO
    assert bump.released_line("Changelog\n=========\n", WHEN) == ":Released: 2026-09-06"


def test_the_prefixed_previous_tag_keeps_its_prefix_in_both_halves() -> None:
    """The mirror of the bare case above, and the one that is not sphinx-needs.

    `previous_tag` returns a PREFIXED tag for every member whose releases postdate the
    monorepo move. Rendering either half from the version instead would not merely 404 in
    this repository -- the bare tag namespace here is sphinx-needs' own pre-move history
    (`0.3.5`, `0.5.0`, `0.7.9`, ...), so a future `sphinx-mounts-v0.5.0` stripped to
    `0.5.0` would resolve to a sphinx-needs tag from 2020 and render a plausible, entirely
    wrong diff.
    """
    needs_style_mounts = MOUNTS_STYLE.replace(
        ":Released: 2026-08-27",
        ":Released: 2026-08-27\n:Full Changelog: `sphinx-mounts-v0.1.4...sphinx-mounts-v0.2.0"
        " <https://github.com/useblocks/sphinx-needs/compare/sphinx-mounts-v0.1.4...sphinx-mounts-v0.2.0>`__",
    )
    got, _ = bump.stamp_changelog(
        needs_style_mounts,
        version="0.3.0",
        when=WHEN,
        previous_tag="sphinx-mounts-v0.2.0",
        new_tag="sphinx-mounts-v0.3.0",
    )
    line = next(
        line for line in got.splitlines() if line.startswith(":Full Changelog:")
    )
    assert line.count("sphinx-mounts-v0.2.0...sphinx-mounts-v0.3.0") == 2
    assert (
        "compare/0.2.0..." not in line
    )  # the prefix survives in the URL, not just the text


def test_an_unreleased_heading_below_the_first_label_takes_the_insert_branch() -> None:
    """The `above every released entry` bound, made load-bearing.

    Without it, an `Unreleased` heading left by mistake inside an older entry's body is
    converted -- which puts the NEW release below the older one, breaking newest-first
    ordering and silently annexing that entry's body.
    """
    text = (
        ".. _changelog:\n\nChangelog\n=========\n\n"
        ".. _`release:1.0.0`:\n\n1.0.0\n-----\n\n:Released: 2026-08-27\n\n"
        "Unreleased\n----------\n\n- a stray heading someone left in 1.0.0's body\n"
    )
    got, what = bump.stamp_changelog(
        text, version="1.1.0", when=WHEN, previous_tag="", new_tag="acme-v1.1.0"
    )
    assert "inserted 1.1.0 above the newest entry" in what
    lines = got.splitlines()
    assert lines.index(".. _`release:1.1.0`:") < lines.index(".. _`release:1.0.0`:")
    assert "Unreleased" in got  # left exactly where it was, for a human to deal with


@pytest.mark.parametrize("adornment", ["==========", "~~~~~~~~~~", "----------"])
def test_an_unreleased_section_is_found_under_any_rst_adornment(adornment: str) -> None:
    """RST fixes no adornment character -- a document's first-used one becomes its top
    level -- so `-` was a convention of the two files here, not a rule. Matching it alone
    left an `Unreleased` section standing above a new, empty entry, keeping the bullets
    that were meant to be that release's changelog, and raised nothing."""
    text = MOUNTS_STYLE.replace("Unreleased\n----------", f"Unreleased\n{adornment}")
    got, what = bump.stamp_changelog(
        text,
        version="0.3.0",
        when=WHEN,
        previous_tag="sphinx-mounts-v0.2.0",
        new_tag="sphinx-mounts-v0.3.0",
    )
    assert (
        what == "converted the `Unreleased` section to 0.3.0 (2 top-level bullets kept)"
    )
    assert "Unreleased" not in got
    assert "**Python 3.11 is supported again**" in got


def test_the_changelog_title_is_found_under_any_rst_adornment() -> None:
    """The same rule, asked of the other heading: the two used to hard-code DIFFERENT
    characters in one module, which is the drift that produced the bug above."""
    text = ".. _changelog:\n\nChangelog\n#########\n"
    got, _ = bump.stamp_changelog(
        text, version="1.0.0", when=WHEN, previous_tag="", new_tag="acme-v1.0.0"
    )
    assert got.endswith(
        ".. _`release:1.0.0`:\n\n1.0.0\n-----\n\n:Released: 2026-09-06\n"
    )


@pytest.mark.parametrize("value", ["3.9.2026", "27.8.2026", "03.09.2026"])
def test_an_unpadded_day_first_date_is_still_day_first(value: str) -> None:
    """`^\\d{2}\\.` refused a hand-stamped `3.9.2026`, so ONE such line would have flipped
    the file to ISO for that release and every one after it."""
    assert bump.released_line(f":Released: {value}\n", WHEN) == ":Released: 06.09.2026"


@pytest.mark.parametrize("value", ["3 Sep 2026", "2026/08/27", "September 3, 2026"])
def test_an_unrecognised_released_format_refuses_rather_than_silently_going_iso(
    value: str,
) -> None:
    """ "ISO when the file has none" and "ISO when the file has one I cannot classify" are
    different rules, and only the first is a documented convention."""
    with pytest.raises(bump.BumpError) as caught:
        bump.released_line(
            f":Released: {value}\n", WHEN, "packages/acme/docs/changelog.rst"
        )
    message = str(caught.value)
    assert value in message
    assert "packages/acme/docs/changelog.rst" in message
    assert "neither DD.MM.YYYY nor YYYY-MM-DD" in message


def test_a_file_with_no_title_and_no_label_is_refused_by_name() -> None:
    with pytest.raises(bump.BumpError) as caught:
        bump.stamp_changelog(
            "Some notes\n==========\n",
            version="1.0.0",
            when=WHEN,
            previous_tag="",
            new_tag="acme-v1.0.0",
            path="packages/acme/docs/changelog.rst",
        )
    assert "packages/acme/docs/changelog.rst" in str(caught.value)


def test_an_empty_changelog_gets_its_first_entry_under_the_title() -> None:
    got, _ = bump.stamp_changelog(
        ".. _changelog:\n\nChangelog\n=========\n",
        version="1.0.0",
        when=WHEN,
        previous_tag="",
        new_tag="acme-v1.0.0",
    )
    assert got == (
        ".. _changelog:\n\nChangelog\n=========\n\n"
        ".. _`release:1.0.0`:\n\n1.0.0\n-----\n\n:Released: 2026-09-06\n"
    )


# --- the run: preconditions and the order of the commands ----------------------------------


@pytest.fixture
def tree(workspace, tmp_path: Path):
    """A scratch workspace with a member that has a changelog, as the real ones do."""

    def build(**kwargs):
        root = workspace(
            {
                "acme-core": {"version": "1.2.3", "module_version": "1.2.3"},
                "acme-plugin": {
                    "version": "0.1.0",
                    "module_version": "0.1.0",
                    "dependencies": ["acme-core>=1.2.3,<2"],
                },
            },
            **kwargs,
        )
        for name, text in (("acme-core", MOUNTS_STYLE), ("acme-plugin", MOUNTS_STYLE)):
            docs = root / "packages" / name / "docs"
            docs.mkdir(parents=True, exist_ok=True)
            (docs / "changelog.rst").write_text(text, encoding="utf-8")
        return root

    return build


def run(root: Path, *argv: str, runner=None) -> tuple[int, FakeRunner]:
    fake = runner or FakeRunner()
    return bump.main([*argv, "--root", str(root)], runner=fake), fake  # ty: ignore[invalid-argument-type]


def test_an_unknown_distribution_is_refused(tree, capsys) -> None:
    code, fake = run(tree(), "acme-nope", "--bump", "patch")
    assert code == 1
    assert "is not a member of this workspace" in capsys.readouterr().out
    # refused BEFORE anything ran
    assert fake.calls == []


def test_a_virtual_member_is_refused(tree, capsys) -> None:
    root = tree()
    manifest = root / "packages" / "acme-plugin" / "pyproject.toml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8") + "\n[tool.uv]\npackage = false\n",
        encoding="utf-8",
    )
    code, fake = run(root, "acme-plugin", "--bump", "patch")
    assert code == 1
    out = capsys.readouterr().out
    assert "virtual member" in out and "no version to bump" in out
    assert fake.calls == []


def test_a_dirty_target_file_is_refused_and_named(tree, capsys) -> None:
    root = tree()
    fake = FakeRunner({"git status": " M packages/acme-core/pyproject.toml\n"})
    code, _ = run(root, "acme-core", "--bump", "minor", runner=fake)
    assert code == 1
    out = capsys.readouterr().out
    assert "not clean" in out
    assert "M packages/acme-core/pyproject.toml" in out
    # the cleanliness check is the ONLY thing that ran
    assert [call[:2] for call in fake.calls] == [["git", "status"]]


def test_the_cleanliness_pathspec_is_every_guarded_file_and_not_the_lock(tree) -> None:
    """The WHOLE pathspec, not two members of it.

    Asserting only "uv.lock is absent" and "one manifest is present" left the fence able to
    drop the module literal, the changelog, the docker workflow or a dependant's manifest
    and stay green -- and the step-1 line would still count them, because the count comes
    from the guarded list and the check from the pathspec. This is a release of the member
    that HAS a dependant, so all five hand-written files are in it.

    `uv.lock` is written but deliberately not guarded: `uv lock` derives it from the
    manifests, so a dirty one is work this run redoes rather than destroys -- and guarding
    it would make the planner's own sequence impossible, since releasing two members in one
    pull request means the second bump always meets the lock the first left dirty.
    """
    root = tree()
    fake = uv_runner(
        root / "packages" / "acme-core" / "pyproject.toml", "1.2.3", "1.3.0"
    )
    code, _ = run(
        root, "acme-core", "--bump", "minor", "--date", "2026-09-06", runner=fake
    )
    assert code == 0
    assert fake.calls[0][:4] == ["git", "status", "--porcelain", "--"]
    assert fake.calls[0][4:] == [
        "packages/acme-core/docs/changelog.rst",
        "packages/acme-core/pyproject.toml",
        "packages/acme-core/src/acme_core/__init__.py",
        "packages/acme-plugin/pyproject.toml",
    ]
    assert "uv.lock" not in fake.calls[0]


def test_the_dry_run_writes_nothing_and_locks_nothing(tree, capsys) -> None:
    root = tree()
    before = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
    fake = uv_runner(
        root / "packages" / "acme-core" / "pyproject.toml", "1.2.3", "1.3.0"
    )
    code, _ = run(root, "acme-core", "--bump", "minor", "--dry-run", runner=fake)
    assert code == 0
    assert {
        path: path.read_bytes() for path in root.rglob("*") if path.is_file()
    } == before
    # `uv lock` and `propagate_floors.py` do not run at all in a dry run; the two git
    # reads and `uv version --dry-run` do, because a preview that guessed at the new
    # version or the previous tag would not be a preview of this run
    assert [call[:2] for call in fake.calls] == [
        ["git", "status"],
        ["uv", "version"],
        ["git", "tag"],
    ]
    assert fake.calls[1][-1] == "--dry-run"
    out = capsys.readouterr().out
    assert 'would set version = "1.3.0"' in out
    assert "would run `uv lock`" in out


def test_the_commands_run_in_the_recipes_order(tree, capsys) -> None:
    """Compute, then apply.

    Every read comes first -- the cleanliness check, the `--dry-run` preview of the new
    version, the tag list -- because the refusals that depend on them must fire while the
    tree is untouched. Only then the real `uv version --no-sync` (which leaves the lock
    stale), the dependants' floors, and `uv lock`.
    """
    root = tree()
    fake = uv_runner(
        root / "packages" / "acme-core" / "pyproject.toml", "1.2.3", "1.3.0"
    )
    code, _ = run(
        root, "acme-core", "--bump", "minor", "--date", "2026-09-06", runner=fake
    )
    assert code == 0
    assert [call[:2] for call in fake.calls] == [
        ["git", "status"],
        ["uv", "version"],  # --dry-run: the preview
        ["git", "tag"],
        ["uv", "version"],  # the real one
        [fake.calls[4][0], fake.calls[4][1]],  # <interpreter> propagate_floors.py
        ["uv", "lock"],
    ]
    preview = [
        "uv",
        "version",
        "--package",
        "acme-core",
        "--bump",
        "minor",
        "--no-sync",
    ]
    assert fake.calls[1] == [*preview, "--dry-run"]
    assert fake.calls[3] == preview
    assert fake.calls[4][1].endswith("propagate_floors.py")
    assert fake.calls[4][2] == "acme-core"


def test_a_real_run_writes_all_four_files(tree, capsys) -> None:
    root = tree()
    manifest = root / "packages" / "acme-core" / "pyproject.toml"
    code, _ = run(
        root,
        "acme-core",
        "--bump",
        "minor",
        "--date",
        "2026-09-06",
        runner=uv_runner(manifest, "1.2.3", "1.3.0"),
    )
    assert code == 0
    module = root / "packages" / "acme-core" / "src" / "acme_core" / "__init__.py"
    assert '__version__ = "1.3.0"' in module.read_text(encoding="utf-8")
    changelog = (root / "packages" / "acme-core" / "docs" / "changelog.rst").read_text(
        encoding="utf-8"
    )
    assert ".. _`release:1.3.0`:" in changelog
    assert ":Released: 2026-09-06" in changelog
    out = capsys.readouterr().out
    assert (
        "acme-plugin" in out
    )  # the dependant was named, and the floors were propagated
    assert "git tag acme-core-v1.3.0 && git push origin acme-core-v1.3.0" in out


def test_the_docker_workflow_is_rewritten_only_for_sphinx_needs(
    workspace, tmp_path: Path, capsys
) -> None:
    """The step is gated on the distribution name, and what it writes is the PREFIXED tag.

    The pure rewrite is asserted above; this asserts the caller hands it a git ref rather
    than a bare version -- the mistake the unit test cannot see, and the one whose symptom
    is a docker build on an untagged branch checking out a ref that does not exist.
    """
    root = workspace(
        {"sphinx-needs": {"version": "8.5.0", "module_version": "8.5.0"}},
        directories={"sphinx-needs": "packages/sphinx-needs"},
    )
    docs = root / "packages" / "sphinx-needs" / "docs"
    docs.mkdir(parents=True)
    (docs / "changelog.rst").write_text(MOUNTS_STYLE, encoding="utf-8")
    workflow = root / ".github" / "workflows" / "docker.yaml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text(DOCKER, encoding="utf-8")

    code, _ = run(
        root,
        "sphinx-needs",
        "--to",
        "8.6.0",
        "--date",
        "2026-09-06",
        runner=uv_runner(
            root / "packages" / "sphinx-needs" / "pyproject.toml",
            "8.5.0",
            "8.6.0",
            name="sphinx-needs",
        ),
    )
    assert code == 0
    written = workflow.read_text(encoding="utf-8")
    assert "|| 'sphinx-needs-v8.6.0' }}" in written
    assert "|| '8.6.0' }}" not in written
    out = capsys.readouterr().out
    assert "NEEDS_VERSION fallback `sphinx-needs-v8.6.0`" in out
    # and the smoke test is in the hand steps for this member, as AGENTS.md says
    assert "uv run poe smoke-needs" in out


def snapshot(root: Path) -> dict[Path, bytes]:
    return {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}


def test_a_refusal_from_the_last_step_leaves_the_tree_untouched(tree, capsys) -> None:
    """The HIGH finding this closes.

    A changelog whose newest entry carries a `:Full Changelog:` line, and a checkout with
    no tag below the new version, is a legitimate refusal from what used to be step 7. It
    used to arrive with the manifest, the module literal, the docker fallback and the lock
    already rewritten -- and that tree is green under `poe lint`, `check-workspace` AND the
    plan job, because nothing in this repository fences a missing changelog entry. It also
    blocked its own re-run, because bump's cleanliness precondition then saw bump's own
    leftovers.

    Now every rewrite is computed before any of them is written, so the refusal happens
    with the tree untouched: no file changed, and no `uv version` without `--dry-run`, no
    `propagate_floors.py`, no `uv lock` ever ran.
    """
    root = tree()
    with_compare = MOUNTS_STYLE.replace(
        ":Released: 2026-08-27", ":Released: 2026-08-27\n:Full Changelog: `a...b <u>`__"
    )
    (root / "packages" / "acme-core" / "docs" / "changelog.rst").write_text(
        with_compare, encoding="utf-8"
    )
    before = snapshot(root)
    fake = uv_runner(
        root / "packages" / "acme-core" / "pyproject.toml", "1.2.3", "1.3.0", tags=""
    )
    code, _ = run(
        root, "acme-core", "--bump", "minor", "--date", "2026-09-06", runner=fake
    )
    assert code == 1
    assert (
        "no release tag below 1.3.0 exists in this checkout" in capsys.readouterr().out
    )
    assert snapshot(root) == before
    assert [call[:2] for call in fake.calls] == [
        ["git", "status"],
        ["uv", "version"],
        ["git", "tag"],
    ]
    assert fake.calls[1][-1] == "--dry-run"  # the only `uv version` was the preview


def test_a_drifted_module_literal_refuses_before_anything_is_written(
    tree, capsys
) -> None:
    """A3 and A1 together: the drift refusal is one of the ones that used to fire with the
    manifest already moved."""
    root = tree()
    module = root / "packages" / "acme-core" / "src" / "acme_core" / "__init__.py"
    module.write_text('"""scratch."""\n\n__version__ = "1.2.2"\n', encoding="utf-8")
    before = snapshot(root)
    fake = uv_runner(
        root / "packages" / "acme-core" / "pyproject.toml", "1.2.3", "1.3.0"
    )
    code, _ = run(
        root, "acme-core", "--bump", "minor", "--date", "2026-09-06", runner=fake
    )
    assert code == 1
    out = capsys.readouterr().out
    assert '`__version__` is "1.2.2"' in out and 'the manifest declares "1.2.3"' in out
    assert snapshot(root) == before
    assert not any(
        call[:2] == ["uv", "version"] and "--dry-run" not in call for call in fake.calls
    )


@pytest.mark.parametrize("target", ["1.0.0", "1.2.3"])
def test_a_version_that_does_not_move_up_is_refused(tree, capsys, target: str) -> None:
    """A downgrade (a typo) and a re-release of the current version. Neither is a release,
    and neither was refused: the plan job's check 2 compares the tag to the manifest, and
    after a downgrade they agree."""
    root = tree()
    before = snapshot(root)
    fake = uv_runner(
        root / "packages" / "acme-core" / "pyproject.toml", "1.2.3", target
    )
    code, _ = run(
        root, "acme-core", "--to", target, "--date", "2026-09-06", runner=fake
    )
    assert code == 1
    out = capsys.readouterr().out
    assert f"acme-core 1.2.3 -> {target} is not a release" in out
    assert "a version never moves down" in out
    assert snapshot(root) == before


def test_a_version_the_changelog_already_carries_is_refused(tree, capsys) -> None:
    """A re-stamp produces two identical RST targets, which `poe docs-needs` fails on with
    a docutils warning that says nothing about a release -- minutes later."""
    root = tree()
    before = snapshot(root)
    # the mounts-shaped scratch changelog already carries `release:0.2.0`
    fake = uv_runner(
        root / "packages" / "acme-plugin" / "pyproject.toml",
        "0.1.0",
        "0.2.0",
        name="acme-plugin",
    )
    code, _ = run(
        root, "acme-plugin", "--to", "0.2.0", "--date", "2026-09-06", runner=fake
    )
    assert code == 1
    out = capsys.readouterr().out
    assert (
        "packages/acme-plugin/docs/changelog.rst already carries a `release:0.2.0` label"
        in out
    )
    assert snapshot(root) == before


def test_the_previous_tag_comes_from_git_and_keeps_its_prefix(tree, capsys) -> None:
    """End to end for B3: the tag list is read from git, `previous_tag` picks the release
    below the new one out of it, and the prefix reaches the compare link."""
    root = tree()
    with_compare = MOUNTS_STYLE.replace(
        ":Released: 2026-08-27",
        ":Released: 2026-08-27\n:Full Changelog: `acme-core-v1.1.0...acme-core-v1.2.3"
        " <https://github.com/useblocks/sphinx-needs/compare/acme-core-v1.1.0...acme-core-v1.2.3>`__",
    )
    changelog = root / "packages" / "acme-core" / "docs" / "changelog.rst"
    changelog.write_text(with_compare, encoding="utf-8")
    fake = uv_runner(
        root / "packages" / "acme-core" / "pyproject.toml",
        "1.2.3",
        "1.3.0",
        tags="acme-core-v1.1.0\nacme-core-v1.2.3\nacme-plugin-v0.1.0\nnot-a-tag\n",
    )
    code, _ = run(
        root, "acme-core", "--bump", "minor", "--date", "2026-09-06", runner=fake
    )
    assert code == 0
    line = next(
        line
        for line in changelog.read_text(encoding="utf-8").splitlines()
        if line.startswith(":Full Changelog:")
    )
    assert line.count("acme-core-v1.2.3...acme-core-v1.3.0") == 2
    assert "compare/1.2.3..." not in line


def test_a_member_with_no_dependants_skips_propagate_floors(tree, capsys) -> None:
    root = tree()
    # 0.3.0, not 0.2.0: the scratch changelog is the mounts shape, which already carries a
    # `release:0.2.0` label, and the precondition below refuses a duplicate
    fake = uv_runner(
        root / "packages" / "acme-plugin" / "pyproject.toml",
        "0.1.0",
        "0.3.0",
        name="acme-plugin",
    )
    code, _ = run(
        root, "acme-plugin", "--to", "0.3.0", "--date", "2026-09-06", runner=fake
    )
    assert code == 0
    assert not any("propagate_floors" in " ".join(call) for call in fake.calls)
    assert "no dependants" in capsys.readouterr().out
    assert fake.calls[1] == [
        "uv",
        "version",
        "--package",
        "acme-plugin",
        "0.3.0",
        "--no-sync",
        "--dry-run",
    ]
