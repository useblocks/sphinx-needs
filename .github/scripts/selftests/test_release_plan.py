"""`release_plan.py`: the five fail-closed checks, the rehearsal, and `previous_tag`.

PyPI and git are monkeypatched here -- `on_pypi`, `list_tags` and `is_ancestor` are the
three functions that touch the outside world, and they are separate functions so that this
file can run offline. The one thing that must never be mocked away is the *direction* of a
failure: every check has to fail closed, so each test asserts the exit code as well as the
message.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import release_plan

pytestmark = pytest.mark.filterwarnings("error")


@pytest.fixture
def offline(monkeypatch):
    """No network, no git, unless a test says otherwise."""
    monkeypatch.setattr(release_plan, "list_tags", lambda: [])
    monkeypatch.setattr(release_plan, "is_ancestor", lambda commit, branch: True)
    return monkeypatch


def published(monkeypatch, mapping: dict[tuple[str, str], bool]) -> None:
    def fake(name: str, version: str) -> bool:
        return mapping[(name, version)]

    monkeypatch.setattr(release_plan, "on_pypi", fake)


def run(root: Path, *args: str) -> int:
    return release_plan.main([*args, "--root", str(root)])


# --- the order ---------------------------------------------------------------------------


def test_prints_the_topological_order(workspace, capsys) -> None:
    root = workspace(
        {
            "acme-core": {"version": "2.0.0"},
            "acme-ext": {"version": "0.1.0", "dependencies": ["acme-core>=2.0.0,<3"]},
            "acme-other": {"version": "0.3.0", "dependencies": ["acme-core>=2.0.0,<3"]},
        }
    )
    assert run(root) == 0
    out = capsys.readouterr().out
    assert "1. acme-core 2.0.0   depends on: -" in out
    assert "2. acme-ext 0.1.0   depends on: acme-core" in out
    assert "3. acme-other 0.3.0   depends on: acme-core" in out


def test_a_cycle_is_an_error(workspace, capsys) -> None:
    root = workspace(
        {
            "acme-a": {"version": "1.0.0", "dependencies": ["acme-b>=1.0.0,<2"]},
            "acme-b": {"version": "1.0.0", "dependencies": ["acme-a>=1.0.0,<2"]},
        }
    )
    assert run(root) == 1
    assert "cycle among workspace members: acme-a, acme-b" in capsys.readouterr().out


# --- (1) the tag names a member ----------------------------------------------------------


@pytest.mark.parametrize(
    "tag", ["bogus-v1.0.0", "acme-core-1.0.0", "v1.0.0", "1.0.0", "sphinx-needs-v1.0.0"]
)
def test_a_tag_that_names_no_member(workspace, capsys, offline, tag: str) -> None:
    root = workspace({"acme-core": {"version": "1.0.0"}})
    assert run(root, "--tag", tag) == 1
    out = capsys.readouterr().out
    assert f"tag `{tag}` does not name a member of this workspace" in out


def test_the_longest_member_name_wins(workspace, capsys, offline) -> None:
    """A member whose name is a prefix of another's must not swallow its tag."""
    published(offline, {("acme-core-extra", "1.0.0"): False})
    root = workspace(
        {"acme-core": {"version": "9.9.9"}, "acme-core-extra": {"version": "1.0.0"}}
    )
    assert run(root, "--tag", "acme-core-extra-v1.0.0") == 0
    assert '"dist": "acme-core-extra"' in capsys.readouterr().out


# --- (2) the tag's version is the tree's -------------------------------------------------


@pytest.mark.parametrize(
    ("tag", "said"),
    [
        ("acme-core-v2.0.0", "2.0.0"),
        # the tag filter would not match this one, but the fence does not rely on that
        ("acme-core-vv1.0.0", "v1.0.0"),
    ],
)
def test_version_mismatch(workspace, capsys, offline, tag: str, said: str) -> None:
    root = workspace({"acme-core": {"version": "1.0.0"}})
    assert run(root, "--tag", tag) == 1
    out = capsys.readouterr().out
    assert f"says acme-core {said}, but this tree builds 1.0.0" in out


# --- (3) not already published -----------------------------------------------------------


def test_already_published_is_fatal(workspace, capsys, offline) -> None:
    published(offline, {("acme-core", "1.0.0"): True})
    root = workspace({"acme-core": {"version": "1.0.0"}})
    assert run(root, "--tag", "acme-core-v1.0.0") == 1
    assert "is already on PyPI" in capsys.readouterr().out


