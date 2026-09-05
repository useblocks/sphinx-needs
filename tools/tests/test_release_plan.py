"""`release_plan.py`: the five fail-closed checks, the rehearsal, and the planner.

PyPI and git are monkeypatched here -- every function that touches the outside world
(`on_pypi`, `published_versions`, `list_tags`, `is_ancestor`, `commits_since`,
`touched_files`, `head_context`, `resolve`) is a separate function for exactly that reason,
so this file runs offline. It matters more for the planner than for the tag checks: git
answers about the working directory, which in these tests is this repository rather than
the scratch workspace under `tmp_path`, so an un-mocked seam would make a test agree with
whatever the branch happens to look like today.

The one thing that must never be mocked away is the *direction* of an answer. The tag
checks fail closed, so each of those tests asserts the exit code as well as the message;
the planner is advice and must never gate, so its tests assert exit 0 as hard as they
assert the words.
"""

from __future__ import annotations

import io
import subprocess
from pathlib import Path

import pytest
from packaging.version import Version
from sn_tools import release_plan

pytestmark = pytest.mark.filterwarnings("error")


@pytest.fixture
def offline(monkeypatch):
    """No network, no git, unless a test says otherwise."""
    monkeypatch.setattr(release_plan, "list_tags", lambda cwd=None: [])
    monkeypatch.setattr(
        release_plan, "is_ancestor", lambda commit, branch, cwd=None: True
    )
    # the planner's seams. A plain `run(root)` reaches all of them, so the defaults are
    # "PyPI has nothing, git has nothing, HEAD is on origin/master" -- a workspace whose
    # every member is unreleased, which each planner test then overrides. Every git seam
    # takes `cwd`, because the planner passes `--root` to git as well as to the manifests
    monkeypatch.setattr(release_plan, "published_versions", lambda name: {})
    monkeypatch.setattr(release_plan, "commits_since", lambda ref, paths, cwd=None: [])
    monkeypatch.setattr(release_plan, "touched_files", lambda ref, paths, cwd=None: {})
    monkeypatch.setattr(
        release_plan, "head_context", lambda cwd=None: ("abc1234", "master")
    )
    monkeypatch.setattr(release_plan, "resolve", lambda ref, cwd=None: "abc1234")
    return monkeypatch


def published(monkeypatch, mapping: dict[tuple[str, str], bool]) -> None:
    def fake(name: str, version: str) -> bool:
        return mapping[(name, version)]

    monkeypatch.setattr(release_plan, "on_pypi", fake)


def pypi(monkeypatch, mapping: dict[str, dict[str, bool]]) -> None:
    """`published_versions` per distribution: {version: is the whole release yanked}."""

    def fake(name: str) -> dict[Version, bool]:
        return {Version(raw): yanked for raw, yanked in mapping.get(name, {}).items()}

    monkeypatch.setattr(release_plan, "published_versions", fake)


def history(monkeypatch, per_member: dict[str, list[tuple[str, str]]]) -> None:
    """`commits_since`, keyed by the member whose shipped paths were asked about.

    The scratch workspaces put every member at `packages/<name>`, so the second segment of
    the path filter names the member -- which is also a small assertion that the planner
    asked about the paths it said it would.
    """

    def fake(
        ref: str, paths: list[str], cwd: Path | None = None
    ) -> list[tuple[str, str]]:
        return per_member.get(paths[0].split("/")[1], [])

    monkeypatch.setattr(release_plan, "commits_since", fake)


def pypi_pair(monkeypatch, mapping: dict[str, dict[str, bool]]) -> None:
    """BOTH PyPI seams from ONE fact table.

    `published_versions` (the planner) reads the whole-project document; `on_pypi` (the tag
    mode's check 4) reads the per-version URL, which answers 200 for a YANKED release too.
    Driving them from one table is what lets a test run both modes over the same index and
    assert the planner predicted what the tag mode then did -- the divergence this pairing
    exists to catch.
    """
    pypi(monkeypatch, mapping)

    def fake(name: str, version: str) -> bool:
        return Version(version) in {Version(raw) for raw in mapping.get(name, {})}

    monkeypatch.setattr(release_plan, "on_pypi", fake)


def git_in(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=root, text=True, capture_output=True, check=True
    )
    return proc.stdout.strip()


@pytest.fixture
def git_workspace(workspace):
    """A scratch workspace that is also a REAL git repository.

    The planner's whole subject is what git says, and `--root` has to reach git as well as
    the manifests -- neither of which a monkeypatched seam can prove. Everything in the
    tests that use this is real except PyPI.
    """

    def build(members: dict, **kwargs) -> Path:
        root = workspace(members, **kwargs)
        git_in(root, "init", "-q", "-b", "main")
        git_in(root, "config", "user.email", "scratch@example.invalid")
        git_in(root, "config", "user.name", "Scratch")
        git_in(root, "config", "commit.gpgsign", "false")
        return root

    return build


def commit(root: Path, message: str, files: dict[str, str]) -> str:
    """Write files, commit them, and return the short sha the planner would print."""
    for name, body in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    git_in(root, "add", "-A")
    git_in(root, "commit", "-q", "-m", message)
    return git_in(root, "rev-parse", "--short", "HEAD")


def run(root: Path, *args: str) -> int:
    return release_plan.main([*args, "--root", str(root)])


# --- the order ---------------------------------------------------------------------------


def test_prints_the_topological_order(workspace, capsys, offline) -> None:
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


# --- (0) a virtual member is never a release ---------------------------------------------


