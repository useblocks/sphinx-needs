"""`scripts/smoke_needs.py`'s sibling mode: which members it builds, and what it asserts.

The smoke test itself needs `uv`, the network and a minute, so it is run by CI's two smoke
jobs and `uv run poe smoke-needs[-published]`, never from here. What this module covers is
the logic those runs rest on and cannot show by passing: the sibling set is read off the
manifests (runtime `dependencies`, transitively, never an extra), and a sibling that quietly
came from the index instead of the tree is a FAILED check rather than a pass -- the
import-location check alone cannot tell the two apart when the versions agree, which on a
pull request they usually do.

It also fences the CI shape the mode was made for: `smoke-needs` stays required through the
`check` aggregator, and `smoke-needs-published` stays out of it.

The script lives in `scripts/`, outside every package and outside `tools/src`, so it is
loaded by path here (the same way CI runs it).
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import zipfile
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
CI = REPO / ".github" / "workflows" / "ci.yaml"

# the jobs `check` deliberately does not wait for, each with the reason; adding one here is
# a decision about branch protection, which is why this is a list in a test and not a glob
INFORMATIONAL = {
    # the siblings as PUBLISHED: red on a pull request means "release a sibling first"
    "smoke-needs-published",
}


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "smoke_needs", REPO / "scripts" / "smoke_needs.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # registered before exec, as the import system does for a module it loads itself
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


smoke = _load()


# --- the sibling set ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("spec", "name"),
    [
        ("ub-project>=1.1.0,<2", "ub-project"),
        ("ub_project >=1.1", "ub-project"),
        ("UB.Project", "ub-project"),
        ("ub-project[extra]~=1.1", "ub-project"),
        ("  ub-project ; python_version >= '3.12'", "ub-project"),
        ("x", "x"),
    ],
)
def test_requirement_name(spec: str, name: str) -> None:
    """The PEP 503 name heads the requirement, whatever spelling and suffix follow."""
    assert smoke.requirement_name(spec) == name


@pytest.mark.parametrize("spec", ["", "  ", ">=1.0", "-leading-dash"])
def test_requirement_name_refuses_what_names_nothing(spec: str) -> None:
    with pytest.raises(smoke.SmokeError, match="cannot read a distribution name"):
        smoke.requirement_name(spec)


def test_siblings_are_runtime_dependencies_transitively(workspace) -> None:
    """Followed through a sibling, never through an extra, never to a non-member.

    `core` reaches `base` only through `mid`, so a direct-only lookup would install a
    published `base` under a tree `mid`. `docs-only` is an extra's, which the smoke test's
    install never asks for (sphinx-ai-index is sphinx-needs' case of it).
    """
    root = workspace(
        {
            "core": {
                "dependencies": ["mid>=1", "sphinx>=7"],
                "optional_dependencies": {"docs": ["docs-only>=1"]},
            },
            "mid": {"dependencies": ["base>=1"]},
            "base": {},
            "docs-only": {},
            "unrelated": {"dependencies": ["base"]},
        }
    )
    members = smoke.workspace_members(root)
    assert smoke.runtime_siblings("core", members) == ["base", "mid"]
    assert smoke.runtime_siblings("base", members) == []
    # any spelling of the distribution names it
    assert smoke.runtime_siblings("Core", members) == ["base", "mid"]


def test_a_cycle_never_lists_the_package_itself(workspace) -> None:
    root = workspace(
        {"core": {"dependencies": ["mid"]}, "mid": {"dependencies": ["core"]}}
    )
    assert smoke.runtime_siblings("core", smoke.workspace_members(root)) == ["mid"]


def test_a_package_outside_any_workspace_has_no_siblings(tmp_path: Path) -> None:
    """The docstring's single-package usage (`smoke_needs.py .`) keeps working."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "solo"\nversion = "1"\n', encoding="utf-8"
    )
    members = smoke.workspace_members(tmp_path)
    assert members == {}
    assert smoke.runtime_siblings("solo", members) == []


def test_a_marker_on_a_sibling_is_refused_in_tree_mode_only(workspace) -> None:
    """A wheel given by path is installed unconditionally, so tree mode cannot honour a
    marker; published mode builds nothing and lets the resolver decide as before."""
    root = workspace(
        {"core": {"dependencies": ["mid; python_version >= '3.12'"]}, "mid": {}}
    )
    members = smoke.workspace_members(root)
    with pytest.raises(smoke.SmokeError, match="environment marker"):
        smoke.runtime_siblings("core", members)
    assert smoke.runtime_siblings("core", members, refuse_markers=False) == ["mid"]