def test_rehearsal_downgrades_exactly_that_check(workspace, capsys, offline) -> None:
    published(offline, {("acme-core", "1.0.0"): True})
    root = workspace({"acme-core": {"version": "1.0.0"}})
    assert run(root, "--tag", "acme-core-v1.0.0", "--rehearsal") == 0
    out = capsys.readouterr().out
    assert "::notice::acme-core 1.0.0 is already on PyPI" in out
    assert "publishes nothing" in out
    assert "::error" not in out


@pytest.mark.parametrize(
    ("tag", "members"),
    [
        ("bogus-v1.0.0", {"acme-core": {"version": "1.0.0"}}),
        ("acme-core-v2.0.0", {"acme-core": {"version": "1.0.0"}}),
    ],
)
def test_rehearsal_leaves_the_other_checks_fatal(
    workspace, capsys, offline, tag: str, members: dict
) -> None:
    published(offline, {("acme-core", "1.0.0"): False})
    root = workspace(members)
    assert run(root, "--tag", tag, "--rehearsal") == 1
    assert "::error" in capsys.readouterr().out


# --- (4) the release order ---------------------------------------------------------------


def test_dependency_not_yet_released(workspace, capsys, offline) -> None:
    published(offline, {("acme-ext", "0.1.0"): False, ("acme-core", "2.0.0"): False})
    root = workspace(
        {
            "acme-core": {"version": "2.0.0"},
            "acme-ext": {"version": "0.1.0", "dependencies": ["acme-core>=2.0.0,<3"]},
        }
    )
    assert run(root, "--tag", "acme-ext-v0.1.0") == 1
    out = capsys.readouterr().out
    assert "acme-ext depends on acme-core, and this tree builds acme-core 2.0.0" in out
    assert "the order is acme-core -> acme-ext (acme-core is #1)" in out


def test_dependency_released_is_green(workspace, capsys, offline) -> None:
    published(offline, {("acme-ext", "0.1.0"): False, ("acme-core", "2.0.0"): True})
    root = workspace(
        {
            "acme-core": {"version": "2.0.0"},
            "acme-ext": {"version": "0.1.0", "dependencies": ["acme-core>=2.0.0,<3"]},
        }
    )
    assert run(root, "--tag", "acme-ext-v0.1.0") == 0
    out = capsys.readouterr().out
    assert "OK    acme-core 2.0.0 is on PyPI" in out
    assert '"dist": "acme-ext", "version": "0.1.0"' in out


def test_rehearsal_still_fails_on_an_unreleased_dependency(
    workspace, capsys, offline
) -> None:
    published(offline, {("acme-ext", "0.1.0"): True, ("acme-core", "2.0.0"): False})
    root = workspace(
        {
            "acme-core": {"version": "2.0.0"},
            "acme-ext": {"version": "0.1.0", "dependencies": ["acme-core>=2.0.0,<3"]},
        }
    )
    assert run(root, "--tag", "acme-ext-v0.1.0", "--rehearsal") == 1
    assert "which is NOT on PyPI" in capsys.readouterr().out


# --- PyPI must never guess ----------------------------------------------------------------


@pytest.mark.parametrize("status", [403, 500, 503])
def test_a_non_404_pypi_answer_is_fatal(
    workspace, capsys, offline, status: int
) -> None:
    """Fail closed: anything but a clean 404 must stop the release, never pass it."""
    import urllib.error

    def raising(url: str, timeout: int = 30):
        raise urllib.error.HTTPError(url, status, "boom", None, None)  # ty: ignore[invalid-argument-type]

    offline.setattr(release_plan.urllib.request, "urlopen", raising)
    root = workspace({"acme-core": {"version": "1.0.0"}})
    assert run(root, "--tag", "acme-core-v1.0.0") == 1
    out = capsys.readouterr().out
    assert f"PyPI returned {status}" in out
    assert "refusing to guess" in out


def test_an_unreachable_pypi_is_fatal(workspace, capsys, offline) -> None:
    import urllib.error

    def raising(url: str, timeout: int = 30):
        raise urllib.error.URLError("no route to host")

    offline.setattr(release_plan.urllib.request, "urlopen", raising)
    root = workspace({"acme-core": {"version": "1.0.0"}})
    assert run(root, "--tag", "acme-core-v1.0.0") == 1
    out = capsys.readouterr().out
    assert "cannot reach PyPI" in out
    assert "refusing to guess" in out