def test_a_virtual_member_is_listed_but_not_numbered(
    workspace, capsys, offline
) -> None:
    root = workspace(
        {
            "acme-core": {"version": "2.0.0"},
            "acme-tools": {"version": "0", "virtual": True},
        }
    )
    assert run(root) == 0
    out = capsys.readouterr().out
    assert "1. acme-core 2.0.0   depends on: -" in out
    assert "-- acme-tools 0   (virtual -- never published)" in out
    assert "2. acme-tools" not in out


def test_a_tag_naming_a_virtual_member_is_refused(workspace, capsys, offline) -> None:
    root = workspace(
        {
            "acme-core": {"version": "2.0.0"},
            "acme-tools": {"version": "0", "virtual": True},
        }
    )
    assert run(root, "--tag", "acme-tools-v0", "--rehearsal", "--no-git") == 1
    out = capsys.readouterr().out
    assert "`acme-tools` is a virtual member (`[tool.uv] package = false`)" in out
    assert "there is nothing to release" in out


def test_a_runtime_dependency_on_a_virtual_member_is_refused(
    workspace, capsys, offline
) -> None:
    """The wheel would name a distribution that is never on PyPI."""
    published(offline, {("acme-core", "2.0.0"): False})
    root = workspace(
        {
            "acme-core": {"version": "2.0.0", "dependencies": ["acme-tools>=0"]},
            "acme-tools": {"version": "0", "virtual": True},
        }
    )
    assert run(root, "--tag", "acme-core-v2.0.0", "--rehearsal", "--no-git") == 1
    out = capsys.readouterr().out
    assert "acme-core declares a runtime (or extra) dependency on acme-tools" in out
    assert "`acme-tools` is never on PyPI" in out


def test_an_extra_only_edge_to_a_virtual_member_is_refused(
    workspace, capsys, offline
) -> None:
    """`edges()` folds extras into the graph, so the message must not say "runtime" flatly."""
    published(offline, {("acme-core", "2.0.0"): False})
    root = workspace(
        {
            "acme-core": {
                "version": "2.0.0",
                "optional_dependencies": {"dev": ["acme-tools>=0"]},
            },
            "acme-tools": {"version": "0", "virtual": True},
        }
    )
    assert run(root, "--tag", "acme-core-v2.0.0", "--rehearsal", "--no-git") == 1
    assert "runtime (or extra) dependency" in capsys.readouterr().out


def test_a_virtual_to_virtual_edge_does_not_block_a_release(
    workspace, capsys, offline
) -> None:
    """The refusal is about a wheel naming something never on PyPI; a virtual dependant
    ships no wheel, so its edge onto a virtual sibling is nobody's problem."""
    published(offline, {("acme-core", "2.0.0"): False})
    root = workspace(
        {
            "acme-core": {"version": "2.0.0"},
            "acme-tools": {
                "version": "0",
                "virtual": True,
                "dependencies": ["acme-more>=0"],
            },
            "acme-more": {"version": "0", "virtual": True},
        }
    )
    assert run(root, "--tag", "acme-core-v2.0.0", "--rehearsal", "--no-git") == 0
    out = capsys.readouterr().out
    assert "-- acme-more 0   (virtual -- never published)" in out
    assert "-- acme-tools 0   (virtual -- never published)" in out
    assert "::error" not in out


def test_pypi_is_never_asked_about_a_virtual_member(workspace, offline) -> None:
    """Check 4 must not turn a virtual dependency into a 404 lookup."""
    asked: list[str] = []

    def fake(name: str, version: str) -> bool:
        asked.append(name)
        return False

    offline.setattr(release_plan, "on_pypi", fake)
    root = workspace(
        {
            "acme-core": {"version": "2.0.0", "dependencies": ["acme-tools>=0"]},
            "acme-tools": {"version": "0", "virtual": True},
        }
    )
    assert run(root, "--tag", "acme-core-v2.0.0", "--rehearsal", "--no-git") == 1
    # check 3 asked about the release candidate; check 4 refused the virtual edge before
    # it could turn it into a lookup that is guaranteed to 404
    assert asked == ["acme-core"]


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

    monkeypatch.setattr(release_plan, "list_tags", lambda cwd=None: [])
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


# --- the planner: what to release, in what order, tested against what ---------------------
# Everything below runs with no `--tag`. The planner is ADVICE: every one of these asserts
# exit 0 unless the data itself could not be gathered.


def test_up_to_date_says_nothing_to_release(workspace, capsys, offline) -> None:
    pypi(offline, {"acme-core": {"2.0.0": False}})
    offline.setattr(release_plan, "list_tags", lambda cwd=None: ["acme-core-v2.0.0"])
    root = workspace({"acme-core": {"version": "2.0.0"}})
    assert run(root) == 0
    out = capsys.readouterr().out
    assert "up to date, nothing to release: 2.0.0 is on PyPI" in out
    assert "no commit since acme-core-v2.0.0 touched its shipped code" in out
    assert "nothing to release: every member is up to date" in out


def test_unreleased_commits_on_a_published_version_ask_for_a_bump(
    workspace, capsys, offline
) -> None:
    pypi(offline, {"acme-core": {"2.0.0": False}})
    offline.setattr(release_plan, "list_tags", lambda cwd=None: ["acme-core-v2.0.0"])
    history(offline, {"acme-core": [("aaa1111", "a fix"), ("bbb2222", "another")]})
    root = workspace({"acme-core": {"version": "2.0.0"}})
    assert run(root) == 0
    out = capsys.readouterr().out
    assert "2 unreleased commits since acme-core-v2.0.0" in out
    assert "2.0.0 is already published -- bump before tagging" in out
    assert "uv version --package acme-core --bump {patch|minor|major} --no-sync" in out
    assert "aaa1111  a fix" in out
    assert "bbb2222  another" in out