def test_a_virtual_member_is_recorded(workspace) -> None:
    root = workspace({"core": {"dependencies": ["tools"]}, "tools": {"virtual": True}})
    members = smoke.workspace_members(root)
    assert members["tools"].virtual
    assert not members["core"].virtual


def test_sphinx_needs_siblings_in_this_repository() -> None:
    """The real manifests: both runtime siblings are reached (ub-project is the motivating
    case, #2383), the docs extra's sphinx-ai-index is not, and each is a member CI can
    build."""
    members = smoke.workspace_members(REPO)
    siblings = smoke.runtime_siblings("sphinx-needs", members)
    assert "ub-project" in siblings
    assert "ub-needs-exchange" in siblings
    assert "sphinx-ai-index" not in siblings
    assert "sphinx-needs" not in siblings
    assert all(not members[name].virtual for name in siblings)


def test_wheel_modules(tmp_path: Path) -> None:
    """Packages and single-file modules; never the metadata, the data dir or a `.pth`."""
    wheel = tmp_path / "acme-1.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        for name in [
            "acme/__init__.py",
            "acme/sub/__init__.py",
            "acme_compat.py",
            "acme-1.0.dist-info/METADATA",
            "acme-1.0.data/scripts/run",
            "acme.pth",
        ]:
            archive.writestr(name, "")
    assert smoke.wheel_modules(wheel) == ["acme", "acme_compat"]


# --- what is asserted of a sibling -------------------------------------------------------

WORKSPACE = {"sphinx-needs", "ub-project", "ub-needs-exchange", "sphinx-ai-index"}


@pytest.fixture
def probe(monkeypatch: pytest.MonkeyPatch):
    """Stand in for the in-environment probe: answer with the given report."""

    def answer(report: dict[str, Any] | None) -> None:
        def fake(
            cmd: list[str], *, cwd: Path, label: str | None = None
        ) -> subprocess.CompletedProcess[str]:
            assert report is not None, "the probe ran where nothing was to be checked"
            return subprocess.CompletedProcess(cmd, 0, json.dumps(report) + "\n", "")

        monkeypatch.setattr(smoke, "run", fake)

    return answer


def _dist(source: Path | None, version: str = "1.1.0") -> dict[str, Any]:
    """One installed distribution as the probe reports it; `None` is "from the index"."""
    return {
        "version": version,
        "direct_url": json.dumps({"url": source.as_uri(), "archive_info": {}})
        if source
        else None,
    }


def _report(
    venv: Path, installed: dict[str, dict[str, Any]], location: Path | None = None
) -> dict[str, Any]:
    """The probe's answer. Always carries the package itself (from a path: it is never
    checked) and a non-member from the index (never checked either), as a real one does."""
    return {
        "installed": {
            "sphinx_needs": _dist(venv.parent / "sphinx_needs-9.1.0-py3-none-any.whl"),
            "Sphinx": _dist(None, "8.2.3"),
            **installed,
        },
        "files": {
            "ub_project": str(
                location or venv / "lib" / "site-packages" / "ub_project" / "x.py"
            )
        },
    }


def _plan(tree_wheels: dict[str, Path], *, tree: bool = True) -> Any:
    return smoke.Siblings(
        "sphinx-needs", WORKSPACE, tree, tree_wheels, ["ub_project"] if tree else []
    )


def _check(venv: Path, plan: Any, where: str = "wheel's environment") -> list[str]:
    checks = smoke.Checks()
    smoke.check_siblings(venv / "bin" / "python", venv, plan, where, checks)
    return checks.failures


def test_the_tree_wheel_in_the_environment_passes(tmp_path: Path, probe) -> None:
    venv = tmp_path / "venv"
    wheel = tmp_path / "dist with space" / "ub_project-1.1.0-py3-none-any.whl"
    probe(_report(venv, {"ub-project": _dist(wheel)}))
    assert _check(venv, _plan({"ub-project": wheel})) == []


def test_a_sibling_from_the_index_fails_in_tree_mode(tmp_path: Path, probe) -> None:
    """THE silent fallback: same version, imported from the environment -- and still red,
    because there is no `direct_url.json` naming the wheel this tree built."""
    venv = tmp_path / "venv"
    probe(_report(venv, {"ub_project": _dist(None)}))
    wheel = tmp_path / "ub_project-1.1.0-py3-none-any.whl"
    assert _check(venv, _plan({"ub-project": wheel})) == [
        "ub-project in the wheel's environment is the wheel this tree built, not the index's"
    ]