def test_a_404_means_not_published(monkeypatch) -> None:
    import urllib.error

    def raising(url: str, timeout: int = 30):
        raise urllib.error.HTTPError(url, 404, "nope", None, None)  # ty: ignore[invalid-argument-type]

    monkeypatch.setattr(release_plan.urllib.request, "urlopen", raising)
    assert release_plan.on_pypi("acme-core", "1.0.0") is False


# --- (5) the tagged commit is on the default branch --------------------------------------


def test_a_tag_off_the_default_branch(workspace, capsys, offline) -> None:
    published(offline, {("acme-core", "1.0.0"): False})
    offline.setattr(release_plan, "is_ancestor", lambda commit, branch: False)
    root = workspace({"acme-core": {"version": "1.0.0"}})
    assert run(root, "--tag", "acme-core-v1.0.0") == 1
    out = capsys.readouterr().out
    assert "is not an ancestor of origin/master" in out
    assert "Merge first, then tag the merged commit" in out


@pytest.mark.parametrize(
    ("on_branch", "expected"),
    [(True, "HEAD is an ancestor of"), (False, "HEAD is NOT an ancestor of")],
)
def test_the_ancestry_check_is_reported_but_not_fatal_in_a_rehearsal(
    workspace, capsys, offline, on_branch: bool, expected: str
) -> None:
    """A rehearsal must still RUN it: otherwise `git merge-base` -- and the checkout depth
    it needs -- would first execute on a real tag."""
    published(offline, {("acme-core", "1.0.0"): False})
    offline.setattr(release_plan, "is_ancestor", lambda commit, branch: on_branch)
    root = workspace({"acme-core": {"version": "1.0.0"}})
    assert run(root, "--tag", "acme-core-v1.0.0", "--rehearsal") == 0
    out = capsys.readouterr().out
    assert f"::notice::{expected} origin/master" in out
    assert "informational" in out
    assert "::error" not in out


def test_a_git_failure_is_fatal_even_in_a_rehearsal(workspace, capsys, offline) -> None:
    """The verdict is downgraded in a rehearsal; an unusable answer is not."""
    published(offline, {("acme-core", "1.0.0"): False})

    def raising(commit: str, branch: str) -> bool:
        raise release_plan.PlanError("no such ref origin/master")

    offline.setattr(release_plan, "is_ancestor", raising)
    root = workspace({"acme-core": {"version": "1.0.0"}})
    assert run(root, "--tag", "acme-core-v1.0.0", "--rehearsal") == 1
    assert "::error::no such ref origin/master" in capsys.readouterr().out


def test_no_git_skips_the_ancestry_check(workspace, offline) -> None:
    published(offline, {("acme-core", "1.0.0"): False})

    def explode(commit: str, branch: str) -> bool:
        raise AssertionError("--no-git must not ask git anything")

    offline.setattr(release_plan, "is_ancestor", explode)
    root = workspace({"acme-core": {"version": "1.0.0"}})
    assert run(root, "--tag", "acme-core-v1.0.0", "--no-git") == 0


def test_an_unusable_git_answer_is_fatal(monkeypatch, workspace, capsys) -> None:
    """`git merge-base` exiting 128 (no such ref) must stop, not pass."""
    import subprocess

    class Fake:
        returncode = 128
        stderr = "fatal: Not a valid object name origin/master"

    monkeypatch.setattr(release_plan, "list_tags", lambda: [])
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: Fake())
    published(monkeypatch, {("acme-core", "1.0.0"): False})
    root = workspace({"acme-core": {"version": "1.0.0"}})
    assert run(root, "--tag", "acme-core-v1.0.0") == 1
    out = capsys.readouterr().out
    assert "refusing to guess whether the commit is on origin/master" in out
    assert "fetch-depth: 0" in out


# --- previous_tag -------------------------------------------------------------------------


TAGS = [
    "8.4.0",
    "8.5.0",
    "7.0.0",
    "v.1.4",  # not PEP 440
    "depbatch-backup-f8556477",  # not a release tag at all
    "sphinx-needs-v8.6.0",
    "sphinx-needs-v8.7.0",
    "sphinx-mounts-v0.3.0",
    "sphinx-mounts-v0.4.0",
]