def test_a_declared_version_that_is_not_published_is_ready_to_tag(
    workspace, capsys, offline
) -> None:
    pypi(offline, {"acme-core": {"1.9.0": False}})
    offline.setattr(release_plan, "list_tags", lambda cwd=None: ["acme-core-v1.9.0"])
    history(offline, {"acme-core": [("aaa1111", "the feature")]})
    root = workspace({"acme-core": {"version": "2.0.0"}})
    assert run(root) == 0
    out = capsys.readouterr().out
    assert "release pending: 2.0.0 is not on PyPI, and this tree builds it" in out
    assert "git tag acme-core-v2.0.0 && git push origin acme-core-v2.0.0" in out
    assert "rehearse first: gh workflow run release.yaml -f tag=acme-core-v2.0.0" in out
    assert "1 commit since acme-core-v1.9.0 touched its shipped code" in out


def test_a_tag_whose_release_never_completed_says_so(
    workspace, capsys, offline
) -> None:
    """The tag exists, PyPI does not have it: re-run the workflow, do not re-tag."""
    pypi(offline, {"acme-core": {"1.9.0": False}})
    offline.setattr(
        release_plan,
        "list_tags",
        lambda cwd=None: ["acme-core-v1.9.0", "acme-core-v2.0.0"],
    )
    root = workspace({"acme-core": {"version": "2.0.0"}})
    assert run(root) == 0
    out = capsys.readouterr().out
    assert "the tag acme-core-v2.0.0 exists but PyPI has no 2.0.0" in out
    assert "re-run the workflow from the tag, do not re-tag" in out


def test_a_tree_behind_pypi_is_reported_and_still_exits_zero(
    workspace, capsys, offline
) -> None:
    pypi(offline, {"acme-core": {"1.0.0": False, "2.0.0": False}})
    root = workspace({"acme-core": {"version": "1.0.0"}})
    assert run(root) == 0
    out = capsys.readouterr().out
    assert "this tree is BEHIND PyPI (1.0.0 vs 2.0.0) -- an old branch?" in out
    assert "::error" not in out
    assert "behind PyPI, so nothing to release from this tree: acme-core" in out


def test_a_yanked_release_is_not_the_latest(workspace, capsys, offline) -> None:
    """A yanked 3.0.0 must not make a 2.0.0 tree look BEHIND: it cannot be installed."""
    pypi(offline, {"acme-core": {"2.0.0": False, "3.0.0": True}})
    offline.setattr(release_plan, "list_tags", lambda cwd=None: ["acme-core-v2.0.0"])
    root = workspace({"acme-core": {"version": "2.0.0"}})
    assert run(root) == 0
    out = capsys.readouterr().out
    assert "2 versions, latest 2.0.0, 1 yanked" in out
    assert "up to date, nothing to release" in out
    assert "BEHIND PyPI" not in out


def test_a_project_pypi_has_never_heard_of_is_not_an_error(
    workspace, capsys, offline
) -> None:
    """A whole-project 404 is a first release, not a failure."""
    root = workspace({"acme-core": {"version": "0.1.0"}})
    assert run(root) == 0
    out = capsys.readouterr().out
    assert "on PyPI            nothing -- acme-core has never been published" in out
    assert "release pending: 0.1.0 is not on PyPI" in out
    assert "::error" not in out


def test_a_404_for_the_whole_project_is_an_empty_answer(monkeypatch) -> None:
    import urllib.error

    def raising(url: str, timeout: int = 30):
        raise urllib.error.HTTPError(url, 404, "nope", None, None)  # ty: ignore[invalid-argument-type]

    monkeypatch.setattr(release_plan.urllib.request, "urlopen", raising)
    assert release_plan.published_versions("acme-core") == {}


@pytest.mark.parametrize("status", [403, 500, 503])
def test_a_non_404_pypi_answer_stops_the_planner(
    workspace, capsys, offline, status: int
) -> None:
    """The planner never gates -- but it also never advises on a guess."""
    import urllib.error

    def raising(url: str, timeout: int = 30):
        raise urllib.error.HTTPError(url, status, "boom", None, None)  # ty: ignore[invalid-argument-type]

    offline.undo()
    offline.setattr(release_plan, "list_tags", lambda cwd=None: [])
    offline.setattr(release_plan, "commits_since", lambda ref, paths, cwd=None: [])
    offline.setattr(
        release_plan, "head_context", lambda cwd=None: ("abc1234", "master")
    )
    offline.setattr(release_plan, "resolve", lambda ref, cwd=None: None)
    offline.setattr(release_plan.urllib.request, "urlopen", raising)
    root = workspace({"acme-core": {"version": "1.0.0"}})
    assert run(root) == 1
    out = capsys.readouterr().out
    assert f"PyPI returned {status}" in out
    assert "refusing to advise on a guess about what acme-core has published" in out


def test_a_git_failure_stops_the_planner(workspace, capsys, offline) -> None:
    def raising(
        ref: str, paths: list[str], cwd: Path | None = None
    ) -> list[tuple[str, str]]:
        raise release_plan.PlanError("`git log` failed (128): not a git repository")

    offline.setattr(release_plan, "commits_since", raising)
    root = workspace({"acme-core": {"version": "1.0.0"}})
    assert run(root) == 1
    assert "::error::`git log` failed (128)" in capsys.readouterr().out


def test_no_git_is_refused_in_planner_mode(workspace, capsys, offline) -> None:
    """The planner IS git reasoning; --no-git would empty the answer, not skip a check."""
    root = workspace({"acme-core": {"version": "1.0.0"}})
    assert run(root, "--no-git") == 1
    out = capsys.readouterr().out
    assert "--no-git makes no sense without --tag" in out
    assert "since each member's last release tag" in out


