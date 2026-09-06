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


def writing_runner(manifest: Path, old: str, new: str) -> FakeRunner:
    """A fake `uv version` that writes the manifest the way the real one does.

    Which is the point: `bump` READS the new version back out of the manifest rather than
    computing it, so a fake that only records the call would let the run carry on with the
    old number and every later assertion would be about the wrong version.
    """

    class Writing(FakeRunner):
        def run(self, command: list[str], *, quiet: bool = False) -> str:
            if command[:2] == ["uv", "version"]:
                manifest.write_text(
                    manifest.read_text(encoding="utf-8").replace(
                        f'version = "{old}"', f'version = "{new}"'
                    ),
                    encoding="utf-8",
                )
            return super().run(command, quiet=quiet)

    return Writing()


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
        ('__version__ = "9.9.9"\n', 0),
        ('__version__ = "8.5.0"\nif True:\n    pass\n__version__ = "8.5.0"\n', 2),
    ],
)
def test_anything_but_exactly_one_literal_is_refused(text: str, count: int) -> None:
    """A module whose literal already disagrees with the manifest, or that carries two, is
    a state no rewrite may pick a winner in."""
    with pytest.raises(bump.BumpError) as caught:
        bump.rewrite_module_literal(text, "8.5.0", "8.6.0")
    assert f"found {count}" in str(caught.value)


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


def test_a_dirty_lock_does_not_block_the_run(tree) -> None:
    """The lock is written but not guarded: `uv lock` derives it from the manifests, so a
    dirty one is work this run redoes rather than destroys -- and guarding it would make
    the planner's own sequence impossible, since releasing two members in one pull request
    means the second bump always meets the lock the first left dirty. The pathspec the
    check is asked with is what encodes that."""
    fake = FakeRunner()
    code, _ = run(
        tree(), "acme-plugin", "--to", "0.2.0", "--date", "2026-09-06", runner=fake
    )
    assert code == 0
    assert "uv.lock" not in fake.calls[0]
    assert "packages/acme-plugin/pyproject.toml" in fake.calls[0]


def test_the_dry_run_writes_nothing_and_locks_nothing(tree, capsys) -> None:
    root = tree()
    before = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
    fake = FakeRunner({"uv version": "acme-core 1.2.3 => 1.3.0\n"})
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
    """`uv version --no-sync` (which leaves the lock stale), then the dependants' floors,
    then `uv lock` -- and the cleanliness check before any of them."""
    root = tree()
    fake = FakeRunner()
    code, _ = run(
        root, "acme-core", "--bump", "minor", "--date", "2026-09-06", runner=fake
    )
    assert code == 0
    assert [call[:2] for call in fake.calls] == [
        ["git", "status"],
        ["uv", "version"],
        [fake.calls[2][0], fake.calls[2][1]],  # <interpreter> propagate_floors.py
        ["uv", "lock"],
        ["git", "tag"],
    ]
    assert fake.calls[1] == [
        "uv",
        "version",
        "--package",
        "acme-core",
        "--bump",
        "minor",
        "--no-sync",
    ]
    assert fake.calls[2][1].endswith("propagate_floors.py")
    assert fake.calls[2][2] == "acme-core"


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
        runner=writing_runner(manifest, "1.2.3", "1.3.0"),
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
        runner=writing_runner(
            root / "packages" / "sphinx-needs" / "pyproject.toml", "8.5.0", "8.6.0"
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


def test_a_member_with_no_dependants_skips_propagate_floors(tree, capsys) -> None:
    fake = FakeRunner()
    code, _ = run(
        tree(), "acme-plugin", "--to", "0.2.0", "--date", "2026-09-06", runner=fake
    )
    assert code == 0
    assert not any("propagate_floors" in " ".join(call) for call in fake.calls)
    assert "no dependants" in capsys.readouterr().out
    assert fake.calls[1] == [
        "uv",
        "version",
        "--package",
        "acme-plugin",
        "0.2.0",
        "--no-sync",
    ]