@pytest.mark.parametrize(
    ("dist", "version", "expected"),
    [
        # sphinx-needs owns the bare namespace as well as its own prefix
        ("sphinx-needs", "8.5.1", "8.5.0"),
        ("sphinx-needs", "8.7.0", "sphinx-needs-v8.6.0"),
        ("sphinx-needs", "8.8.0", "sphinx-needs-v8.7.0"),
        ("sphinx-needs", "9.0.0", "sphinx-needs-v8.7.0"),
        # the first ever release of a package has no predecessor
        ("sphinx-needs", "1.0.0", ""),
        # an extension sees only its own prefix -- the bare tags are not its releases
        ("sphinx-mounts", "0.5.0", "sphinx-mounts-v0.4.0"),
        ("sphinx-mounts", "0.3.0", ""),
        ("sphinx-codelinks", "1.0.0", ""),
    ],
)
def test_previous_tag(dist: str, version: str, expected: str) -> None:
    assert release_plan.previous_tag(dist, version, TAGS) == expected


def test_previous_tag_is_reported_and_written_to_github_output(
    workspace, capsys, offline, tmp_path: Path
) -> None:
    published(offline, {("sphinx-needs", "8.6.0"): False})
    offline.setattr(release_plan, "list_tags", lambda: TAGS)
    output = tmp_path / "gh-output"
    offline.setenv("GITHUB_OUTPUT", str(output))
    root = workspace({"sphinx-needs": {"version": "8.6.0"}})
    assert run(root, "--tag", "sphinx-needs-v8.6.0", "--github-output") == 0
    assert "OK    previous release tag: 8.5.0" in capsys.readouterr().out
    assert output.read_text() == (
        "dist=sphinx-needs\nversion=8.6.0\nprevious_tag=8.5.0\n"
    )


def test_github_output_without_the_variable_is_fatal(
    workspace, capsys, offline
) -> None:
    """The one flag that could fail OPEN: asked for, did nothing, exit 0."""
    published(offline, {("acme-core", "1.0.0"): False})
    offline.delenv("GITHUB_OUTPUT", raising=False)
    root = workspace({"acme-core": {"version": "1.0.0"}})
    assert run(root, "--tag", "acme-core-v1.0.0", "--github-output") == 1
    assert "--github-output was asked for but GITHUB_OUTPUT is not set" in (
        capsys.readouterr().out
    )


def test_no_previous_tag_is_reported_as_such(workspace, capsys, offline) -> None:
    published(offline, {("acme-core", "1.0.0"): False})
    root = workspace({"acme-core": {"version": "1.0.0"}})
    assert run(root, "--tag", "acme-core-v1.0.0") == 0
    out = capsys.readouterr().out
    assert "previous release tag: (none -- this is the first)" in out
    assert '"previous_tag": ""' in out


def test_a_dynamic_member_version_stops_the_plan(workspace, capsys, offline) -> None:
    root = workspace({"acme-core": {"version": None}})
    assert run(root, "--tag", "acme-core-v1.0.0") == 1
    assert "has a dynamic version" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("manifest", "expected"),
    [
        ("[tool.poe]\nx = 1\n", "no [project] table -- is this a package?"),
        ('[project]\nversion = "1.0.0"\n', "[project] declares no `name`"),
    ],
)
def test_a_manifest_the_plan_cannot_read_is_annotated_not_a_traceback(
    workspace, capsys, offline, manifest: str, expected: str
) -> None:
    """`plan` is job one, so a broken manifest reaches it before it reaches the fence in
    `build` -- it has to name the file, not print a traceback."""
    root = workspace({"acme-core": {"version": "1.0.0"}})
    (root / "packages/acme-core/pyproject.toml").write_text(manifest, encoding="utf-8")
    assert run(root, "--tag", "acme-core-v1.0.0") == 1
    out = capsys.readouterr().out
    assert "::error::" in out
    assert expected in out
    assert "Traceback" not in out


def test_a_member_with_no_version_is_annotated_not_a_traceback(
    workspace, capsys, offline
) -> None:
    """Neither dynamic nor declared: the commonest PEP 621 mistake. It used to KeyError."""
    root = workspace({"acme-core": {"version": "1.0.0"}})
    (root / "packages/acme-core/pyproject.toml").write_text(
        '[project]\nname = "acme-core"\nrequires-python = ">=3.11,<4"\n',
        encoding="utf-8",
    )
    assert run(root, "--tag", "acme-core-v1.0.0") == 1
    out = capsys.readouterr().out
    assert "::error::" in out
    assert "acme-core declares no [project] version" in out
    assert "Traceback" not in out