def test_the_context_header_names_head_and_the_branch(
    workspace, capsys, offline
) -> None:
    offline.setattr(
        release_plan, "head_context", lambda cwd=None: ("deadbee", "detached")
    )
    offline.setattr(release_plan, "is_ancestor", lambda commit, branch, cwd=None: False)
    root = workspace({"acme-core": {"version": "1.0.0"}})
    assert run(root) == 0
    out = capsys.readouterr().out
    assert "HEAD deadbee (detached)" in out
    assert "HEAD is not on origin/master -- releases are cut from master" in out
    assert "<member>/src and <member>/pyproject.toml" in out


def test_an_absent_origin_master_is_reported_not_fatal(
    workspace, capsys, offline
) -> None:
    def explode(commit: str, branch: str, cwd: Path | None = None) -> bool:
        raise AssertionError(
            "is_ancestor must not be asked about a ref that is not there"
        )

    offline.setattr(release_plan, "resolve", lambda ref, cwd=None: None)
    offline.setattr(release_plan, "is_ancestor", explode)
    root = workspace({"acme-core": {"version": "1.0.0"}})
    assert run(root) == 0
    assert "origin/master not found (no fetch?): ancestry not checked" in (
        capsys.readouterr().out
    )


# --- the planner: dependant advice --------------------------------------------------------


DIAMOND = {
    "acme-core": {"version": "2.0.0"},
    "acme-ext": {"version": "0.1.0", "dependencies": ["acme-core>=2.0.0,<3"]},
}


def test_the_plan_job_would_refuse_the_dependant_is_said_in_advance(
    workspace, capsys, offline
) -> None:
    """Check (4) of the tag mode, six minutes and one red job earlier."""
    pypi(offline, {"acme-core": {"1.9.0": False}})
    root = workspace(DIAMOND)
    assert run(root) == 0
    out = capsys.readouterr().out
    # the manifest's own text, not `packaging`'s sorted rendering of it
    assert "acme-ext 0.1.0 needs acme-core>=2.0.0,<3" in out
    assert (
        "the plan job WILL refuse `acme-ext-v0.1.0`: check 4 needs acme-core 2.0.0 on "
        "PyPI, and PyPI has 1.9.0 as its newest live version -- release acme-core first"
        in out
    )


def test_advice_never_gates(workspace, capsys, offline) -> None:
    """ "release acme-core first" is the strongest thing the planner says, and it exits 0."""
    pypi(offline, {"acme-core": {"1.9.0": False}})
    root = workspace(DIAMOND)
    assert run(root) == 0
    out = capsys.readouterr().out
    assert "release acme-core first" in out
    assert "::error" not in out


def test_a_dependant_with_nothing_published_names_that_too(
    workspace, capsys, offline
) -> None:
    root = workspace(DIAMOND)
    assert run(root) == 0
    assert (
        "check 4 needs acme-core 2.0.0 on PyPI, and PyPI has nothing"
        in capsys.readouterr().out
    )


def test_the_compat_cell_target_and_what_it_lacks(workspace, capsys, offline) -> None:
    pypi(offline, {"acme-core": {"2.0.0": False}, "acme-ext": {"0.1.0": False}})
    offline.setattr(release_plan, "list_tags", lambda cwd=None: ["acme-core-v2.0.0"])
    history(offline, {"acme-core": [("aaa1111", "a core fix"), ("bbb2222", "another")]})
    root = workspace(DIAMOND)
    assert run(root) == 0
    out = capsys.readouterr().out
    assert (
        "the compat cell installs acme-core from PyPI: `acme-ext-v0.1.0` would be tested "
        "against acme-core 2.0.0, which lacks acme-core's 2 commits since acme-core-v2.0.0"
        in out
    )
    assert (
        "`uv run python tools/src/sn_tools/import_check.py acme-ext` installs the "
        "PUBLISHED acme-core and imports every acme-ext module" in out
    )
    assert "behaviour changes still need the suite (the compat cell)" in out


def test_a_commit_touching_both_packages_is_singled_out(
    workspace, capsys, offline
) -> None:
    """Chris's scenario: one feature commit changed the core and the extension together."""
    pypi(offline, {"acme-core": {"2.0.0": False}})
    offline.setattr(release_plan, "list_tags", lambda cwd=None: ["acme-core-v2.0.0"])
    history(
        offline,
        {"acme-core": [("5ha12ed0", "the shared feature"), ("c0e0n1y0", "a core fix")]},
    )
    offline.setattr(
        release_plan,
        "touched_files",
        lambda ref, paths, cwd=None: {
            "5ha12ed0": {
                "packages/acme-core/src/a.py",
                "packages/acme-ext/src/b.py",
            },
            "c0e0n1y0": {"packages/acme-core/src/c.py"},
        },
    )
    root = workspace(DIAMOND)
    assert run(root) == 0
    out = capsys.readouterr().out
    assert (
        "these changed both acme-core and acme-ext -- acme-ext very likely relies on the "
        "unreleased acme-core; bump and release acme-core first" in out
    )
    assert "5ha12ed0  the shared feature" in out
    # the core-only commit is counted, but it is not evidence about the extension
    assert "which lacks acme-core's 2 commits" in out
    assert "c0e0n1y0  a core fix" not in out.split("dependants:", 1)[1]