def test_a_member_the_lookup_missed_fails_in_tree_mode(
    tmp_path: Path, probe, capsys: pytest.CaptureFixture[str]
) -> None:
    """A workspace member installed WITHOUT a tree wheel -- reached, say, through
    `ub-project[ai]` and an `ai` extra naming sphinx-ai-index, which `runtime_siblings`
    does not follow -- came from the index, and is named rather than passed over: the
    check is against what is installed, not against the derivation."""
    venv = tmp_path / "venv"
    wheel = tmp_path / "ub_project-1.1.0-py3-none-any.whl"
    probe(
        _report(
            venv,
            {"ub-project": _dist(wheel), "sphinx_ai_index": _dist(None, "1.0.0")},
        )
    )
    assert _check(venv, _plan({"ub-project": wheel})) == [
        "sphinx-ai-index in the wheel's environment is the wheel this tree built, "
        "not the index's"
    ]
    assert "the sibling lookup missed it" in capsys.readouterr().out


def test_a_tree_wheel_that_is_not_installed_fails(tmp_path: Path, probe) -> None:
    venv = tmp_path / "venv"
    probe(_report(venv, {}))
    wheel = tmp_path / "ub_project-1.1.0-py3-none-any.whl"
    assert _check(venv, _plan({"ub-project": wheel})) == [
        "ub-project is installed in the wheel's environment"
    ]


def test_a_sibling_imported_from_the_checkout_fails(tmp_path: Path, probe) -> None:
    venv = tmp_path / "venv"
    wheel = tmp_path / "ub_project-1.1.0-py3-none-any.whl"
    checkout = REPO / "packages" / "ub-project" / "src" / "x.py"
    probe(_report(venv, {"ub-project": _dist(wheel)}, checkout))
    assert _check(venv, _plan({"ub-project": wheel}), "sdist's environment") == [
        "ub_project imports from the sdist's environment, not the checkout"
    ]


def test_published_mode_wants_every_member_from_the_index(
    tmp_path: Path, probe, capsys: pytest.CaptureFixture[str]
) -> None:
    venv = tmp_path / "venv"
    probe(_report(venv, {"ub-project": _dist(None), "ub-needs-exchange": _dist(None)}))
    assert _check(venv, _plan({}, tree=False)) == []
    out = capsys.readouterr().out
    assert "ub-project 1.1.0 from the index" in out
    assert "ub-needs-exchange 1.1.0 from the index" in out


def test_published_mode_fails_on_a_member_from_a_file(tmp_path: Path, probe) -> None:
    """The pre-release check cannot go green on a sibling that did not come from PyPI."""
    venv = tmp_path / "venv"
    wheel = tmp_path / "ub_project-1.1.0-py3-none-any.whl"
    probe(_report(venv, {"ub-project": _dist(wheel)}))
    assert _check(venv, _plan({}, tree=False)) == [
        "ub-project in the wheel's environment is the index's, as published"
    ]


def test_no_workspace_runs_no_probe(tmp_path: Path, probe) -> None:
    """A single-package repository: nothing is a workspace member, nothing is probed."""
    probe(None)
    plan = smoke.Siblings("solo", set(), True, {}, [])
    assert _check(tmp_path / "venv", plan) == []


# --- the CI shape ------------------------------------------------------------------------


def _jobs() -> dict[str, Any]:
    return yaml.safe_load(CI.read_text(encoding="utf-8"))["jobs"]


def test_check_waits_for_every_job_but_the_informational_ones() -> None:
    """`check` is the one required status, so a job it does not wait for gates nothing:
    a new job is either listed there or named in INFORMATIONAL above, never forgotten."""
    jobs = _jobs()
    needs = set(jobs["check"]["needs"])
    assert "smoke-needs" in needs
    assert needs.isdisjoint(INFORMATIONAL)
    assert needs | INFORMATIONAL == set(jobs) - {"check"}


def test_the_published_smoke_job_mirrors_the_required_one() -> None:
    """Same runner setup (graphviz, the 3.11 floor) as `smoke-needs`; only the task
    differs, and a red does not fail the run."""
    jobs = _jobs()
    required, published = jobs["smoke-needs"], jobs["smoke-needs-published"]
    assert published.get("continue-on-error") is True
    assert "continue-on-error" not in required

    def setup(job: dict[str, Any]) -> list[Any]:
        return [
            step
            for step in job["steps"]
            if "poe smoke-needs" not in step.get("run", "")
        ]

    assert setup(published) == setup(required)
    assert published["runs-on"] == required["runs-on"]
    assert published["steps"][-1]["run"] == "uv run --frozen poe smoke-needs-published"
    assert required["steps"][-1]["run"] == "uv run --frozen poe smoke-needs"
