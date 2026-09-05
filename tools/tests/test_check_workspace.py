"""Every check in `check_workspace.py`, red and green.

The point of each of these is a mistake that no other gate in the repository can see: uv
resolves the workspace copy whatever a specifier says, the specifier is not in `uv.lock` at
all, and a member out of step with the root's `requires-python` still locks, builds and
publishes. So the tests assert on the *messages* as well as the exit codes -- a fence whose
output does not name the file and the fix is one nobody acts on.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sn_tools import check_workspace

pytestmark = pytest.mark.filterwarnings("error")


def run(root: Path, *args: str) -> int:
    return check_workspace.main([*args, "--root", str(root)])


def test_green(workspace, capsys) -> None:
    root = workspace({"acme-core": {"version": "1.2.3", "module_version": "1.2.3"}})
    assert run(root) == 0
    out = capsys.readouterr().out
    assert "the root lists every member, bare: acme-core" in out
    assert "every member is sourced from the workspace" in out
    assert "requires-python >=3.11,<4" in out
    assert "no intra-workspace runtime dependencies among 1 member(s)" in out
    assert "__version__ == 1.2.3" in out


def test_green_with_an_honest_tight_edge(workspace, capsys) -> None:
    root = workspace(
        {
            "acme-core": {"version": "2.0.0"},
            "acme-ext": {"version": "0.1.0", "dependencies": ["acme-core>=2.0.0,<3"]},
        }
    )
    assert run(root) == 0
    assert "acme-ext -> acme-core<3,>=2.0.0  (workspace acme-core 2.0.0)" in (
        capsys.readouterr().out
    )


# --- (1) the root lists every member, bare --------------------------------------------


def test_root_missing_a_member(workspace, capsys) -> None:
    root = workspace({"acme-core": {}}, root_dependencies=[])
    assert run(root) == 1
    out = capsys.readouterr().out
    assert "::error file=pyproject.toml::`acme-core` is a workspace member" in out
    assert "a bare `uv sync` does not install it" in out


def test_root_depends_on_a_non_member(workspace, capsys) -> None:
    root = workspace({"acme-core": {}}, root_dependencies=["acme-core", "requests"])
    assert run(root) == 1
    out = capsys.readouterr().out
    assert "the root depends on `requests`, which is not a workspace member" in out


def test_root_dependency_is_not_bare(workspace, capsys) -> None:
    root = workspace({"acme-core": {}}, root_dependencies=["acme-core>=1"])
    assert run(root) == 1
    out = capsys.readouterr().out
    assert "the root dependency `acme-core>=1` is not bare" in out
    assert "Write `acme-core`" in out


# --- (2) every member is sourced from the workspace -----------------------------------


def test_member_without_a_source_entry(workspace, capsys) -> None:
    root = workspace({"acme-core": {}}, sources={})
    assert run(root) == 1
    out = capsys.readouterr().out
    assert "`acme-core` is a workspace member with no [tool.uv.sources] entry" in out
    # the message quotes what uv itself says, measured on uv 0.12.9
    assert "is included as a workspace member, but is missing" in out
    # ... and the check does not also claim success
    assert "every member is sourced from the workspace" not in out


def test_one_bad_source_among_several(workspace, capsys) -> None:
    root = workspace(
        {"acme-core": {}, "acme-ext": {}},
        sources={"acme-core": "{ workspace = true }"},
    )
    assert run(root) == 1
    out = capsys.readouterr().out
    assert "`acme-ext` is a workspace member with no [tool.uv.sources] entry" in out
    assert "every member is sourced from the workspace" not in out


def test_member_sourced_from_somewhere_else(workspace, capsys) -> None:
    root = workspace(
        {"acme-core": {}}, sources={"acme-core": '{ git = "https://example.invalid" }'}
    )
    assert run(root) == 1
    out = capsys.readouterr().out
    assert "does not resolve the member in this tree" in out
    assert "every member is sourced from the workspace" not in out


# --- (3) requires-python equality (the retired inline ci.yaml step) --------------------


def test_member_requires_python_differs(workspace, capsys) -> None:
    root = workspace({"acme-core": {"requires_python": ">=3.12,<4"}})
    assert run(root) == 1
    out = capsys.readouterr().out
    assert (
        "::error file=packages/acme-core/pyproject.toml::requires-python is >=3.12,<4, "
        "but the root declares >=3.11,<4" in out
    )


# --- (4) intra-workspace specifiers ----------------------------------------------------


def test_specifier_does_not_admit_the_tree(workspace, capsys) -> None:
    root = workspace(
        {
            "acme-core": {"version": "1.2.3"},
            "acme-ext": {"dependencies": ["acme-core>=99"]},
        }
    )
    assert run(root) == 1
    out = capsys.readouterr().out
    assert (
        "the workspace builds acme-core 1.2.3, which this specifier does not admit"
        in out
    )
    assert "uv#9811" in out


def test_specifier_is_admitted_but_not_tight(workspace, capsys) -> None:
    root = workspace(
        {
            "acme-core": {"version": "1.2.3"},
            "acme-ext": {"dependencies": ["acme-core>=1.0"]},
        }
    )
    assert run(root) == 1
    out = capsys.readouterr().out
    assert "tight tracking wants `acme-core<2,>=1.2.3`" in out
    assert "propagate_floors.py acme-core" in out


def test_a_runtime_dependency_on_a_virtual_member_is_an_error(
    workspace, capsys
) -> None:
    """`[tool.uv] package = false` means uv can build it with no command, so it is never on
    PyPI and a wheel naming it could not be installed."""
    root = workspace(
        {
            "acme-core": {"version": "2.0.0", "dependencies": ["acme-tools>=0,<1"]},
            "acme-tools": {"version": "0", "virtual": True},
        }
    )
    assert run(root) == 1
    out = capsys.readouterr().out
    assert "`acme-tools` is `[tool.uv] package = false`" in out
    assert "could never be installed" in out


def test_a_virtual_member_is_otherwise_checked_like_any_other(
    workspace, capsys
) -> None:
    """Only the runtime-edge rule is special: the rest applies unchanged."""
    root = workspace(
        {
            "acme-core": {"version": "2.0.0"},
            "acme-tools": {
                "version": "0",
                "virtual": True,
                "requires_python": ">=3.12,<4",
            },
        }
    )
    assert run(root) == 1
    out = capsys.readouterr().out
    assert (
        "::error file=packages/acme-tools/pyproject.toml::requires-python is >=3.12,<4"
        in out
    )


def test_no_policy_accepts_a_loose_but_honest_floor(workspace, capsys) -> None:
    root = workspace(
        {
            "acme-core": {"version": "1.2.3"},
            "acme-ext": {"dependencies": ["acme-core>=1.0"]},
        }
    )
    assert run(root, "--no-policy") == 0
    assert "OK    acme-ext -> acme-core>=1.0" in capsys.readouterr().out


def test_an_extra_is_checked_too(workspace, capsys) -> None:
    root = workspace(
        {
            "acme-core": {"version": "1.2.3"},
            "acme-ext": {"optional_dependencies": {"all": ["acme-core>=99"]}},
        }
    )
    assert run(root) == 1
    assert "acme-ext[all] -> acme-core>=99" in capsys.readouterr().out


def test_dynamic_member_version_is_an_error(workspace, capsys) -> None:
    root = workspace({"acme-core": {"version": None}})
    assert run(root) == 1
    out = capsys.readouterr().out
    assert "acme-core declares a dynamic version" in out
    assert "uv version --package" in out


# --- (5) `__version__` agrees with the manifest ---------------------------------------


def test_module_version_disagrees(workspace, capsys) -> None:
    root = workspace({"acme-core": {"version": "8.5.0", "module_version": "8.5.1"}})
    assert run(root) == 1
    out = capsys.readouterr().out
    assert "::error file=packages/acme-core/src/acme_core/__init__.py::" in out
    assert '__version__ = "8.5.1"' in out
    assert 'version = "8.5.0"' in out


def test_module_without_a_version_literal_is_skipped(workspace, capsys) -> None:
    root = workspace({"acme-core": {"version": "8.5.0"}})
    (root / "packages/acme-core/src/acme_core").mkdir(parents=True)
    (root / "packages/acme-core/src/acme_core/__init__.py").write_text(
        '"""no version here."""\n', encoding="utf-8"
    )
    assert run(root) == 0
    assert "__version__" not in capsys.readouterr().out


def test_module_name_comes_from_tool_flit_module(workspace, capsys) -> None:
    root = workspace(
        {
            "acme-core": {
                "version": "8.5.0",
                "module_version": "8.5.1",
                "module_name": "acme",
            }
        }
    )
    assert run(root) == 1
    assert "packages/acme-core/src/acme/__init__.py" in capsys.readouterr().out


# --- everything is reported, not just the first -----------------------------------------


def test_every_failure_is_reported_in_one_run(workspace, capsys) -> None:
    root = workspace(
        {
            "acme-core": {"version": "1.2.3", "requires_python": ">=3.12,<4"},
            "acme-ext": {
                "version": "0.1.0",
                "dependencies": ["acme-core>=99"],
                "module_version": "0.2.0",
            },
        },
        root_dependencies=["acme-core"],
    )
    assert run(root) == 1
    out = capsys.readouterr().out
    assert out.count("::error") == 4, out
    assert "`acme-ext` is a workspace member but is not in the root" in out
    assert "requires-python is >=3.12,<4" in out
    assert "does not admit" in out
    assert "__version__" in out


def test_a_member_with_no_name_is_annotated_not_a_traceback(workspace, capsys) -> None:
    """It used to raise KeyError('name') -- fail closed, but with no annotation."""
    root = workspace({"acme-core": {"version": "1.0.0"}})
    (root / "packages/acme-core/pyproject.toml").write_text(
        '[project]\nversion = "1.0.0"\n', encoding="utf-8"
    )
    assert run(root) == 1
    out = capsys.readouterr().out
    assert "::error file=packages/acme-core/pyproject.toml::" in out
    assert "[project] declares no `name`" in out
    assert "Traceback" not in out


# --- source keys are canonicalised, as uv canonicalises them ---------------------------


def test_a_source_key_spelled_differently_is_the_same_member(workspace, capsys) -> None:
    """uv accepts `my_member` for a member named `My_Member`; so must this."""
    root = workspace(
        {"My_Member": {"version": "1.0.0"}},
        root_dependencies=["My_Member"],
        sources={"my_member": "{ workspace = true }"},
    )
    assert run(root) == 0
    assert "every member is sourced from the workspace" in capsys.readouterr().out


# --- the edges ---------------------------------------------------------------------------


def test_a_member_below_the_first_level_gets_a_root_relative_annotation(
    workspace, capsys
) -> None:
    """`::error file=` is resolved against the workspace root, so the path must be too."""
    root = workspace(
        {"acme-core": {"version": "8.5.0", "module_version": "8.5.1"}},
        member_globs=["packages/*/*"],
        directories={"acme-core": "packages/group/acme-core"},
    )
    assert run(root) == 1
    out = capsys.readouterr().out
    assert "::error file=packages/group/acme-core/src/acme_core/__init__.py::" in out, (
        out
    )


def test_a_member_matched_by_two_globs_is_counted_once(workspace, capsys) -> None:
    root = workspace(
        {"acme-core": {"version": "1.0.0"}},
        member_globs=["packages/*", "packages/acme-core"],
    )
    assert run(root) == 0
    out = capsys.readouterr().out
    assert out.count("packages/acme-core/pyproject.toml: requires-python") == 1
    assert "among 1 member(s)" in out


def test_a_non_bare_root_dependency_does_not_also_print_ok(workspace, capsys) -> None:
    root = workspace({"acme-core": {}}, root_dependencies=["acme-core>=1"])
    assert run(root) == 1
    out = capsys.readouterr().out
    assert "is not bare" in out
    assert "the root lists every member, bare" not in out


def test_a_nameless_member_is_one_error_not_two(workspace, capsys) -> None:
    """The member's own error is the actionable one; a "matches no package" ERROR on top of
    it would show two problems where there is one."""
    root = workspace({"acme-core": {"version": "1.0.0"}}, root_dependencies=[])
    (root / "packages/acme-core/pyproject.toml").write_text(
        '[project]\nversion = "1.0.0"\n', encoding="utf-8"
    )
    assert run(root) == 1
    out = capsys.readouterr().out
    assert out.count("::error") == 1, out
    assert "[project] declares no `name`" in out
    # the glob is still reported, as context rather than as a second finding
    assert "matches no usable package in this tree -- see the errors above" in out


def test_a_members_glob_matching_nothing_at_all_is_still_reported(
    tmp_path: Path, capsys
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "root"\nversion = "0"\nrequires-python = ">=3.11,<4"\n'
        'dependencies = []\n\n[tool.uv.workspace]\nmembers = ["packages/*"]\n',
        encoding="utf-8",
    )
    assert check_workspace.main(["--root", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "matches no package in this tree" in out
    assert "no usable package" not in out


def test_no_workspace_members_key(tmp_path: Path, capsys) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0"\n', encoding="utf-8"
    )
    assert check_workspace.main(["--root", str(tmp_path)]) == 1
    assert "no [tool.uv.workspace] members" in capsys.readouterr().out


def test_no_manifest_at_all(tmp_path: Path, capsys) -> None:
    assert check_workspace.main(["--root", str(tmp_path / "nope")]) == 2
    assert "run this at the workspace root" in capsys.readouterr().out


def test_an_unparseable_member_manifest_is_named(workspace, capsys) -> None:
    root = workspace({"acme-core": {"version": "1.0.0"}})
    (root / "packages/acme-core/pyproject.toml").write_text(
        '[project]\nname = "acme-core"\ndependencies = [\n', encoding="utf-8"
    )
    assert run(root) == 1
    out = capsys.readouterr().out
    assert "::error file=packages/acme-core/pyproject.toml::" in out
    assert "not valid TOML" in out


def test_an_unparseable_root_manifest_is_named(tmp_path: Path, capsys) -> None:
    (tmp_path / "pyproject.toml").write_text("[project\n", encoding="utf-8")
    assert check_workspace.main(["--root", str(tmp_path)]) == 2
    assert "::error file=pyproject.toml::" in capsys.readouterr().out