def test_an_extra_only_edge_gets_the_same_advice(workspace, capsys, offline) -> None:
    """`edges()` folds extras in, so the specifier lookup has to as well."""
    pypi(offline, {"acme-core": {"1.9.0": False}})
    root = workspace(
        {
            "acme-core": {"version": "2.0.0"},
            "acme-ext": {
                "version": "0.1.0",
                "optional_dependencies": {"all": ["acme-core>=2.0.0,<3"]},
            },
        }
    )
    assert run(root) == 0
    assert "the plan job WILL refuse `acme-ext-v0.1.0`" in capsys.readouterr().out


# --- the planner: tags, the sequence, and the seam that must stay out of `--tag` ----------


def test_a_bare_tag_is_a_release_of_sphinx_needs_only(
    workspace, capsys, offline
) -> None:
    offline.setattr(release_plan, "list_tags", lambda cwd=None: ["8.5.0"])
    root = workspace(
        {"sphinx-needs": {"version": "8.5.0"}, "acme-core": {"version": "8.5.0"}}
    )
    assert run(root) == 0
    out = capsys.readouterr().out
    assert "  last release tag   8.5.0" in out
    assert "last release tag   none -- never tagged" in out


def test_release_tags_skips_what_is_not_a_release(workspace) -> None:
    """`v.1.4` and a backup ref are tags in this repository and are not releases.

    `v2.0.0` is: PEP 440 normalises a leading `v` away, so it parses as 2.0.0 and names
    the pre-move release it says it does. That is the behaviour `previous_tag` has always
    had -- this factoring must not change it -- and it is harmless either way, because
    `2.0.0` is tagged as well and neither is ever the maximum.
    """
    tags = [
        "8.5.0",
        "v2.0.0",
        "v.1.4",
        "depbatch-backup-f8556477",
        "sphinx-needs-v8.6.0",
    ]
    assert release_plan.release_tags("sphinx-needs", tags) == [
        (Version("8.5.0"), "8.5.0"),
        (Version("2.0.0"), "v2.0.0"),
        (Version("8.6.0"), "sphinx-needs-v8.6.0"),
    ]
    assert release_plan.release_tags("acme-core", tags) == []


def test_the_suggested_sequence_is_dependencies_first(
    workspace, capsys, offline
) -> None:
    pypi(offline, {"acme-core": {"2.0.0": False}})
    offline.setattr(release_plan, "list_tags", lambda cwd=None: ["acme-core-v2.0.0"])
    history(offline, {"acme-core": [("aaa1111", "a core fix")]})
    root = workspace(DIAMOND)
    assert run(root) == 0
    out = capsys.readouterr().out.split("suggested sequence")[1]
    assert "1. after a bump: acme-core" in out
    assert "uv version --package acme-core --bump {patch|minor|major} --no-sync" in out
    assert "gh workflow run release.yaml -f tag=acme-core-v<new version>" in out
    assert "2. acme-ext 0.1.0" in out
    assert "git tag acme-ext-v0.1.0 && git push origin acme-ext-v0.1.0" in out


def test_a_virtual_member_is_never_analysed(workspace, capsys, offline) -> None:
    def explode(name: str):
        assert name != "acme-tools", "the planner asked PyPI about a virtual member"
        return {}

    offline.setattr(release_plan, "published_versions", explode)
    root = workspace(
        {
            "acme-core": {"version": "2.0.0"},
            "acme-tools": {"version": "0", "virtual": True},
        }
    )
    assert run(root) == 0
    out = capsys.readouterr().out
    assert "-- acme-tools 0   (virtual -- never published)" in out
    assert "acme-tools 0   (packages/acme-tools)" not in out


def test_tag_mode_never_reaches_the_planner_seams(workspace, capsys, offline) -> None:
    """R3: the plan job runs `--tag` with `--no-project`; the planner must not wake up."""

    def explode(*args, **kwargs):
        raise AssertionError("`--tag` mode must not call the planner's seams")

    published(offline, {("acme-core", "1.0.0"): False})
    offline.setattr(release_plan, "published_versions", explode)
    offline.setattr(release_plan, "commits_since", explode)
    offline.setattr(release_plan, "touched_files", explode)
    offline.setattr(release_plan, "head_context", explode)
    offline.setattr(release_plan, "resolve", explode)
    root = workspace({"acme-core": {"version": "1.0.0"}})
    assert run(root, "--tag", "acme-core-v1.0.0") == 0
    out = capsys.readouterr().out
    assert "release plan -- advice" not in out
    assert '"dist": "acme-core"' in out


# --- the planner predicts the gate that actually fires -------------------------------------
# Fix round 1, H2. `print_dependant` used to branch on "does any published non-yanked C
# satisfy D's specifier"; check (4) of the tag mode asks "is C's TREE version published".
# Those are different questions, and the divergence showed up in both directions on
# manifests `check_workspace.py` reports OK. Every test here runs BOTH modes over one index
# and asserts they agree about the verdict.


def both_modes(root: Path, capsys, dependant_tag: str) -> tuple[str, int]:
    """Run the planner, then the tag mode for the dependant, over the same mocked index."""
    assert run(root) == 0, "the planner must never gate, whatever it finds"
    planner_output = capsys.readouterr().out
    tag_exit = run(root, "--tag", dependant_tag, "--no-git")
    capsys.readouterr()
    return planner_output, tag_exit


def test_a_gap_in_the_index_is_predicted_as_check_4_refusing(
    workspace, capsys, offline
) -> None:
    """C's tree version was skipped on the index: the plan job refuses, and says so here.

    The reviewer's case (a). `usable` is non-empty -- 2.2.0 satisfies `>=2.1.0,<3` -- so the
    old code cheerfully said "would be tested against acme-core 2.2.0" about a tag the plan
    job then refused.
    """
    pypi_pair(
        offline,
        {"acme-core": {"2.0.0": False, "2.2.0": False}},
    )
    root = workspace(
        {
            "acme-core": {"version": "2.1.0"},
            "acme-ext": {"version": "0.1.0", "dependencies": ["acme-core>=2.1.0,<3"]},
        }
    )
    out, tag_exit = both_modes(root, capsys, "acme-ext-v0.1.0")
    assert (
        "the plan job WILL refuse `acme-ext-v0.1.0`: check 4 needs acme-core 2.1.0 on "
        "PyPI, and PyPI has 2.2.0 as its newest live version -- release acme-core first"
        in out
    )
    assert "would be tested against acme-core 2.2.0" not in out
    assert tag_exit == 1, "the planner promised a refusal; check 4 must deliver one"


def test_a_yanked_tree_version_names_the_resolver_gate_not_the_plan_job(
    workspace, capsys, offline
) -> None:
    """The reviewer's case (b): the per-version PyPI URL is 200 for a yanked release, so
    check (4) PASSES -- what stops the release is resolving a range from the index.

    Here the range has nothing else to resolve to: 2.0.0 is live but the dependant's floor
    is 2.1.0. When it DOES have something, the answer is different -- see the test below.
    """
    pypi_pair(
        offline,
        {"acme-core": {"2.0.0": False, "2.1.0": True}},
    )
    root = workspace(
        {
            "acme-core": {"version": "2.1.0"},
            "acme-ext": {"version": "0.1.0", "dependencies": ["acme-core>=2.1.0,<3"]},
        }
    )
    out, tag_exit = both_modes(root, capsys, "acme-ext-v0.1.0")
    assert (
        "the plan job passes (acme-core 2.1.0 is on PyPI) but every file of it is yanked "
        "and no other live acme-core satisfies acme-core>=2.1.0,<3, so the resolver gate "
        "-- `uv pip install --dry-run` against the index -- cannot resolve it: release a "
        "new acme-core" in out
    )
    assert "the plan job WILL refuse" not in out
    assert tag_exit == 0, "check 4 accepts a yanked release; the planner must not lie"


def test_a_specifier_no_release_satisfies_names_the_resolver_gate_and_lint(
    workspace, capsys, offline
) -> None:
    """The reviewer's case (c): C's tree version is published, but D's floor is above it."""
    pypi_pair(offline, {"acme-core": {"2.0.0": False}})
    root = workspace(
        {
            "acme-core": {"version": "2.0.0"},
            "acme-ext": {"version": "0.1.0", "dependencies": ["acme-core>=3.0.0,<4"]},
        }
    )
    out, tag_exit = both_modes(root, capsys, "acme-ext-v0.1.0")
    assert (
        "no published acme-core satisfies acme-core>=3.0.0,<4: the resolver gate fails "
        "(and Lint's check-workspace refuses a specifier that does not admit the tree's "
        "2.0.0)" in out
    )
    assert "the plan job WILL refuse" not in out
    assert tag_exit == 0, "check 4 only asks whether acme-core 2.0.0 is published"


def test_the_happy_path_still_describes_the_compat_cell(
    workspace, capsys, offline
) -> None:
    """The reviewer's case (d): nothing is wrong, so the only thing left to say is what the
    dependant would actually be tested against."""
    pypi_pair(offline, {"acme-core": {"2.0.0": False}})
    offline.setattr(release_plan, "list_tags", lambda cwd=None: ["acme-core-v2.0.0"])
    root = workspace(DIAMOND)
    out, tag_exit = both_modes(root, capsys, "acme-ext-v0.1.0")
    assert (
        "the compat cell installs acme-core from PyPI: `acme-ext-v0.1.0` would be tested "
        "against acme-core 2.0.0" in out
    )
    assert "the plan job WILL refuse" not in out
    assert "the resolver gate" not in out
    assert tag_exit == 0


# --- `--root` reaches git, on a real repository --------------------------------------------
# Fix round 1, M3/M2. Nothing below monkeypatches a git seam: that is the point.


def test_the_root_flag_drives_git_as_well_as_the_manifests(
    git_workspace, capsys, monkeypatch
) -> None:
    """`--root` named a tree while every git call answered about the process's own.

    The pytest process runs in THIS repository, whose HEAD, tags and history are nothing
    like the scratch one -- so before the fix this printed confident, wrong advice at exit 0.
    """
    monkeypatch.setattr(release_plan, "published_versions", lambda name: {})
    root = git_workspace({"acme-core": {"version": "1.0.0"}})
    first = commit(
        root,
        "the released commit",
        {"packages/acme-core/src/acme_core/__init__.py": "VALUE = 1\n"},
    )
    git_in(root, "tag", "acme-core-v1.0.0")
    second = commit(
        root,
        "an unreleased change",
        {"packages/acme-core/src/acme_core/x.py": "VALUE = 2\n"},
    )
    assert run(root) == 0
    out = capsys.readouterr().out
    assert f"HEAD {second} (main)" in out
    assert "last release tag   acme-core-v1.0.0" in out
    assert "1 commit since acme-core-v1.0.0 touched its shipped code" in out
    assert f"{second}  an unreleased change" in out
    assert f"{first}  the released commit" not in out
    # a scratch repository has no origin/master, and that is a fact to report, not an error
    assert "origin/master not found (no fetch?): ancestry not checked" in out


def test_only_shipped_paths_count_as_unreleased_work(
    git_workspace, capsys, monkeypatch
) -> None:
    """The planner's headline semantic, printed on every run and repeated in the docs:
    `<member>/src` and `<member>/pyproject.toml` count; docs and tests do not."""
    monkeypatch.setattr(
        release_plan, "published_versions", lambda name: {Version("1.0.0"): False}
    )
    root = git_workspace({"acme-core": {"version": "1.0.0"}})
    commit(
        root,
        "the released commit",
        {"packages/acme-core/src/acme_core/__init__.py": "VALUE = 1\n"},
    )
    git_in(root, "tag", "acme-core-v1.0.0")
    manifest = root / "packages/acme-core/pyproject.toml"
    src = commit(
        root, "src change", {"packages/acme-core/src/acme_core/x.py": "VALUE = 2\n"}
    )
    metadata = commit(
        root,
        "manifest change",
        {
            "packages/acme-core/pyproject.toml": manifest.read_text(encoding="utf-8")
            + '\ndescription = "scratch"\n'
        },
    )
    docs = commit(root, "docs change", {"packages/acme-core/docs/index.md": "hello\n"})
    tests = commit(
        root,
        "tests change",
        {"packages/acme-core/tests/test_x.py": "def test_x():\n    pass\n"},
    )
    assert run(root) == 0
    out = capsys.readouterr().out
    assert "2 unreleased commits since acme-core-v1.0.0" in out
    assert f"{src}  src change" in out
    assert f"{metadata}  manifest change" in out
    assert f"{docs}  docs change" not in out
    assert f"{tests}  tests change" not in out


def test_a_non_ascii_path_is_not_lost_by_gits_quoting(
    git_workspace, capsys, monkeypatch
) -> None:
    """git C-quotes such a path by default -- `"…/t\\303\\253st.py"`, quotes included -- and
    `under()` then matches nothing, so the both-packages heuristic misses the commit."""

    def published(name: str) -> dict[Version, bool]:
        return {Version("1.0.0"): False} if name == "acme-core" else {}

    monkeypatch.setattr(release_plan, "published_versions", published)
    root = git_workspace(
        {
            "acme-core": {"version": "1.0.0"},
            "acme-ext": {"version": "0.1.0", "dependencies": ["acme-core>=1.0.0,<2"]},
        }
    )
    commit(
        root,
        "the released commit",
        {"packages/acme-core/src/acme_core/__init__.py": "VALUE = 1\n"},
    )
    git_in(root, "tag", "acme-core-v1.0.0")
    shared = commit(
        root,
        "a shared feature",
        {
            "packages/acme-core/src/acme_core/x.py": "VALUE = 2\n",
            "packages/acme-ext/src/acme_ext/tëst.py": "VALUE = 3\n",
        },
    )
    assert run(root) == 0
    out = capsys.readouterr().out
    assert "these changed both acme-core and acme-ext" in out
    assert f"{shared}  a shared feature" in out


# --- PyPI answers this function does not get to guess about --------------------------------


def json_from(monkeypatch, payload: str) -> None:
    monkeypatch.setattr(
        release_plan.urllib.request,
        "urlopen",
        lambda url, timeout=30: io.BytesIO(payload.encode("utf-8")),
    )


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ("[1, 2, 3]", "PyPI returned a list, not an object"),
        ('{"releases": []}', "`releases` for"),
        (
            '{"releases": {"1.0.0": [1, 2]}}',
            "file list for acme-core 1.0.0 is not a list of objects",
        ),
    ],
)
def test_a_pypi_document_of_the_wrong_shape_is_refused(
    monkeypatch, payload: str, expected: str
) -> None:
    """Before this these were `AttributeError` tracebacks out of the one script whose whole
    subject is refusing to guess."""
    json_from(monkeypatch, payload)
    with pytest.raises(release_plan.PlanError) as excinfo:
        release_plan.published_versions("acme-core")
    assert expected in str(excinfo.value)


def test_a_pypi_read_timeout_is_refused_not_a_traceback(monkeypatch) -> None:
    """`TimeoutError` is an `OSError` and NOT a `URLError`: `urlopen`'s read phase does not
    wrap it, so the narrower clause let a timeout through as a traceback."""

    def raising(url: str, timeout: int = 30):
        raise TimeoutError("The read operation timed out")

    monkeypatch.setattr(release_plan.urllib.request, "urlopen", raising)
    with pytest.raises(release_plan.PlanError) as excinfo:
        release_plan.published_versions("acme-core")
    message = str(excinfo.value)
    assert "cannot reach PyPI" in message
    assert "refusing to advise on a guess about what acme-core has published" in message


def test_a_release_with_no_files_left_counts_as_yanked(monkeypatch) -> None:
    """Nothing installable is left, which is the property `latest` is about."""
    json_from(
        monkeypatch,
        '{"releases": {"1.0.0": [], "2.0.0": [{"yanked": false}],'
        ' "3.0.0": [{"yanked": true}, {"yanked": true}],'
        ' "4.0.0": [{"yanked": true}, {"yanked": false}]}}',
    )
    assert release_plan.published_versions("acme-core") == {
        Version("1.0.0"): True,
        Version("2.0.0"): False,
        Version("3.0.0"): True,
        # one usable file is enough to install, so this release is not yanked
        Version("4.0.0"): False,
    }


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("packages/core/src", True),
        ("packages/core/src/x/a.py", True),
        ("packages/core/pyproject.toml", True),
        # the boundary: a sibling whose name merely starts with the same characters
        ("packages/core/srcfoo/x.py", False),
        ("packages/core/src.py", False),
        ("packages/core/pyproject.toml.bak", False),
        ("packages/core/docs/index.md", False),
        ("packages/coretools/src/x.py", False),
    ],
)
def test_under_respects_the_path_boundary(path: str, expected: bool) -> None:
    roots = ["packages/core/src", "packages/core/pyproject.toml"]
    assert release_plan.under(path, roots) is expected


# --- fix round 2: the yank only matters when the range has nowhere else to go -------------


def test_a_yanked_tree_version_the_range_can_route_around_is_not_a_blocker(
    workspace, capsys, offline
) -> None:
    """V2. `2.1.0` is yanked, but `2.0.0` is live and satisfies `>=2.0.0,<3` -- so the
    resolver gate succeeds and the compat cell tests against `2.0.0`.

    Firing the yanked branch unconditionally asserted the opposite, told the reader to cut a
    release that is not needed, and (because it returned first) suppressed the compat-cell
    line, the "lacks N commits" clause and the both-packages heuristic entirely.
    """
    pypi_pair(offline, {"acme-core": {"2.0.0": False, "2.1.0": True}})
    offline.setattr(release_plan, "list_tags", lambda cwd=None: ["acme-core-v2.0.0"])
    history(offline, {"acme-core": [("5ha12ed0", "the shared feature")]})
    offline.setattr(
        release_plan,
        "touched_files",
        lambda ref, paths, cwd=None: {
            "5ha12ed0": {"packages/acme-core/src/a.py", "packages/acme-ext/src/b.py"}
        },
    )
    root = workspace(
        {
            "acme-core": {"version": "2.1.0"},
            "acme-ext": {"version": "0.1.0", "dependencies": ["acme-core>=2.0.0,<3"]},
        }
    )
    out, tag_exit = both_modes(root, capsys, "acme-ext-v0.1.0")
    assert (
        "the compat cell installs acme-core from PyPI: `acme-ext-v0.1.0` would be tested "
        "against acme-core 2.0.0 (acme-core 2.1.0, this tree's version, is yanked, so the "
        "index resolves to 2.0.0 instead), which lacks acme-core's 1 commit since "
        "acme-core-v2.0.0" in out
    )
    # the branch that used to swallow all of this
    assert "cannot resolve it: release a new acme-core" not in out
    assert "these changed both acme-core and acme-ext" in out
    assert "5ha12ed0  the shared feature" in out
    assert tag_exit == 0


def test_an_index_that_is_entirely_yanked_is_not_an_empty_one(
    workspace, capsys, offline
) -> None:
    """V3. `core.latest` is None when every release is yanked, and "PyPI has nothing" is a
    different, wronger fact -- `print_status` five lines above already gets this right."""
    pypi_pair(offline, {"acme-core": {"1.0.0": True, "2.0.0": True}})
    root = workspace(
        {
            "acme-core": {"version": "3.0.0"},
            "acme-ext": {"version": "0.1.0", "dependencies": ["acme-core>=3.0.0,<4"]},
        }
    )
    assert run(root) == 0
    out = capsys.readouterr().out
    assert (
        "check 4 needs acme-core 3.0.0 on PyPI, and PyPI has 2 versions, all yanked -- "
        "release acme-core first" in out
    )
    assert "PyPI has nothing" not in out
    # and the member's own block agrees with the dependant's
    assert "on PyPI            2 versions, latest: none -- every version yanked" in out


# --- fix round 2: the sixth `cwd` call site --------------------------------------------


def test_the_ancestry_check_asks_the_root_repository(
    git_workspace, capsys, monkeypatch
) -> None:
    """V5. The one `--root` call site no test reached: the existing fixture has no
    `origin/master`, so `is_ancestor` never ran and dropping its `cwd` stayed green.

    Asking THIS repository instead would answer about a HEAD that is not on origin/master
    (this branch is not), so the false line appears exactly when the true one should not.
    """
    monkeypatch.setattr(release_plan, "published_versions", lambda name: {})
    root = git_workspace({"acme-core": {"version": "1.0.0"}})
    commit(
        root,
        "the first commit",
        {"packages/acme-core/src/acme_core/__init__.py": "VALUE = 1\n"},
    )
    git_in(root, "update-ref", "refs/remotes/origin/master", "HEAD")
    assert run(root) == 0
    out = capsys.readouterr().out
    assert "origin/master not found" not in out
    assert "HEAD is not on origin/master" not in out


def test_a_head_off_the_root_repositorys_master_is_reported(
    git_workspace, capsys, monkeypatch
) -> None:
    """The other direction, so the absence above is a measurement and not a silence."""
    monkeypatch.setattr(release_plan, "published_versions", lambda name: {})
    root = git_workspace({"acme-core": {"version": "1.0.0"}})
    first = commit(
        root,
        "the first commit",
        {"packages/acme-core/src/acme_core/__init__.py": "VALUE = 1\n"},
    )
    git_in(root, "update-ref", "refs/remotes/origin/master", first)
    commit(root, "off master", {"packages/acme-core/src/acme_core/x.py": "VALUE = 2\n"})
    assert run(root) == 0
    out = capsys.readouterr().out
    assert "HEAD is not on origin/master -- releases are cut from master" in out
    assert "origin/master not found" not in out


def test_an_unreachable_pypi_names_the_reason_not_the_wrapper(monkeypatch) -> None:
    """A `URLError` is reported by its `.reason` -- `[Errno 61] Connection refused` -- exactly
    as `on_pypi` reports it two functions away, not by the `<urlopen error ...>` wrapper that
    `str(exc)` gives. The two messages must not drift: they describe the same outage."""
    import urllib.error

    def raising(url: str, timeout: int = 30):
        raise urllib.error.URLError(OSError(61, "Connection refused"))

    monkeypatch.setattr(release_plan.urllib.request, "urlopen", raising)
    with pytest.raises(release_plan.PlanError) as caught:
        release_plan.published_versions("acme-core")
    message = str(caught.value)
    assert "cannot reach PyPI ([Errno 61] Connection refused)" in message
    assert "<urlopen error" not in message
